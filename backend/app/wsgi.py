"""Adattatore WSGI per cPanel "Setup Python App" (Passenger / LiteSpeed lswsgi)."""

from __future__ import annotations

import os
import threading
from collections.abc import Callable, Iterable
from typing import Any

from a2wsgi import ASGIMiddleware
from fastapi import FastAPI

StartResponse = Callable[..., Any]
WSGIApp = Callable[[dict[str, Any], StartResponse], Iterable[bytes]]


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
        # Con l'app pubblicata su agenda.corenexus.it/api, il server passa SCRIPT_NAME=/api e
        # PATH_INFO=/v1/...: si ricompone il path completo, così le rotte /api/v1 restano
        # identiche in sviluppo e in produzione.
        script_name = environ.get("SCRIPT_NAME", "")
        if script_name:
            environ["PATH_INFO"] = script_name + environ.get("PATH_INFO", "")
            environ["SCRIPT_NAME"] = ""
        return _asgi_for_this_process()(environ, start_response)  # type: ignore[arg-type]

    return application
