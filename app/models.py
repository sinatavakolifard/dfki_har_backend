from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, LargeBinary, String, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))

    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height_cm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    weight_kg: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gender: Mapped[str | None] = mapped_column(String(32), nullable=True)

    sessions: Mapped[list["Session"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_ms: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False)
    target_hz: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)

    csv_compression: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'gzip'"))
    csv_uncompressed_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    csv_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    csv_gz: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)

    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))

    user: Mapped[User] = relationship(back_populates="sessions")

    __table_args__ = (
        Index("ix_sessions_user_started", "user_id", "started_at"),
    )
