"""Isolamento tra studi su MariaDB/MySQL (criterio MVP 15).

Si usano due tabelle di prova create e rimosse dal test, con le stesse regole delle tabelle reali:
modello TenantScoped, vincolo UNIQUE (tenant_id, id) e chiave esterna composita.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import (
    Engine,
    ForeignKeyConstraint,
    String,
    UniqueConstraint,
    Uuid,
    delete,
    func,
    select,
    text,
    update,
)
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Database, UnsafeDatabaseUserError
from app.core.models import Base, TenantScoped
from app.core.schema_checks import (
    find_tenant_tables_without_composite_key,
    find_unguarded_tenant_tables,
)
from app.core.tenancy import (
    CrossTenantWriteError,
    MissingTenantContextError,
    UnsafeTenantQueryError,
)

TENANT_A = uuid.UUID("00000000-0000-0000-0000-00000000000a")
TENANT_B = uuid.UUID("00000000-0000-0000-0000-00000000000b")


class ProbeNote(TenantScoped, Base):
    __tablename__ = "t_probe_note"
    __table_args__ = (UniqueConstraint("tenant_id", "id"),)
    label: Mapped[str] = mapped_column(String(50))


class ProbeComment(TenantScoped, Base):
    __tablename__ = "t_probe_comment"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        ForeignKeyConstraint(
            ["tenant_id", "note_id"], ["t_probe_note.tenant_id", "t_probe_note.id"]
        ),
    )
    note_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    body: Mapped[str] = mapped_column(String(50))


PROBES = [ProbeNote.__table__, ProbeComment.__table__]


@pytest.fixture
def probe_tables(owner_engine: Engine) -> Iterator[None]:
    Base.metadata.create_all(owner_engine, tables=PROBES)  # type: ignore[arg-type]
    yield
    Base.metadata.drop_all(owner_engine, tables=PROBES)  # type: ignore[arg-type]


@pytest.fixture
def notes(db: Database, probe_tables: None) -> dict[str, uuid.UUID]:
    ids: dict[str, uuid.UUID] = {}
    for tenant, labels in ((TENANT_A, ["a1", "a2"]), (TENANT_B, ["b1"])):
        with db.tenant_session(tenant) as s:
            for label in labels:
                note = ProbeNote(label=label)
                s.add(note)
                s.flush()
                ids[label] = note.id
    return ids


def _labels(db: Database, tenant: uuid.UUID) -> list[str]:
    with db.tenant_session(tenant) as s:
        return list(s.scalars(select(ProbeNote.label).order_by(ProbeNote.label)))


def test_tenant_sees_only_own_rows(db: Database, notes: dict[str, uuid.UUID]) -> None:
    assert _labels(db, TENANT_A) == ["a1", "a2"]
    assert _labels(db, TENANT_B) == ["b1"]


def test_new_rows_get_session_tenant(db: Database, notes: dict[str, uuid.UUID]) -> None:
    with db.tenant_session(TENANT_B) as s:
        assert s.get(ProbeNote, notes["b1"]).tenant_id == TENANT_B  # type: ignore[union-attr]


def test_cannot_read_other_tenant_by_id(db: Database, notes: dict[str, uuid.UUID]) -> None:
    with db.tenant_session(TENANT_A) as s:
        assert s.get(ProbeNote, notes["b1"]) is None
        assert s.scalar(select(func.count()).select_from(ProbeNote)) == 2


def test_aggregates_subqueries_and_exists_are_filtered(
    db: Database, notes: dict[str, uuid.UUID]
) -> None:
    with db.tenant_session(TENANT_B) as s:
        assert s.scalar(select(func.count(ProbeNote.id))) == 1
        assert s.scalar(select(func.count()).select_from(ProbeNote)) == 1
        sub = select(ProbeNote.id).where(ProbeNote.label.like("a%")).scalar_subquery()
        assert s.scalars(select(ProbeNote.label).where(ProbeNote.id.in_(sub))).all() == []
        assert s.scalar(select(select(ProbeNote).where(ProbeNote.label == "a1").exists())) is False


def test_core_table_queries_are_refused(db: Database, notes: dict[str, uuid.UUID]) -> None:
    """Modello.__table__ aggirerebbe il filtro: la query viene rifiutata invece di eseguirla."""
    with pytest.raises(UnsafeTenantQueryError), db.tenant_session(TENANT_A) as s:
        s.execute(select(ProbeNote.__table__))


def test_bulk_update_and_delete_stay_in_tenant(db: Database, notes: dict[str, uuid.UUID]) -> None:
    with db.tenant_session(TENANT_A) as s:
        s.execute(update(ProbeNote).values(label="cambiata"))
    assert _labels(db, TENANT_B) == ["b1"]
    with db.tenant_session(TENANT_A) as s:
        s.execute(delete(ProbeNote))
    assert _labels(db, TENANT_A) == []
    assert _labels(db, TENANT_B) == ["b1"]


def test_cannot_insert_for_other_tenant(db: Database, notes: dict[str, uuid.UUID]) -> None:
    with pytest.raises(CrossTenantWriteError), db.tenant_session(TENANT_A) as s:
        s.add(ProbeNote(label="intruso", tenant_id=TENANT_B))
    assert _labels(db, TENANT_B) == ["b1"]


def test_cannot_move_row_to_other_tenant(db: Database, notes: dict[str, uuid.UUID]) -> None:
    with pytest.raises(CrossTenantWriteError), db.tenant_session(TENANT_A) as s:
        note = s.get(ProbeNote, notes["a1"])
        assert note is not None
        note.tenant_id = TENANT_B
    assert _labels(db, TENANT_A) == ["a1", "a2"]


def test_no_tenant_context_is_refused(db: Database, notes: dict[str, uuid.UUID]) -> None:
    with pytest.raises(MissingTenantContextError), db.system_session() as s:
        s.scalars(select(ProbeNote)).all()
    with pytest.raises(MissingTenantContextError), db.system_session() as s:
        s.add(ProbeNote(label="senza tenant", tenant_id=TENANT_A))


def test_joins_are_filtered_on_every_table(db: Database, notes: dict[str, uuid.UUID]) -> None:
    with db.tenant_session(TENANT_A) as s:
        s.add(ProbeComment(note_id=notes["a1"], body="ok"))
    with db.tenant_session(TENANT_B) as s:
        rows = s.execute(
            select(ProbeComment, ProbeNote).join(ProbeNote, ProbeNote.id == ProbeComment.note_id)
        )
        assert rows.all() == []


def test_database_rejects_cross_tenant_reference(db: Database, notes: dict[str, uuid.UUID]) -> None:
    """Anche aggirando l'ORM, la FK composita impedisce riferimenti a un altro studio."""
    with pytest.raises(IntegrityError), db.tenant_session(TENANT_A) as s:
        s.add(ProbeComment(note_id=notes["b1"], body="riferimento a B"))


