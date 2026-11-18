"""Baseline: verifica dei requisiti del database (MariaDB/MySQL, InnoDB, utf8mb4).

Revision ID: 0001_baseline
Revises:
Create Date: 2026-11-17
"""

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

revision: str = "0001_baseline"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    charset = conn.execute(text("SELECT @@character_set_database")).scalar()
    if charset != "utf8mb4":
        raise RuntimeError(
            f"Il database usa il set di caratteri '{charset}': serve utf8mb4 "
            "(cPanel → phpMyAdmin → Operazioni → Codifica caratteri → utf8mb4_unicode_ci)"
        )
    engine = conn.execute(text("SELECT @@default_storage_engine")).scalar()
    if str(engine).upper() != "INNODB":
        raise RuntimeError(f"Motore di default '{engine}': serve InnoDB (transazioni e FK)")


def downgrade() -> None:
    pass
