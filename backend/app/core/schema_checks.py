"""Controlli sullo schema reale del database, eseguiti dai test (guardia CI)."""

from __future__ import annotations

from sqlalchemy import Connection, text

from app.core.models import Base, TenantScoped


def tenant_model_tables() -> set[str]:
    return {
        str(getattr(m.local_table, "name", ""))
        for m in Base.registry.mappers
        if issubclass(m.class_, TenantScoped)
    }


def _tables_with_tenant_id(conn: Connection) -> set[str]:
    rows = conn.execute(
        text(
            "SELECT table_name FROM information_schema.columns "
            "WHERE table_schema = DATABASE() AND column_name = 'tenant_id'"
        )
    )
    return {r[0] for r in rows}


def find_unguarded_tenant_tables(conn: Connection) -> list[str]:
    """Tabelle con tenant_id che non corrispondono a un modello TenantScoped (niente filtro ORM)."""
    return sorted(_tables_with_tenant_id(conn) - tenant_model_tables())


def find_tenant_tables_without_composite_key(conn: Connection) -> list[str]:
    """Tabelle con tenant_id senza un indice UNIQUE esattamente su (tenant_id, id)."""
    rows = conn.execute(
        text(
            "SELECT table_name, index_name, "
            "GROUP_CONCAT(column_name ORDER BY seq_in_index) AS cols "
            "FROM information_schema.statistics "
            "WHERE table_schema = DATABASE() AND non_unique = 0 "
            "GROUP BY table_name, index_name"
        )
    )
    with_key = {r.table_name for r in rows if r.cols == "tenant_id,id"}
    return sorted(_tables_with_tenant_id(conn) - with_key)