def test_tenant_session_rejects_non_uuid(db: Database) -> None:
    with pytest.raises(TypeError), db.tenant_session("00000000-0000-0000-0000-00000000000a"):  # type: ignore[arg-type]
        pass


def test_schema_guards_pass_on_conforming_tables(owner_engine: Engine, probe_tables: None) -> None:
    with owner_engine.connect() as conn:
        assert find_unguarded_tenant_tables(conn) == []
        assert find_tenant_tables_without_composite_key(conn) == []


def test_schema_guards_detect_raw_tenant_table(owner_engine: Engine) -> None:
    """Guardia CI: una tabella con tenant_id senza modello TenantScoped né chiave composita."""
    name = f"t_raw_{uuid.uuid4().hex[:8]}"
    with owner_engine.begin() as conn:
        conn.execute(text(f"CREATE TABLE {name} (id CHAR(32) PRIMARY KEY, tenant_id CHAR(32))"))
    try:
        with owner_engine.connect() as conn:
            assert name in find_unguarded_tenant_tables(conn)
            assert name in find_tenant_tables_without_composite_key(conn)
    finally:
        with owner_engine.begin() as conn:
            conn.execute(text(f"DROP TABLE {name}"))


def test_migrated_schema_is_conforming(owner_engine: Engine) -> None:
    with owner_engine.connect() as conn:
        assert find_unguarded_tenant_tables(conn) == []
        assert find_tenant_tables_without_composite_key(conn) == []


def test_app_user_has_no_schema_privileges(db: Database) -> None:
    db.verify_privileges()  # non solleva
    with pytest.raises(DBAPIError), db.engine.begin() as conn:
        conn.execute(text("CREATE TABLE t_forbidden (id INT)"))


def test_startup_refuses_privileged_user(owner_engine: Engine) -> None:
    privileged = Database(owner_engine.url.render_as_string(hide_password=False))
    try:
        with pytest.raises(UnsafeDatabaseUserError):
            privileged.verify_privileges()
    finally:
        privileged.dispose()
