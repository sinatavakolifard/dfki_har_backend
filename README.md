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

The sibling [`dfki_human_activity_recognition`](../dfki_human_activity_recognition)
app already ships a `HarApi` client at
`lib/services/har_api.dart` (uses `http` + `crypto`; compresses with
`dart:io`'s `gzip` and uploads multipart). End-to-end wiring on the app
side:

1. **Set the server URL + key.** In the app, open Preferences → *Backend
   uploads* and fill in:
   - **Server base URL** — e.g. `http://10.0.2.2:8000` for the Android
     emulator, `http://localhost:8000` for the iOS simulator, or the LAN /
     public URL of the deployed API.
   - **API key** — the `HAR_API_KEY` value from this repo's `.env`.

   Tap **Test connection** to verify; on success the app stores both
   values.

2. **Opt in to uploads.** Flip the *Upload recordings* switch. From then
   on, every Stop sends the gzipped CSV; failures keep the local CSV so the
   user can retry from the Sessions list (popup menu → *Upload to
   backend*).

3. **Re-upload / migrate older recordings.** The same popup menu has an
   *Upload to backend* action per session.

Cleartext HTTP is fine for local development, but Android release builds
block it by default. For anything reachable from another host, put the API
behind TLS (see *Deploying*) — `X-API-Key` is transmitted in plaintext
otherwise.

## Inspecting stored data

The compose file binds Postgres to `127.0.0.1:5432` (creds from
`.env` / `.env.example` — default `har` / `har-dev-password`).

```bash
docker compose exec db psql -U har -d har
```

Once in psql:

```sql
\dt                                   -- users, sessions, alembic_version
SELECT id, age, gender, updated_at FROM users;

-- skip csv_gz, it is the raw gzipped blob
SELECT id, user_id, started_at, sample_count, csv_uncompressed_bytes,
       uploaded_at
  FROM sessions
  ORDER BY uploaded_at DESC
  LIMIT 20;
```

Or hit the API directly:

```bash
KEY=$(grep ^HAR_API_KEY .env | cut -d= -f2)
curl -s -H "X-API-Key: $KEY" \
  "http://localhost:8000/v1/sessions?user_id=<uuid>&limit=50" | jq
```

OpenAPI / Swagger UI lives at `http://localhost:8000/docs` — click
*Authorize* once and you can browse interactively.

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
