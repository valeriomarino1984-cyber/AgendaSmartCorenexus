"""Sedi, professionisti, prestazioni (con modalità in studio/online) e clienti con consensi.

Revision ID: 0003_catalog
Revises: 0002_accounts
Create Date: 2026-11-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_catalog"
down_revision: str | None = "0002_accounts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "locations",
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("address", sa.String(length=200), nullable=True),
        sa.Column("timezone", sa.String(length=40), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name=op.f("fk_locations_tenant_id_tenants")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_locations")),
        sa.UniqueConstraint("tenant_id", "id", name=op.f("uq_locations_tenant_id_id")),
    )
    op.create_index(op.f("ix_locations_tenant_id"), "locations", ["tenant_id"], unique=False)
    op.create_table(
        "professionals",
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("specialization", sa.String(length=120), nullable=True),
        sa.Column("color", sa.String(length=7), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("public_booking", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "status IN ('active','inactive')", name=op.f("ck_professionals_status_valido")
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name=op.f("fk_professionals_tenant_id_tenants")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_professionals_user_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_professionals")),
        sa.UniqueConstraint("tenant_id", "id", name=op.f("uq_professionals_tenant_id_id")),
        sa.UniqueConstraint(
            "tenant_id", "user_id", name=op.f("uq_professionals_tenant_id_user_id")
        ),
    )
    op.create_index(
        op.f("ix_professionals_tenant_id"), "professionals", ["tenant_id"], unique=False
    )
    op.create_table(
        "services",
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("preparation_minutes", sa.Integer(), nullable=False),
        sa.Column("price", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("color", sa.String(length=7), nullable=False),
        sa.Column("mode", sa.String(length=20), nullable=False),
        sa.Column("public_visible", sa.Boolean(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "mode IN ('in_person','online','both')", name=op.f("ck_services_modalita_valida")
        ),
        sa.CheckConstraint(
            "duration_minutes BETWEEN 5 AND 600", name=op.f("ck_services_durata_valida")
        ),
        sa.CheckConstraint(
            "preparation_minutes BETWEEN 0 AND 240", name=op.f("ck_services_preparazione_valida")
        ),
        sa.CheckConstraint("price IS NULL OR price >= 0", name=op.f("ck_services_prezzo_valido")),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name=op.f("fk_services_tenant_id_tenants")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_services")),
        sa.UniqueConstraint("tenant_id", "id", name=op.f("uq_services_tenant_id_id")),
    )
    op.create_index(op.f("ix_services_tenant_id"), "services", ["tenant_id"], unique=False)
    op.create_table(
        "clients",
        sa.Column("first_name", sa.String(length=80), nullable=False),
        sa.Column("last_name", sa.String(length=80), nullable=False),
        sa.Column("phone_e164", sa.String(length=16), nullable=True),
        sa.Column("email", sa.String(length=254), nullable=True),
        sa.Column("birth_date", sa.Date(), nullable=True),
        sa.Column("reference_professional_id", sa.Uuid(), nullable=True),
        sa.Column("admin_notes", sa.Text(), nullable=True),
        sa.Column("preferred_channel", sa.String(length=20), nullable=True),
        sa.Column("whatsapp_consent", sa.Boolean(), nullable=False),
        sa.Column("whatsapp_consent_at", sa.DateTime(), nullable=True),
        sa.Column("email_consent", sa.Boolean(), nullable=False),
        sa.Column("email_consent_at", sa.DateTime(), nullable=True),
        sa.Column("marketing_consent", sa.Boolean(), nullable=False),
        sa.Column("marketing_consent_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "preferred_channel IS NULL OR preferred_channel IN ('whatsapp','email','none')",
            name=op.f("ck_clients_canale_valido"),
        ),
        sa.CheckConstraint(
            "status IN ('active','archived')", name=op.f("ck_clients_status_valido")
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "reference_professional_id"],
            ["professionals.tenant_id", "professionals.id"],
            name=op.f("fk_clients_tenant_id_reference_professional_id_professionals"),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name=op.f("fk_clients_tenant_id_tenants")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_clients")),
        sa.UniqueConstraint("tenant_id", "id", name=op.f("uq_clients_tenant_id_id")),
    )
    op.create_index("ix_clients_tenant_email", "clients", ["tenant_id", "email"], unique=False)
    op.create_index(op.f("ix_clients_tenant_id"), "clients", ["tenant_id"], unique=False)
    op.create_index(
        "ix_clients_tenant_name", "clients", ["tenant_id", "last_name", "first_name"], unique=False
    )
    op.create_index("ix_clients_tenant_phone", "clients", ["tenant_id", "phone_e164"], unique=False)
    op.create_table(
        "service_professionals",
        sa.Column("service_id", sa.Uuid(), nullable=False),
        sa.Column("professional_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id", "professional_id"],
            ["professionals.tenant_id", "professionals.id"],
            name=op.f("fk_service_professionals_tenant_id_professional_id_professionals"),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "service_id"],
            ["services.tenant_id", "services.id"],
            name=op.f("fk_service_professionals_tenant_id_service_id_services"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_service_professionals")),
        sa.UniqueConstraint(
            "service_id",
            "professional_id",
            name=op.f("uq_service_professionals_service_id_professional_id"),
        ),
        sa.UniqueConstraint("tenant_id", "id", name=op.f("uq_service_professionals_tenant_id_id")),
    )
    op.create_index(
        op.f("ix_service_professionals_tenant_id"),
        "service_professionals",
        ["tenant_id"],
        unique=False,
    )
    op.create_table(
        "client_consent_events",
        sa.Column("client_id", sa.Uuid(), nullable=False),
        sa.Column("channel", sa.String(length=20), nullable=False),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("source", sa.String(length=30), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "action IN ('granted','revoked')", name=op.f("ck_client_consent_events_azione_valida")
        ),
        sa.CheckConstraint(
            "channel IN ('whatsapp','email','marketing')",
            name=op.f("ck_client_consent_events_canale_valido"),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "client_id"],
            ["clients.tenant_id", "clients.id"],
            name=op.f("fk_client_consent_events_tenant_id_client_id_clients"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_client_consent_events")),
        sa.UniqueConstraint("tenant_id", "id", name=op.f("uq_client_consent_events_tenant_id_id")),
    )
    op.create_index(
        op.f("ix_client_consent_events_tenant_id"),
        "client_consent_events",
        ["tenant_id"],
        unique=False,
    )

    # Studi già esistenti: sede principale e scheda professionista per titolari e professionisti.
    # Gli id sono UUID senza trattini (formato del tipo Uuid di SQLAlchemy su MySQL/MariaDB).
    op.execute(
        """
        INSERT INTO locations (id, tenant_id, created_at, name, timezone, is_default, active)
        SELECT REPLACE(UUID(), '-', ''), t.id, UTC_TIMESTAMP(), 'Sede principale', t.timezone, 1, 1
        FROM tenants t
        WHERE NOT EXISTS (SELECT 1 FROM locations l WHERE l.tenant_id = t.id)
        """
    )
    op.execute(
        """
        INSERT INTO professionals
            (id, tenant_id, created_at, user_id, name, color, status, public_booking)
        SELECT REPLACE(UUID(), '-', ''), m.tenant_id, UTC_TIMESTAMP(), m.user_id, u.full_name,
               '#0071e3', 'active', 1
        FROM tenant_users m JOIN users u ON u.id = m.user_id
        WHERE m.role IN ('owner', 'professional') AND m.status = 'active'
          AND NOT EXISTS (
              SELECT 1 FROM professionals p
              WHERE p.tenant_id = m.tenant_id AND p.user_id = m.user_id
          )
        """
    )


def downgrade() -> None:
    # In MySQL gli indici usati dalle FK non si eliminano da soli: DROP TABLE li rimuove.
    op.drop_table("client_consent_events")
    op.drop_table("service_professionals")
    op.drop_table("clients")
    op.drop_table("services")
    op.drop_table("professionals")
    op.drop_table("locations")
