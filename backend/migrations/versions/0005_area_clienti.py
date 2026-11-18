"""Area clienti: link di accesso via email e sessioni dei clienti (tabelle di piattaforma).

Revision ID: 0005_area_clienti
Revises: 0004_agenda
Create Date: 2026-11-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_area_clienti"
down_revision: str | None = "0004_agenda"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "client_login_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_client_login_tokens")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_client_login_tokens_token_hash")),
    )
    op.create_index("ix_client_login_tokens_email", "client_login_tokens", ["email"], unique=False)
    op.create_table(
        "client_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("ip", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_client_sessions")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_client_sessions_token_hash")),
    )
    op.create_index("ix_client_sessions_email", "client_sessions", ["email"], unique=False)


def downgrade() -> None:
    op.drop_table("client_sessions")
    op.drop_table("client_login_tokens")
