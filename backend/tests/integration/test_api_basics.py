from __future__ import annotations

import io
import json
import os
import signal
from collections.abc import Iterator
from typing import Any
from wsgiref.util import setup_testing_defaults

import pytest
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient
from structlog.testing import capture_logs

from app.core.config import Settings
from app.main import create_app
from app.wsgi import build_wsgi_app


@pytest.fixture
def app(settings: Settings) -> Iterator[FastAPI]:
    application = create_app(settings)
    # Router incluso con prefisso, come i moduli reali.
    probe = APIRouter(prefix="/_test")

    @probe.get("/manage/{token}")
    def _probe(token: str) -> dict[str, str]:
        return {"ok": "yes"}

    @probe.get("/files/{rest:path}")
    def _probe_path(rest: str) -> dict[str, str]:
        return {"ok": "yes"}

    @probe.get("/boom")
    def _boom() -> None:
        raise RuntimeError("errore interno con dati riservati")

    application.include_router(probe, prefix="/api/v1")
    yield application
    application.state.db.dispose()


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


def test_liveness(client: TestClient) -> None:
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
    assert len(r.headers["X-Request-ID"]) >= 8


def test_security_headers(client: TestClient) -> None:
    r = client.get("/api/v1/health")
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"
    assert "Strict-Transport-Security" not in r.headers  # solo in staging/produzione


def test_readiness_checks_db(client: TestClient) -> None:
    assert client.get("/api/v1/health/ready").status_code == 200


def test_valid_request_id_is_propagated(client: TestClient) -> None:
    r = client.get("/api/v1/health", headers={"X-Request-ID": "abc-12345678"})
    assert r.headers["X-Request-ID"] == "abc-12345678"


def test_malformed_request_id_is_replaced(client: TestClient) -> None:
    r = client.get("/api/v1/health", headers={"X-Request-ID": "<script>x"})
    assert r.headers["X-Request-ID"] != "<script>x"


def test_not_found_uses_error_envelope(client: TestClient) -> None:
    r = client.get("/api/v1/inesistente")
    assert r.status_code == 404
    body = r.json()["error"]
    assert body["code"] == "not_found"
    assert body["request_id"] == r.headers["X-Request-ID"]


def test_unhandled_error_hides_details(client: TestClient) -> None:
    r = client.get("/api/v1/_test/boom")
    assert r.status_code == 500
    assert "riservati" not in r.text
    assert r.json()["error"]["code"] == "internal_error"


def test_access_log_has_route_template_not_raw_path(client: TestClient) -> None:
    secret = "tok_SEGRETO_123"
    with capture_logs() as logs:
        r = client.get(f"/api/v1/_test/manage/{secret}?q=altro")
    assert r.status_code == 200
    entries = [e for e in logs if e.get("event") == "http_request"]
    assert entries and entries[0]["route"] == "/api/v1/_test/manage/{token}"
    assert secret not in repr(logs)


def test_access_log_masks_path_params_with_slashes(client: TestClient) -> None:
    with capture_logs() as logs:
        assert client.get("/api/v1/_test/files/segreto/annidato").status_code == 200
    assert "segreto" not in repr(logs)
    assert "annidato" not in repr(logs)


def test_access_log_static_route(client: TestClient) -> None:
    with capture_logs() as logs:
        client.get("/api/v1/health")
    assert [e["route"] for e in logs if e.get("event") == "http_request"] == ["/api/v1/health"]


def test_openapi_available_outside_production(client: TestClient) -> None:
    r = client.get("/api/openapi.json")
    assert r.status_code == 200
    assert r.json()["info"]["title"] == "CoreNexus Agenda API"


def test_openapi_disabled_in_production(settings: Settings) -> None:
    prod = settings.model_copy(
        update={
            "environment": "production",
            "app_base_url": "https://agenda.corenexus.it",
            "public_booking_base_url": "https://agenda.corenexus.it/prenota",
            "cors_origins": ["https://agenda.corenexus.it"],
        }
    )
    application = create_app(prod)
    try:
        c = TestClient(application)
        assert c.get("/api/openapi.json").status_code == 404
        h = c.get("/api/v1/health").headers
        assert h["Strict-Transport-Security"].startswith("max-age=")
        assert "default-src 'none'" in h["Content-Security-Policy"]
    finally:
        application.state.db.dispose()


def test_passenger_entrypoint_serves_readiness(app: FastAPI) -> None:
    """Percorso reale di produzione: WSGI (Passenger) montato su /api → a2wsgi → FastAPI → DB."""
    environ: dict[str, object] = {}
    setup_testing_defaults(environ)
    environ.update(SCRIPT_NAME="/api", PATH_INFO="/v1/health/ready", REQUEST_METHOD="GET")
    environ["wsgi.input"] = io.BytesIO(b"")
    status: dict[str, str] = {}

    def start_response(s: str, headers: list[tuple[str, str]], exc_info: object = None) -> None:
        status["value"] = s

    body = b"".join(build_wsgi_app(app)(environ, start_response))
    assert status["value"].startswith("200")
    assert json.loads(body) == {"status": "ok"}


@pytest.mark.skipif(not hasattr(os, "fork"), reason="fork non disponibile")
def test_works_in_forked_worker(app: FastAPI) -> None:
    """LiteSpeed (Netsons) carica l'app nel padre e risponde da processi creati per fork."""
    application = build_wsgi_app(app)
    # Una richiesta nel padre: crea adattatore e connessioni, come durante il precaricamento.
    assert _call_wsgi(application, "/v1/health/ready")[0].startswith("200")
    read_fd, write_fd = os.pipe()
    pid = os.fork()
    if pid == 0:  # processo figlio
        os.close(read_fd)
        signal.alarm(10)  # se resta bloccato, il figlio muore e il test fallisce
        status, body = _call_wsgi(application, "/v1/health/ready")
        os.write(write_fd, f"{status}|{body.decode()}".encode())
        os._exit(0)
    os.close(write_fd)
    _, exit_status = os.waitpid(pid, 0)
    result = os.read(read_fd, 1000).decode()
    os.close(read_fd)
    assert os.WIFEXITED(exit_status), "il processo figlio è rimasto bloccato"
    assert result.startswith("200") and '{"status":"ok"}' in result
    # Il padre continua a funzionare con le proprie connessioni.
    assert _call_wsgi(application, "/v1/health/ready")[0].startswith("200")


def _call_wsgi(application: Any, path: str) -> tuple[str, bytes]:
    environ: dict[str, object] = {}
    setup_testing_defaults(environ)
    environ.update(SCRIPT_NAME="/api", PATH_INFO=path, REQUEST_METHOD="GET")
    environ["wsgi.input"] = io.BytesIO(b"")
    captured: dict[str, str] = {}

    def start_response(s: str, headers: list[tuple[str, str]], exc_info: object = None) -> None:
        captured["status"] = s

    body = b"".join(application(environ, start_response))
    return captured["status"], body
