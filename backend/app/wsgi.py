"""Adattatore WSGI per Passenger (cPanel "Setup Python App")."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

from a2wsgi import ASGIMiddleware
from fastapi import FastAPI

StartResponse = Callable[..., Any]
WSGIApp = Callable[[dict[str, Any], StartResponse], Iterable[bytes]]


def build_wsgi_app(app: FastAPI) -> WSGIApp:
    asgi = ASGIMiddleware(app)  # type: ignore[arg-type]

    def application(environ: dict[str, Any], start_response: StartResponse) -> Iterable[bytes]:
        # Con l'app pubblicata su agenda.corenexus.it/api, Passenger passa SCRIPT_NAME=/api e
        # PATH_INFO=/v1/...: si ricompone il path completo, così le rotte /api/v1 restano
        # identiche in sviluppo e in produzione.
        script_name = environ.get("SCRIPT_NAME", "")
        if script_name:
            environ["PATH_INFO"] = script_name + environ.get("PATH_INFO", "")
            environ["SCRIPT_NAME"] = ""
        return asgi(environ, start_response)  # type: ignore[arg-type]

    return application
