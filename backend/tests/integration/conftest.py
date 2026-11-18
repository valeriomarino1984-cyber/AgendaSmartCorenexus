"""Fixture dei test di integrazione: applicazione FastAPI e client HTTP con Origin ammessa."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app

ORIGIN = {"Origin": "http://localhost:3000"}


@pytest.fixture
def app(settings: Settings) -> Iterator[FastAPI]:
    application = create_app(settings)
    yield application
    application.state.db.dispose()


def new_client(app: FastAPI) -> TestClient:
    return TestClient(app, headers=ORIGIN)


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return new_client(app)
