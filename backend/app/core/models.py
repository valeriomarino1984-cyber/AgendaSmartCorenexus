"""Base dei modelli ORM e convenzioni comuni (MySQL/MariaDB, InnoDB, utf8mb4)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, MetaData, Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Nomi dei vincoli deterministici: le migrazioni Alembic restano stabili tra ambienti.
NAMING = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


def utcnow() -> datetime:
    """MySQL DATETIME non conserva il fuso: nel database si salva sempre UTC."""
    return datetime.now(UTC).replace(tzinfo=None)


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING)


class TenantScoped:
    """Mixin delle tabelle di uno studio.

    Le sessioni ORM filtrano automaticamente per `tenant_id` e rifiutano scritture verso
    un altro tenant (vedi app/core/tenancy.py). Ogni tabella deve anche avere un vincolo
    UNIQUE (tenant_id, id), usato dalle chiavi esterne composite verso le altre tabelle
    dello stesso tenant: il controllo è in app/core/schema_checks.py.
    """

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
