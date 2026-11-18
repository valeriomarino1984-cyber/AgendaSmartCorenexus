"""Agenda: disponibilità settimanali, eccezioni, appuntamenti (anche online) e loro storico.

Revision ID: 0004_agenda
Revises: 0003_catalog
Create Date: 2026-11-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision: str = "0004_agenda"
down_revision: str | None = "0003_catalog"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "availability",
        sa.Column("professional_id", sa.Uuid(), nullable=False),
        sa.Column("location_id", sa.Uuid(), nullable=False),
        sa.Column("weekday", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=True),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("end_time > start_time", name=op.f("ck_availability_orario_valido")),
        sa.CheckConstraint(
            "valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from",
            name=op.f("ck_availability_periodo_valido"),
        ),
        sa.CheckConstraint("weekday BETWEEN 1 AND 7", name=op.f("ck_availability_giorno_valido")),
        sa.ForeignKeyConstraint(
            ["tenant_id", "location_id"],
            ["locations.tenant_id", "locations.id"],
            name=op.f("fk_availability_tenant_id_location_id_locations"),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "professional_id"],
            ["professionals.tenant_id", "professionals.id"],
            name=op.f("fk_availability_tenant_id_professional_id_professionals"),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name=op.f("fk_availability_tenant_id_tenants")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_availability")),
        sa.UniqueConstraint("tenant_id", "id", name=op.f("uq_availability_tenant_id_id")),
    )
    op.create_index(op.f("ix_availability_tenant_id"), "availability", ["tenant_id"], unique=False)
    op.create_index(
        "ix_availability_tenant_prof",
        "availability",
        ["tenant_id", "professional_id", "weekday"],
        unique=False,
    )
    op.create_table(
        "availability_exceptions",
        sa.Column("professional_id", sa.Uuid(), nullable=True),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("start_at", sa.DateTime(), nullable=False),
        sa.Column("end_at", sa.DateTime(), nullable=False),
        sa.Column("reason", sa.String(length=200), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "(kind = 'closure') = (professional_id IS NULL)",
            name=op.f("ck_availability_exceptions_chiusura_di_studio"),
        ),
        sa.CheckConstraint(
            "kind IN ('vacation','unavailable','closure','extra')",
            name=op.f("ck_availability_exceptions_tipo_valido"),
        ),
        sa.CheckConstraint(
            "end_at > start_at", name=op.f("ck_availability_exceptions_periodo_valido")
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "professional_id"],
            ["professionals.tenant_id", "professionals.id"],
            name=op.f("fk_availability_exceptions_tenant_id_professional_id_professionals"),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name=op.f("fk_availability_exceptions_tenant_id_tenants")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_availability_exceptions")),
        sa.UniqueConstraint(
            "tenant_id", "id", name=op.f("uq_availability_exceptions_tenant_id_id")
        ),
    )
    op.create_index(
        "ix_availability_exceptions_period",
        "availability_exceptions",
        ["tenant_id", "start_at", "end_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_availability_exceptions_tenant_id"),
        "availability_exceptions",
        ["tenant_id"],
        unique=False,
    )
    op.create_table(
        "appointments",
        sa.Column("public_code", sa.String(length=12), nullable=False),
        sa.Column("client_id", sa.Uuid(), nullable=False),
        sa.Column("professional_id", sa.Uuid(), nullable=False),
        sa.Column("service_id", sa.Uuid(), nullable=False),
        sa.Column("location_id", sa.Uuid(), nullable=False),
        sa.Column("start_at", sa.DateTime(), nullable=False),
        sa.Column("end_at", sa.DateTime(), nullable=False),
        sa.Column("preparation_minutes", sa.Integer(), nullable=False),
        sa.Column("buffer_end_at", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("is_online", sa.Boolean(), nullable=False),
        sa.Column("video_url", sa.String(length=300), nullable=True),
        sa.Column("price", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("cancellation_reason", sa.String(length=300), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "source IN ('staff','public_booking','waitlist','recurring')",
            name=op.f("ck_appointments_origine_valida"),
        ),
        sa.CheckConstraint(
            "status IN ('pending','confirmed','cancelled_by_client','cancelled_by_staff',"
            "'completed','no_show')",
            name=op.f("ck_appointments_stato_valido"),
        ),
        sa.CheckConstraint(
            "NOT is_online OR video_url IS NOT NULL", name=op.f("ck_appointments_link_video")
        ),
        sa.CheckConstraint(
            "buffer_end_at >= end_at", name=op.f("ck_appointments_preparazione_valida")
        ),
        sa.CheckConstraint("end_at > start_at", name=op.f("ck_appointments_orario_valido")),
        sa.CheckConstraint(
            "price IS NULL OR price >= 0", name=op.f("ck_appointments_prezzo_valido")
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name=op.f("fk_appointments_created_by_users")
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "client_id"],
            ["clients.tenant_id", "clients.id"],
            name=op.f("fk_appointments_tenant_id_client_id_clients"),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "location_id"],
            ["locations.tenant_id", "locations.id"],
            name=op.f("fk_appointments_tenant_id_location_id_locations"),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "professional_id"],
            ["professionals.tenant_id", "professionals.id"],
            name=op.f("fk_appointments_tenant_id_professional_id_professionals"),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "service_id"],
            ["services.tenant_id", "services.id"],
            name=op.f("fk_appointments_tenant_id_service_id_services"),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name=op.f("fk_appointments_tenant_id_tenants")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_appointments")),
        sa.UniqueConstraint("tenant_id", "id", name=op.f("uq_appointments_tenant_id_id")),
        sa.UniqueConstraint(
            "tenant_id", "public_code", name=op.f("uq_appointments_tenant_id_public_code")
        ),
    )
    op.create_index(
        "ix_appointments_client_start",
        "appointments",
        ["tenant_id", "client_id", "start_at"],
        unique=False,
    )
    op.create_index(
        "ix_appointments_prof_start",
        "appointments",
        ["tenant_id", "professional_id", "start_at"],
        unique=False,
    )
    op.create_index(
        "ix_appointments_start", "appointments", ["tenant_id", "start_at"], unique=False
    )
    op.create_index(op.f("ix_appointments_tenant_id"), "appointments", ["tenant_id"], unique=False)
    op.create_table(
        "appointment_events",
        sa.Column("appointment_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=30), nullable=False),
        sa.Column("actor_type", sa.String(length=10), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("previous_value", sa.JSON(), nullable=True),
        sa.Column("new_value", sa.JSON(), nullable=True),
        sa.Column(
            "occurred_at",
            sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql", "mariadb"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "actor_type IN ('staff','client','system')",
            name=op.f("ck_appointment_events_attore_valido"),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "appointment_id"],
            ["appointments.tenant_id", "appointments.id"],
            name=op.f("fk_appointment_events_tenant_id_appointment_id_appointments"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_appointment_events")),
        sa.UniqueConstraint("tenant_id", "id", name=op.f("uq_appointment_events_tenant_id_id")),
    )
    op.create_index(
        op.f("ix_appointment_events_tenant_id"), "appointment_events", ["tenant_id"], unique=False
    )


def downgrade() -> None:
    # DROP TABLE rimuove anche gli indici (in MySQL quelli usati dalle FK non si eliminano a parte).
    op.drop_table("appointment_events")
    op.drop_table("appointments")
    op.drop_table("availability_exceptions")
    op.drop_table("availability")
