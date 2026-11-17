"""Fixture comuni. I test girano su PostgreSQL e Redis reali (vedi README, sezione Test)."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config as AlembicConfig
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import Settings
from app.core.db import Database

BACKEND_DIR = Path(__file__).resolve().parents[1]


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        pytest.exit(f"Variabile d'ambiente {name} mancante: vedi README, sezione Test", 2)
    return value


@pytest.fixture(scope="session")
def settings() -> Settings:
    _require_env("DATABASE_URL")
    _require_env("MIGRATIONS_DATABASE_URL")
    return Settings(environment="test", log_json=True)


def alembic_config() -> AlembicConfig:
    return AlembicConfig(str(BACKEND_DIR / "alembic.ini"))


@pytest.fixture(scope="session", autouse=True)
def migrated_database(settings: Settings) -> None:
    command.upgrade(alembic_config(), "head")


@pytest.fixture
async def db(settings: Settings) -> AsyncIterator[Database]:
    # pool_size=1: ogni sessione riusa la stessa connessione fisica, così i test
    # verificano che il contesto tenant non "sopravviva" tra una transazione e l'altra.
    database = Database(settings.database_url.get_secret_value(), pool_size=1, max_overflow=0)
    yield database
    await database.dispose()


@pytest.fixture
async def owner_conn(settings: Settings) -> AsyncIterator[AsyncConnection]:
    assert settings.migrations_database_url is not None
    engine = create_async_engine(
        settings.migrations_database_url.get_secret_value(), poolclass=NullPool
    )
    async with engine.connect() as conn:
        yield conn
    await engine.dispose()
