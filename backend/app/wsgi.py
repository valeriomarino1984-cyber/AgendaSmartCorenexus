"""Adattatore WSGI per cPanel "Setup Python App" (Passenger / LiteSpeed lswsgi)."""

from __future__ import annotations

import os
import threading
from collections.abc import Callable, Iterable
from typing import Any
from urllib.parse import unquote

from a2wsgi import ASGIMiddleware
from fastapi import FastAPI

StartResponse = Callable[..., Any]
WSGIApp = Callable[[dict[str, Any], StartResponse], Iterable[bytes]]


# Tutte le rotte dell'API stanno sotto questo prefisso (anche la documentazione /api/docs).
API_PREFIX = "/api"


def full_path(environ: dict[str, Any]) -> str:
    """Percorso completo con il prefisso /api, qualunque sia il modo in cui il server lo passa."""
    path = _raw_full_path(environ)
    if path == API_PREFIX or path.startswith(API_PREFIX + "/"):
        return path
    # Il server ha tolto il prefisso senza indicarlo in SCRIPT_NAME: lo si rimette.
    return API_PREFIX + (path if path.startswith("/") else "/" + path)


def _raw_full_path(environ: dict[str, Any]) -> str:
    """Percorso completo della richiesta (es. /api/v1/health), qualunque sia il montaggio.

    Con l'app pubblicata su agenda.corenexus.it/api il server può passare SCRIPT_NAME=/api e
    PATH_INFO=/v1/..., oppure PATH_INFO già completo (succede su Netsons quando un'altra app
    occupa la radice del dominio). Si usa REQUEST_URI, l'indirizzo originale, quando c'è;
    altrimenti SCRIPT_NAME + PATH_INFO senza ripetere il prefisso.
    """
    request_uri: str | None = environ.get("REQUEST_URI")
    if request_uri:
        raw = request_uri.split("?", 1)[0]
        if raw.startswith(("http://", "https://")):  # forma assoluta, rara ma ammessa
            raw = "/" + raw.split("/", 3)[-1] if raw.count("/") >= 3 else "/"
        # PATH_INFO in WSGI è decodificato e rappresentato in latin-1 (PEP 3333).
        return unquote(raw, encoding="latin-1")
    script_name: str = environ.get("SCRIPT_NAME", "")
    path_info: str = environ.get("PATH_INFO", "")
    if script_name and not (path_info == script_name or path_info.startswith(script_name + "/")):
        return script_name + path_info
    return path_info or "/"


def build_wsgi_app(app: FastAPI) -> WSGIApp:
    """Restituisce l'app WSGI, sicura anche quando il server crea i processi per fork.

    LiteSpeed (usato da Netsons) carica l'app nel processo padre e poi crea i processi che
    rispondono per fork. a2wsgi avvia un thread con l'event loop alla creazione: i thread non
    sopravvivono al fork e nei figli ogni richiesta resterebbe bloccata. Per questo l'adattatore
    si crea per processo, alla prima richiesta, e le connessioni al database ereditate dal padre
    vengono scartate (non si condividono socket tra processi).
    """
    state: dict[str, Any] = {"pid": None, "asgi": None}
    lock = threading.Lock()

    def _asgi_for_this_process() -> ASGIMiddleware:
        pid = os.getpid()
        if state["pid"] != pid:
            with lock:
                if state["pid"] != pid:
                    db = getattr(app.state, "db", None)
                    if db is not None:
                        # close=False: le connessioni restano al padre, il figlio ne apre di nuove.
                        db.engine.dispose(close=False)
                    state["asgi"] = ASGIMiddleware(app)  # type: ignore[arg-type]
                    state["pid"] = pid
        asgi: ASGIMiddleware = state["asgi"]
        return asgi

    def application(environ: dict[str, Any], start_response: StartResponse) -> Iterable[bytes]:
        environ["PATH_INFO"] = full_path(environ)
        environ["SCRIPT_NAME"] = ""
        return _asgi_for_this_process()(environ, start_response)  # type: ignore[arg-type]

    return application
