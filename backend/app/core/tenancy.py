"""Isolamento tra studi a livello ORM (MySQL/MariaDB non ha la Row Level Security).

Tre barriere, tutte attive:
1. Ogni SELECT/UPDATE/DELETE ORM su un modello `TenantScoped` riceve in automatico
   `WHERE tenant_id = <tenant della sessione>`.
2. Prima di ogni flush si verifica che i record nuovi o modificati appartengano al tenant
   della sessione (il tenant_id mancante viene impostato, uno diverso è un errore).
3. Senza contesto tenant, qualsiasi accesso ORM a un modello `TenantScoped` è rifiutato
   (fail-closed), anziché restituire dati di tutti gli studi.

Nel database restano le chiavi esterne composite (tenant_id, id), che impediscono di
collegare oggetti di studi diversi anche in caso di errore nel codice.
Il SQL testuale (`text()`) non passa da questi controlli: è vietato sulle tabelle tenant.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import Table, event
from sqlalchemy.orm import ORMExecuteState, Session, with_loader_criteria
from sqlalchemy.sql import visitors

from app.core.models import Base, TenantScoped

TENANT_KEY = "tenant_id"
# Motivazione obbligatoria per le rare letture che attraversano più studi (es. al login).
PLATFORM_KEY = "platform_reason"


class MissingTenantContextError(RuntimeError):
    """Accesso a dati di uno studio senza aver indicato quale."""


class CrossTenantWriteError(RuntimeError):
    """Tentativo di scrivere un record con il tenant_id di un altro studio."""


class UnsafeTenantQueryError(RuntimeError):
    """Query su una tabella degli studi senza il modello ORM: il filtro non si applicherebbe."""


def _tenant_tables() -> set[Table]:
    return {
        m.local_table  # type: ignore[misc]
        for m in Base.registry.mappers
        if issubclass(m.class_, TenantScoped)
    }


def _touches_tenant_data(state: ORMExecuteState) -> bool:
    """Cerca le tabelle degli studi in tutta la query: colonne, FROM, JOIN, sottoquery, EXISTS.

    `state.all_mappers` non basta: in `select(func.count()).select_from(Modello)` è vuoto.
    """
    tenant_tables = _tenant_tables()
    via_orm = {m.local_table for m in state.all_mappers if issubclass(m.class_, TenantScoped)}
    raw: set[Table] = set()
    for element in visitors.iterate(state.statement):  # type: ignore[arg-type]
        if not isinstance(element, Table):
            continue
        base_table = getattr(element, "__element__", element)
        if base_table not in tenant_tables:
            continue
        if "parententity" in getattr(element, "_annotations", {}):
            via_orm.add(base_table)
        else:
            raw.add(base_table)
    # Una tabella presente solo come oggetto Core (Modello.__table__) non riceverebbe il filtro.
    unsafe = raw - via_orm
    if unsafe:
        names = ", ".join(sorted(t.name for t in unsafe))
        raise UnsafeTenantQueryError(f"query su '{names}' senza il modello ORM: usare la classe")
    return bool(via_orm)


@event.listens_for(Session, "do_orm_execute")
def _filter_by_tenant(state: ORMExecuteState) -> None:
    if not (state.is_select or state.is_update or state.is_delete):
        return
    if state.is_column_load or state.is_relationship_load:
        return  # caricamenti derivati da un oggetto già filtrato
    if not _touches_tenant_data(state):
        return
    if state.session.info.get(PLATFORM_KEY):
        return  # accesso di piattaforma esplicito, vedi Database.platform_session()
    tenant_id = state.session.info.get(TENANT_KEY)
    if tenant_id is None:
        raise MissingTenantContextError("accesso a dati di uno studio senza contesto tenant")
    state.statement = state.statement.options(
        with_loader_criteria(
            TenantScoped,
            lambda cls: cls.tenant_id == tenant_id,
            include_aliases=True,
        )
    )


@event.listens_for(Session, "before_flush")
def _check_writes(session: Session, _ctx: Any, _instances: Any) -> None:
    tenant_id: uuid.UUID | None = session.info.get(TENANT_KEY)
    for obj in (*session.new, *session.dirty, *session.deleted):
        if not isinstance(obj, TenantScoped):
            continue
        if session.info.get(PLATFORM_KEY):
            raise CrossTenantWriteError(
                "le sessioni di piattaforma sono in sola lettura sui dati degli studi"
            )
        if tenant_id is None:
            raise MissingTenantContextError("scrittura su dati di uno studio senza contesto tenant")
        if obj in session.new and obj.tenant_id is None:
            obj.tenant_id = tenant_id
        if obj.tenant_id != tenant_id:
            raise CrossTenantWriteError("il record appartiene a un altro studio")
