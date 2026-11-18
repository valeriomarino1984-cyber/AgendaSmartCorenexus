"""Notifiche email ai clienti: coda dei messaggi e impostazioni dello studio (conferme, promemoria).

Revision ID: 0007_notifiche
Revises: 0006_piattaforma
Create Date: 2026-11-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_notifiche"
down_revision: str | None = "0006_piattaforma"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "notification_jobs",
        sa.Column("appointment_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("channel", sa.String(length=10), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(), nullable=False),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(length=60), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "channel IN ('email','whatsapp')", name=op.f("ck_notification_jobs_canale_valido")
        ),
        sa.CheckConstraint(
            "kind IN ('confirmation','reminder','rescheduled','cancelled')",
            name=op.f("ck_notification_jobs_tipo_valido"),
        ),
        sa.CheckConstraint(
            "status IN ('pending','sending','sent','failed','skipped','cancelled')",
            name=op.f("ck_notification_jobs_stato_valido"),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "appointment_id"],
            ["appointments.tenant_id", "appointments.id"],
            name=op.f("fk_notification_jobs_tenant_id_appointment_id_appointments"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notification_jobs")),
        sa.UniqueConstraint("tenant_id", "id", name=op.f("uq_notification_jobs_tenant_id_id")),
    )
    op.create_index(
        "ix_notification_jobs_appointment",
        "notification_jobs",
        ["tenant_id", "appointment_id"],
        unique=False,
    )
    op.create_index(
        "ix_notification_jobs_due", "notification_jobs", ["status", "scheduled_at"], unique=False
    )
    op.create_index(
        op.f("ix_notification_jobs_tenant_id"), "notification_jobs", ["tenant_id"], unique=False
    )
    # Studi esistenti: conferme attive e promemoria 24 ore prima (come i nuovi).
    op.add_column(
        "tenant_settings",
        sa.Column("email_confirmations", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "tenant_settings",
        sa.Column("reminder_hours", sa.Integer(), nullable=False, server_default="24"),
    )
    op.create_check_constraint(
        op.f("ck_tenant_settings_promemoria_valido"),
        "tenant_settings",
        "reminder_hours BETWEEN 0 AND 168",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("ck_tenant_settings_promemoria_valido"), "tenant_settings", type_="check"
    )
    op.drop_column("tenant_settings", "reminder_hours")
    op.drop_column("tenant_settings", "email_confirmations")
    op.drop_table("notification_jobs")
