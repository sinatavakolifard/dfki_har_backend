# HAR Backend

Local-only FastAPI + PostgreSQL backend for the
[`dfki_human_activity_recognition`](../dfki_human_activity_recognition) Flutter
app. Devices upload session CSVs gzip-compressed; the server stores the
compressed bytes directly in Postgres (`bytea`) along with metadata.

## Stack

- FastAPI on Python 3.12
- PostgreSQL 16 (compressed CSVs live in a `bytea` column)
- SQLAlchemy 2.0 async + asyncpg
- Alembic for migrations
- Single shared `X-API-Key` for auth

## Run it locally

```bash
cp .env.example .env
# edit .env: set HAR_API_KEY to something long and random
docker compose up --build
```

That brings up Postgres + the API on `http://localhost:8000`. The API
container runs `alembic upgrade head` on start, so the schema is in place
before it serves traffic.

Sanity check:

```bash
curl http://localhost:8000/health
# {"status":"ok"}
```

OpenAPI docs: `http://localhost:8000/docs`.

## API

All routes under `/v1/*` require `X-API-Key: <HAR_API_KEY>`. `/health` does
not.

### Users

- `PUT  /v1/users/{user_id}` — upsert the device's profile (idempotent).
  Body: `{"age": 30, "height_cm": 175, "weight_kg": 70, "gender": "f"}`,
  all fields optional.
- `GET  /v1/users/{user_id}` — fetch.

### Sessions

- `POST /v1/sessions` — multipart upload:
  - `metadata` (form field, JSON string) — see schema below
  - `file` (form field, binary) — the gzip-compressed CSV bytes

  The server verifies the bytes really are gzip, that the inner CSV's
  SHA-256 and uncompressed length match `metadata`, and rejects with 400
  otherwise. Duplicate `id` returns 409.

- `GET  /v1/sessions?user_id=<uuid>&limit=&offset=` — list metadata,
  newest first.
- `GET  /v1/sessions/{session_id}` — get one session's metadata.
- `GET  /v1/sessions/{session_id}/csv` — download the gzipped CSV. The
  response body is still gzipped (`application/gzip`); pandas reads it
  directly via `pd.read_csv(path)` when saved with a `.csv.gz` extension.
- `DELETE /v1/sessions/{session_id}` — delete one session.

`metadata` JSON shape:

```json
{
  "id": "uuid-of-session",
  "user_id": "uuid-of-device",
  "started_at": "2026-05-18T10:00:00Z",
  "duration_ms": 1800000,
  "sample_count": 61200,
  "target_hz": 34,
  "description": "walking on flat ground",
  "csv_uncompressed_bytes": 4321000,
  "csv_sha256": "<hex sha256 of the uncompressed csv bytes>"
}
```

## Flutter integration

Add to `pubspec.yaml`:

```yaml
  http: ^1.2.2
  crypto: ^3.0.5
```

Helper that compresses + uploads a session CSV from the HAR app:

```dart
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:crypto/crypto.dart';
import 'package:http/http.dart' as http;

class HarApi {
  HarApi({required this.baseUrl, required this.apiKey});

  final Uri baseUrl;
  final String apiKey;

  Future<void> upsertUser({
    required String userId,
    int? age,
    int? heightCm,
    int? weightKg,
    String? gender,
  }) async {
    final r = await http.put(
      baseUrl.resolve('/v1/users/$userId'),
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': apiKey,
      },
      body: jsonEncode({
        if (age != null) 'age': age,
        if (heightCm != null) 'height_cm': heightCm,
        if (weightKg != null) 'weight_kg': weightKg,
        if (gender != null) 'gender': gender,
      }),
    );
    if (r.statusCode >= 300) {
      throw Exception('upsertUser failed: ${r.statusCode} ${r.body}');
    }
  }

  Future<void> uploadSession({
    required String sessionId,
    required String userId,
    required DateTime startedAt,
    required int durationMs,
    required int sampleCount,
    required int targetHz,
    String? description,
    required File csvFile,
  }) async {
    final csvBytes = await csvFile.readAsBytes();
    final gz = Uint8List.fromList(gzip.encode(csvBytes));
    final sha = sha256.convert(csvBytes).toString();

    final req = http.MultipartRequest('POST', baseUrl.resolve('/v1/sessions'))
      ..headers['X-API-Key'] = apiKey
      ..fields['metadata'] = jsonEncode({
        'id': sessionId,
        'user_id': userId,
        'started_at': startedAt.toUtc().toIso8601String(),
        'duration_ms': durationMs,
        'sample_count': sampleCount,
        'target_hz': targetHz,
        'description': description,
        'csv_uncompressed_bytes': csvBytes.length,
        'csv_sha256': sha,
      })
      ..files.add(http.MultipartFile.fromBytes(
        'file',
        gz,
        filename: '$sessionId.csv.gz',
        contentType: null, // server treats it as application/gzip
      ));

    final streamed = await req.send();
    if (streamed.statusCode >= 300) {
      final body = await streamed.stream.bytesToString();
      throw Exception('uploadSession failed: ${streamed.statusCode} $body');
    }
  }
}
```

`gzip` is in `dart:io`, so no extra dependency is needed for compression
itself. Wire this into the HAR app once the planned upload-consent step is
in place (see `PROGRESS.md` → "Opt-in uploading deferred").

## Migrations

Alembic runs automatically on container start. To work with migrations
locally:

```bash
# shell into the api container or set DATABASE_URL locally
alembic revision --autogenerate -m "describe change"
alembic upgrade head
alembic downgrade -1
```

## Tests

The smoke tests (`test_auth.py`) run with a bare `pytest`. The roundtrip
tests need a Postgres instance:

```bash
docker compose up -d db
createdb -h localhost -U har har_test     # one-time
export TEST_DATABASE_URL=postgresql+asyncpg://har:har-dev-password@localhost:5432/har_test
pip install -e '.[dev]'
pytest
```

## Deploying to your server

The `docker-compose.yml` is the deployment unit. On the server:

```bash
git pull
cp .env.example .env && $EDITOR .env   # set a real API key + DB password
docker compose up -d --build
```

Put it behind a TLS reverse proxy (Caddy / nginx / Traefik) so the API key
is not sent in plaintext. The compose file binds Postgres to `127.0.0.1`
only.

## Storage sizing

At 34 Hz with 9 floats per row, a one-hour session is roughly 12 MB raw
CSV → ~1.5–2 MB after gzip. 1000 hours of recordings comes in under 2 GB
of `bytea` data — well within what Postgres handles comfortably on a
single node. If you outgrow that, the migration to filesystem-backed
storage is mechanical (add a `csv_path` column, write blobs to disk on
upload, read them on download).
