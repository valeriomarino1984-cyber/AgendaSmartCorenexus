"""Prenotazione online: impostazioni dello studio e chiave anti-doppione sugli appuntamenti.

Revision ID: 0008_prenotazione_online
Revises: 0007_notifiche
Create Date: 2026-11-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_prenotazione_online"
down_revision: str | None = "0007_notifiche"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("appointments", sa.Column("booking_key", sa.String(length=64), nullable=True))
    op.create_unique_constraint(
        op.f("uq_appointments_tenant_id_booking_key"), "appointments", ["tenant_id", "booking_key"]
    )
    # Studi esistenti: pagina di prenotazione spenta, la accendono loro.
    for name, col, default in [
        ("online_booking_enabled", sa.Boolean(), sa.false()),
        ("online_booking_days_ahead", sa.Integer(), "60"),
        ("online_booking_min_notice_hours", sa.Integer(), "2"),
        ("online_booking_requires_confirmation", sa.Boolean(), sa.false()),
    ]:
        op.add_column(
            "tenant_settings", sa.Column(name, col, nullable=False, server_default=default)
        )
    op.create_check_constraint(
        op.f("ck_tenant_settings_giorni_prenotabili"),
        "tenant_settings",
        "online_booking_days_ahead BETWEEN 1 AND 365",
    )
    op.create_check_constraint(
        op.f("ck_tenant_settings_preavviso_online"),
        "tenant_settings",
        "online_booking_min_notice_hours BETWEEN 0 AND 168",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("ck_tenant_settings_preavviso_online"), "tenant_settings", type_="check"
    )
    op.drop_constraint(
        op.f("ck_tenant_settings_giorni_prenotabili"), "tenant_settings", type_="check"
    )
    for name in (
        "online_booking_requires_confirmation",
        "online_booking_min_notice_hours",
        "online_booking_days_ahead",
        "online_booking_enabled",
    ):
        op.drop_column("tenant_settings", name)
    op.drop_constraint(
        op.f("uq_appointments_tenant_id_booking_key"), "appointments", type_="unique"
    )
    op.drop_column("appointments", "booking_key")
