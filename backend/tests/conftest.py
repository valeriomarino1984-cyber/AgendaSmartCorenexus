"""Fixture comuni. I test girano su MariaDB/MySQL reale (vedi README, sezione Test)."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from alembic import command
from sqlalchemy import Engine, create_engine
from sqlalchemy.pool import NullPool

from app.core.config import Settings
from app.core.db import Database
from app.core.migrate import alembic_config


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


@pytest.fixture(scope="session", autouse=True)
def migrated_database(settings: Settings) -> None:
    command.upgrade(alembic_config(), "head")


@pytest.fixture
def db(settings: Settings) -> Iterator[Database]:
    database = Database(settings.database_url.get_secret_value(), pool_size=1, max_overflow=0)
    yield database
    database.dispose()


@pytest.fixture
def owner_engine(settings: Settings) -> Iterator[Engine]:
    assert settings.migrations_database_url is not None
    engine = create_engine(settings.migrations_database_url.get_secret_value(), poolclass=NullPool)
    yield engine
    engine.dispose()
