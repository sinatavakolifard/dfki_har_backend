from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_api_key
from app.db import get_session
from app.models import User
from app.schemas import UserIn, UserOut

router = APIRouter(prefix="/v1/users", tags=["users"], dependencies=[Depends(require_api_key)])


@router.put("/{user_id}", response_model=UserOut)
async def upsert_user(
    user_id: UUID,
    payload: UserIn,
    session: AsyncSession = Depends(get_session),
) -> User:
    user = await session.get(User, user_id)
    if user is None:
        user = User(id=user_id, **payload.model_dump())
        session.add(user)
    else:
        for field, value in payload.model_dump().items():
            setattr(user, field, value)
        user.updated_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(user)
    return user


@router.get("/{user_id}", response_model=UserOut)
async def get_user(
    user_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> User:
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")
    return user
