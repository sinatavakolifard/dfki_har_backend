"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-05-18

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("age", sa.Integer(), nullable=True),
        sa.Column("height_cm", sa.Integer(), nullable=True),
        sa.Column("weight_kg", sa.Integer(), nullable=True),
        sa.Column("gender", sa.String(length=32), nullable=True),
    )

    op.create_table(
        "sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_ms", sa.BigInteger(), nullable=False),
        sa.Column("sample_count", sa.Integer(), nullable=False),
        sa.Column("target_hz", sa.Integer(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column(
            "csv_compression",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'gzip'"),
        ),
        sa.Column("csv_uncompressed_bytes", sa.BigInteger(), nullable=False),
        sa.Column("csv_sha256", sa.String(length=64), nullable=False),
        sa.Column("csv_gz", sa.LargeBinary(), nullable=False),
        sa.Column(
            "uploaded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_sessions_user_started", "sessions", ["user_id", "started_at"])


def downgrade() -> None:
    op.drop_index("ix_sessions_user_started", table_name="sessions")
    op.drop_table("sessions")
    op.drop_table("users")
