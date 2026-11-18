"""Area piattaforma CoreNexus: personale con verifica in due passaggi, inviti e sessioni.

Revision ID: 0006_piattaforma
Revises: 0005_area_clienti
Create Date: 2026-11-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_piattaforma"
down_revision: str | None = "0005_area_clienti"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "platform_staff",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("full_name", sa.String(length=120), nullable=False),
        sa.Column("password_hash", sa.String(length=200), nullable=True),
        sa.Column("totp_salt", sa.String(length=64), nullable=False),
        sa.Column("totp_confirmed_at", sa.DateTime(), nullable=True),
        sa.Column("last_totp_step", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("last_login_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "status IN ('invited','active','disabled')",
            name=op.f("ck_platform_staff_status_valido"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_platform_staff")),
        sa.UniqueConstraint("email", name=op.f("uq_platform_staff_email")),
    )
    op.create_table(
        "platform_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("staff_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("mfa_passed_at", sa.DateTime(), nullable=True),
        sa.Column("mfa_failures", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("ip", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(
            ["staff_id"],
            ["platform_staff.id"],
            name=op.f("fk_platform_sessions_staff_id_platform_staff"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_platform_sessions")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_platform_sessions_token_hash")),
    )
    op.create_index("ix_platform_sessions_staff", "platform_sessions", ["staff_id"], unique=False)
    op.create_table(
        "platform_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("staff_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["staff_id"],
            ["platform_staff.id"],
            name=op.f("fk_platform_tokens_staff_id_platform_staff"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_platform_tokens")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_platform_tokens_token_hash")),
    )
    op.create_index("ix_platform_tokens_staff", "platform_tokens", ["staff_id"], unique=False)


def downgrade() -> None:
    op.drop_table("platform_tokens")
    op.drop_table("platform_sessions")
    op.drop_table("platform_staff")
