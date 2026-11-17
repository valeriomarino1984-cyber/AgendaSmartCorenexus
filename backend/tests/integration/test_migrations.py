import os

import pytest
from alembic import command
from alembic.script import ScriptDirectory

from app.core.migrate import alembic_config, migrate_on_startup


def test_single_head() -> None:
    heads = ScriptDirectory.from_config(alembic_config()).get_heads()
    assert len(heads) == 1, f"più head Alembic: {heads}"


def test_migrations_are_reversible() -> None:
    cfg = alembic_config()
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")


def test_auto_migrate_runs_and_drops_ddl_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    # setenv con lo stesso valore: a fine test monkeypatch ripristina la variabile rimossa.
    monkeypatch.setenv("MIGRATIONS_DATABASE_URL", os.environ["MIGRATIONS_DATABASE_URL"])
    monkeypatch.setenv("AUTO_MIGRATE", "1")
    migrate_on_startup()
    # Dopo le migrazioni le credenziali DDL non sono più nell'ambiente del processo.
    assert "MIGRATIONS_DATABASE_URL" not in os.environ


def test_without_auto_migrate_credentials_are_dropped(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MIGRATIONS_DATABASE_URL", os.environ["MIGRATIONS_DATABASE_URL"])
    monkeypatch.delenv("AUTO_MIGRATE", raising=False)
    migrate_on_startup()
    assert "MIGRATIONS_DATABASE_URL" not in os.environ


def test_auto_migrate_requires_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTO_MIGRATE", "1")
    monkeypatch.delenv("MIGRATIONS_DATABASE_URL")
    with pytest.raises(RuntimeError, match="MIGRATIONS_DATABASE_URL"):
        migrate_on_startup()
