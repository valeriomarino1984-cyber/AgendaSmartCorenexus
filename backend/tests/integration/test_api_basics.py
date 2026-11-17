from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from fastapi import APIRouter, FastAPI
from httpx import ASGITransport, AsyncClient
from structlog.testing import capture_logs

from app.core.config import Settings
from app.main import create_app


@pytest.fixture
async def app(settings: Settings) -> AsyncIterator[FastAPI]:
    application = create_app(settings)

    # Router incluso con prefisso, come i moduli reali.
    probe = APIRouter(prefix="/_test")

    @probe.get("/manage/{token}")
    async def _probe(token: str) -> dict[str, str]:
        return {"ok": "yes"}

    @probe.get("/files/{rest:path}")
    async def _probe_path(rest: str) -> dict[str, str]:
        return {"ok": "yes"}

    application.include_router(probe, prefix="/api/v1")

    @application.get("/api/v1/_test/boom")
    async def _boom() -> None:
        raise RuntimeError("errore interno con dati riservati")

    async with application.router.lifespan_context(application):
        yield application


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_liveness(client: AsyncClient) -> None:
    r = await client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
    assert len(r.headers["X-Request-ID"]) >= 8


async def test_readiness_checks_db_and_redis(client: AsyncClient) -> None:
    r = await client.get("/api/v1/health/ready")
    assert r.status_code == 200


async def test_valid_request_id_is_propagated(client: AsyncClient) -> None:
    r = await client.get("/api/v1/health", headers={"X-Request-ID": "abc-12345678"})
    assert r.headers["X-Request-ID"] == "abc-12345678"


async def test_malformed_request_id_is_replaced(client: AsyncClient) -> None:
    r = await client.get("/api/v1/health", headers={"X-Request-ID": "<script>\nx"})
    assert r.headers["X-Request-ID"] != "<script>\nx"


async def test_not_found_uses_error_envelope(client: AsyncClient) -> None:
    r = await client.get("/api/v1/inesistente")
    assert r.status_code == 404
    body = r.json()["error"]
    assert body["code"] == "not_found"
    assert body["request_id"] == r.headers["X-Request-ID"]


async def test_unhandled_error_hides_details(client: AsyncClient) -> None:
    r = await client.get("/api/v1/_test/boom")
    assert r.status_code == 500
    assert "riservati" not in r.text
    assert r.json()["error"]["code"] == "internal_error"


async def test_access_log_has_route_template_not_raw_path(client: AsyncClient) -> None:
    secret = "tok_SEGRETO_123"
    with capture_logs() as logs:
        r = await client.get(f"/api/v1/_test/manage/{secret}?q=altro")
    assert r.status_code == 200
    entries = [e for e in logs if e.get("event") == "http_request"]
    assert entries and entries[0]["route"] == "/api/v1/_test/manage/{token}"
    assert secret not in repr(logs)


async def test_access_log_masks_path_params_with_slashes(client: AsyncClient) -> None:
    with capture_logs() as logs:
        r = await client.get("/api/v1/_test/files/segreto/annidato")
    assert r.status_code == 200
    assert "segreto" not in repr(logs)
    assert "annidato" not in repr(logs)


async def test_access_log_static_route(client: AsyncClient) -> None:
    with capture_logs() as logs:
        await client.get("/api/v1/health")
    assert [e["route"] for e in logs if e.get("event") == "http_request"] == ["/api/v1/health"]


async def test_openapi_available_outside_production(client: AsyncClient) -> None:
    r = await client.get("/api/openapi.json")
    assert r.status_code == 200
    assert r.json()["info"]["title"] == "CoreNexus Agenda API"


async def test_openapi_disabled_in_production() -> None:
    prod = Settings(
        database_url="postgresql+asyncpg://u:p@h/db",
        environment="production",
        app_base_url="https://agenda.corenexus.it",
        public_booking_base_url="https://agenda.corenexus.it/prenota",
        cors_origins=["https://agenda.corenexus.it"],
    )
    application = create_app(prod)  # senza lifespan: nessuna connessione aperta
    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        assert (await c.get("/api/openapi.json")).status_code == 404
