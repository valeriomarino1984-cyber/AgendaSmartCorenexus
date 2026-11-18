"""Studi, utenti, ruoli, sessioni, token monouso, limiti di frequenza, registro attività.

Revision ID: 0002_accounts
Revises: 0001_baseline
Create Date: 2026-11-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_accounts"
down_revision: str | None = "0001_baseline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Categorie della specifica §1.1. health_related: messaggi neutri attivi di default (Decisione 11).
BUSINESS_TYPES = [
    ("fisioterapista", "Fisioterapista", True),
    ("nutrizionista", "Nutrizionista / Dietista", True),
    ("biologo_nutrizionista", "Biologo nutrizionista", True),
    ("psicologo", "Psicologo", True),
    ("psicoterapeuta", "Psicoterapeuta", True),
    ("osteopata", "Osteopata", True),
    ("massoterapista", "Massoterapista", True),
    ("personal_trainer", "Personal trainer", False),
    ("estetista", "Estetista", False),
    ("centro_benessere", "Centro benessere", False),
    ("consulente", "Consulente", False),
    ("studio_professionale", "Studio professionale", False),
    ("poliambulatorio", "Poliambulatorio / centro multidisciplinare", True),
    ("altro", "Altra attività", False),
]


def upgrade() -> None:
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=True),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(length=60), nullable=False),
        sa.Column("resource", sa.String(length=60), nullable=True),
        sa.Column("resource_id", sa.String(length=64), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("ip", sa.String(length=45), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_logs")),
    )
    op.create_index(
        "ix_audit_logs_tenant_created", "audit_logs", ["tenant_id", "created_at"], unique=False
    )
    op.create_table(
        "business_types",
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("label", sa.String(length=80), nullable=False),
        sa.Column("health_related", sa.Boolean(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("code", name=op.f("pk_business_types")),
    )
    business_types = sa.table(
        "business_types",
        sa.column("code", sa.String),
        sa.column("label", sa.String),
        sa.column("health_related", sa.Boolean),
        sa.column("sort_order", sa.Integer),
        sa.column("active", sa.Boolean),
    )
    op.bulk_insert(
        business_types,
        [
            {"code": c, "label": lbl, "health_related": h, "sort_order": i, "active": True}
            for i, (c, lbl, h) in enumerate(BUSINESS_TYPES)
        ],
    )
    op.create_table(
        "rate_limit_events",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_rate_limit_events")),
    )
    op.create_index(
        "ix_rate_limit_events_key_created",
        "rate_limit_events",
        ["key_hash", "created_at"],
        unique=False,
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("password_hash", sa.String(length=200), nullable=True),
        sa.Column("full_name", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("email_verified_at", sa.DateTime(), nullable=True),
        sa.Column("is_platform_admin", sa.Boolean(), nullable=False),
        sa.Column("last_login_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending','active','disabled')", name=op.f("ck_users_status_valido")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    )
    op.create_table(
        "tenants",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("slug", sa.String(length=60), nullable=False),
        sa.Column("business_type", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("trial_ends_at", sa.DateTime(), nullable=True),
        sa.Column("timezone", sa.String(length=40), nullable=False),
        sa.Column("neutral_messaging", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "status IN ('trial','active','suspended','cancelled')",
            name=op.f("ck_tenants_status_valido"),
        ),
        sa.ForeignKeyConstraint(
            ["business_type"],
            ["business_types.code"],
            name=op.f("fk_tenants_business_type_business_types"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tenants")),
        sa.UniqueConstraint("slug", name=op.f("uq_tenants_slug")),
    )
    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("active_tenant_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("ip", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(
            ["active_tenant_id"],
            ["tenants.id"],
            name=op.f("fk_auth_sessions_active_tenant_id_tenants"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_auth_sessions_user_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_auth_sessions")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_auth_sessions_token_hash")),
    )
    op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"], unique=False)
    op.create_table(
        "tenant_settings",
        sa.Column("contact_email", sa.String(length=254), nullable=True),
        sa.Column("contact_phone", sa.String(length=30), nullable=True),
        sa.Column("address", sa.String(length=200), nullable=True),
        sa.Column("cancellation_min_hours", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "cancellation_min_hours BETWEEN 0 AND 168",
            name=op.f("ck_tenant_settings_preavviso_valido"),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name=op.f("fk_tenant_settings_tenant_id_tenants")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tenant_settings")),
        sa.UniqueConstraint("tenant_id", "id", name=op.f("uq_tenant_settings_tenant_id_id")),
        sa.UniqueConstraint("tenant_id", name=op.f("uq_tenant_settings_tenant_id")),
    )
    op.create_index(
        op.f("ix_tenant_settings_tenant_id"), "tenant_settings", ["tenant_id"], unique=False
    )
    op.create_table(
        "tenant_users",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("permissions", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "role IN ('owner','professional','secretary')",
            name=op.f("ck_tenant_users_ruolo_valido"),
        ),
        sa.CheckConstraint(
            "status IN ('active','disabled')", name=op.f("ck_tenant_users_status_valido")
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name=op.f("fk_tenant_users_tenant_id_tenants")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_tenant_users_user_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tenant_users")),
        sa.UniqueConstraint("tenant_id", "id", name=op.f("uq_tenant_users_tenant_id_id")),
        sa.UniqueConstraint("tenant_id", "user_id", name=op.f("uq_tenant_users_tenant_id_user_id")),
    )
    op.create_index(op.f("ix_tenant_users_tenant_id"), "tenant_users", ["tenant_id"], unique=False)
    op.create_table(
        "user_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("purpose", sa.String(length=20), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("invite_tenant_id", sa.Uuid(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "purpose IN ('verify_email','reset_password','invite')",
            name=op.f("ck_user_tokens_scopo_valido"),
        ),
        sa.ForeignKeyConstraint(
            ["invite_tenant_id"],
            ["tenants.id"],
            name=op.f("fk_user_tokens_invite_tenant_id_tenants"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_user_tokens_user_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_tokens")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_user_tokens_token_hash")),
    )
    op.create_index(
        "ix_user_tokens_user_purpose", "user_tokens", ["user_id", "purpose"], unique=False
    )


def downgrade() -> None:
    # In MySQL gli indici usati dalle FK non si eliminano da soli: DROP TABLE li rimuove.
    op.drop_table("user_tokens")
    op.drop_table("tenant_users")
    op.drop_table("tenant_settings")
    op.drop_table("auth_sessions")
    op.drop_table("tenants")
    op.drop_table("users")
    op.drop_table("rate_limit_events")
    op.drop_table("business_types")
    op.drop_table("audit_logs")
