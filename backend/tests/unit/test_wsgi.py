"""L'adattatore Passenger deve servire le rotte /api/v1 anche quando l'app è montata su /api."""

import io
import json
from wsgiref.util import setup_testing_defaults

import pytest
from fastapi import FastAPI

from app.wsgi import build_wsgi_app


def _call(
    script_name: str, path_info: str, request_uri: str | None = None
) -> tuple[str, dict[str, str]]:
    app = FastAPI()

    @app.get("/api/v1/ping")
    def ping() -> dict[str, str]:
        return {"pong": "ok"}

    environ: dict[str, object] = {}
    setup_testing_defaults(environ)
    environ.update(SCRIPT_NAME=script_name, PATH_INFO=path_info, REQUEST_METHOD="GET")
    if request_uri is not None:
        environ["REQUEST_URI"] = request_uri
    environ["wsgi.input"] = io.BytesIO(b"")
    captured: dict[str, str] = {}

    def start_response(
        status: str, headers: list[tuple[str, str]], exc_info: object = None
    ) -> None:
        captured["status"] = status

    body = b"".join(build_wsgi_app(app)(environ, start_response))
    return captured["status"], json.loads(body)


@pytest.mark.parametrize(
    ("script_name", "path_info", "request_uri"),
    [
        ("/api", "/v1/ping", None),  # montata su /api, prefisso separato
        ("", "/api/v1/ping", None),  # alla radice
        ("/api", "/api/v1/ping", None),  # prefisso ripetuto in PATH_INFO (Netsons, sito su /)
        ("/api", "/v1/ping", "/api/v1/ping?x=1"),  # REQUEST_URI disponibile
        ("/api", "/api/v1/ping", "/api/v1/ping"),
        ("", "/qualcosa", "/api/v1/%70ing"),  # REQUEST_URI ha la precedenza, decodificato
        ("", "/v1/ping", None),  # prefisso tolto dal server senza indicarlo
        ("", "/v1/ping", "/v1/ping"),
    ],
)
def test_routes_work_however_the_server_mounts_the_app(
    script_name: str, path_info: str, request_uri: str | None
) -> None:
    status, body = _call(script_name, path_info, request_uri)
    assert status.startswith("200")
    assert body == {"pong": "ok"}
