import gzip
import hashlib
import json
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile, status
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_api_key
from app.config import Settings, get_settings
from app.db import get_session
from app.models import Session as SessionModel
from app.models import User
from app.schemas import SessionMetadataIn, SessionOut

router = APIRouter(prefix="/v1/sessions", tags=["sessions"], dependencies=[Depends(require_api_key)])


@router.post("", response_model=SessionOut, status_code=status.HTTP_201_CREATED)
async def upload_session(
    metadata: str = Form(..., description="JSON-encoded SessionMetadataIn"),
    file: UploadFile = File(..., description="gzip-compressed CSV bytes"),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> SessionModel:
    try:
        meta = SessionMetadataIn.model_validate_json(metadata)
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.errors()) from exc
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="metadata is not valid JSON") from exc

    blob = await file.read()
    if len(blob) == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="empty upload")
    if len(blob) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"upload exceeds {settings.max_upload_bytes} bytes",
        )

    # Validate the bytes really are gzip and that the inner CSV matches the
    # claimed sha256 + uncompressed length. We never trust client-side numbers
    # without checking.
    try:
        decompressed = gzip.decompress(blob)
    except (OSError, EOFError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="payload is not valid gzip") from exc

    if len(decompressed) != meta.csv_uncompressed_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="csv_uncompressed_bytes does not match decoded payload",
        )
    actual_sha = hashlib.sha256(decompressed).hexdigest()
    if actual_sha != meta.csv_sha256:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="csv_sha256 does not match decoded payload",
        )

    user = await session.get(User, meta.user_id)
    if user is None:
        # First-time upload from a client that didn't call PUT /v1/users first:
        # auto-create a profile-less row so the FK holds.
        user = User(id=meta.user_id)
        session.add(user)
        await session.flush()

    existing = await session.get(SessionModel, meta.id)
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="session already uploaded")

    row = SessionModel(
        id=meta.id,
        user_id=meta.user_id,
        started_at=meta.started_at,
        duration_ms=meta.duration_ms,
        sample_count=meta.sample_count,
        target_hz=meta.target_hz,
        description=meta.description,
        csv_compression="gzip",
        csv_uncompressed_bytes=meta.csv_uncompressed_bytes,
        csv_sha256=meta.csv_sha256,
        csv_gz=blob,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


@router.get("", response_model=list[SessionOut])
async def list_sessions(
    user_id: UUID = Query(...),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> list[SessionModel]:
    stmt = (
        select(SessionModel)
        .where(SessionModel.user_id == user_id)
        .order_by(SessionModel.started_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


@router.get("/{session_id}", response_model=SessionOut)
async def get_session_metadata(
    session_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> SessionModel:
    row = await session.get(SessionModel, session_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="session not found")
    return row


@router.get("/{session_id}/csv")
async def download_session_csv(
    session_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> Response:
    row = await session.get(SessionModel, session_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="session not found")
    # Serve the bytes still gzipped — pandas.read_csv understands .csv.gz, and
    # we save bandwidth. Clients that want decompressed bytes can gunzip on
    # arrival.
    return Response(
        content=row.csv_gz,
        media_type="application/gzip",
        headers={
            "Content-Disposition": f'attachment; filename="{session_id}.csv.gz"',
            "X-CSV-SHA256": row.csv_sha256,
            "X-CSV-Uncompressed-Bytes": str(row.csv_uncompressed_bytes),
        },
    )


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> Response:
    row = await session.get(SessionModel, session_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="session not found")
    await session.delete(row)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
