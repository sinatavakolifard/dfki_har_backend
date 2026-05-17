import gzip
import hashlib
import uuid
from datetime import datetime, timezone

import pytest

from tests.conftest import requires_db


@requires_db
@pytest.mark.asyncio
async def test_upload_list_download_delete(client, auth_headers, db_schema):
    user_id = uuid.uuid4()
    session_id = uuid.uuid4()
    csv = (
        b"timestamp_ms,accel_x,accel_y,accel_z,gyro_x,gyro_y,gyro_z,mag_x,mag_y,mag_z\n"
        b"0,0.01,0.02,9.8,0.0,0.0,0.0,20,-10,40\n"
        b"30,0.02,0.03,9.79,0.001,0.0,-0.001,20,-10,40\n"
    )
    gz = gzip.compress(csv)
    meta = {
        "id": str(session_id),
        "user_id": str(user_id),
        "started_at": datetime.now(timezone.utc).isoformat(),
        "duration_ms": 60,
        "sample_count": 2,
        "target_hz": 34,
        "description": "walking-test",
        "csv_uncompressed_bytes": len(csv),
        "csv_sha256": hashlib.sha256(csv).hexdigest(),
    }

    r = await client.post(
        "/v1/sessions",
        headers=auth_headers,
        data={"metadata": __import__("json").dumps(meta)},
        files={"file": ("session.csv.gz", gz, "application/gzip")},
    )
    assert r.status_code == 201, r.text
    assert r.json()["id"] == str(session_id)

    r = await client.get(f"/v1/sessions?user_id={user_id}", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    assert body[0]["sample_count"] == 2

    r = await client.get(f"/v1/sessions/{session_id}/csv", headers=auth_headers)
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/gzip"
    assert gzip.decompress(r.content) == csv

    r = await client.delete(f"/v1/sessions/{session_id}", headers=auth_headers)
    assert r.status_code == 204

    r = await client.get(f"/v1/sessions/{session_id}", headers=auth_headers)
    assert r.status_code == 404


@requires_db
@pytest.mark.asyncio
async def test_upload_rejects_sha_mismatch(client, auth_headers, db_schema):
    user_id = uuid.uuid4()
    session_id = uuid.uuid4()
    csv = b"timestamp_ms,accel_x\n0,0.0\n"
    gz = gzip.compress(csv)
    meta = {
        "id": str(session_id),
        "user_id": str(user_id),
        "started_at": datetime.now(timezone.utc).isoformat(),
        "duration_ms": 0,
        "sample_count": 1,
        "target_hz": 34,
        "description": None,
        "csv_uncompressed_bytes": len(csv),
        "csv_sha256": "0" * 64,  # wrong
    }
    r = await client.post(
        "/v1/sessions",
        headers=auth_headers,
        data={"metadata": __import__("json").dumps(meta)},
        files={"file": ("s.csv.gz", gz, "application/gzip")},
    )
    assert r.status_code == 400
    assert "sha256" in r.json()["detail"]
