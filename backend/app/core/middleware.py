"""Middleware ASGI: request_id, log di accesso senza dati sensibili nel path."""

from __future__ import annotations

import re
import time
import uuid

import structlog
from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9-]{8,64}$")
log = structlog.get_logger("http")


def route_template(scope: Scope) -> str:
    """Path della richiesta con i parametri sostituiti dal loro nome (es. /a/{token}).

    Non si usa `route.path` perché per i router inclusi FastAPI può restituire il path
    relativo senza prefisso. Se un valore non è individuabile come segmento (es. parametri
    `:path` con '/'), si ricade sul formato della rotta: il valore non viene mai registrato.
    """
    route = scope.get("route")
    if route is None:
        return "<unmatched>"
    path: str = scope.get("path", "")
    params: dict[str, object] = scope.get("path_params") or {}
    if not params:
        return path
    by_value = {str(v).lower(): k for k, v in params.items()}
    segments = path.split("/")
    found = {s.lower() for s in segments} & by_value.keys()
    if len(found) < len(by_value):
        return "…" + str(getattr(route, "path_format", "<route>"))
    return "/".join(
        "{" + by_value[s.lower()] + "}" if s.lower() in by_value else s for s in segments
    )


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = Headers(scope=scope).get("x-request-id")
        request_id = incoming if incoming and _REQUEST_ID_RE.match(incoming) else uuid.uuid4().hex
        scope.setdefault("state", {})["request_id"] = request_id
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        status_code = 500
        started = time.perf_counter()

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                MutableHeaders(scope=message)["X-Request-ID"] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            # Solo il template (es. /public/manage/{token}), mai i valori né la query string.
            log.info(
                "http_request",
                method=scope["method"],
                route=route_template(scope),
                status=status_code,
                duration_ms=round((time.perf_counter() - started) * 1000, 1),
            )
            structlog.contextvars.clear_contextvars()


class SecurityHeadersMiddleware:
    """Header di sicurezza su ogni risposta dell'API (gli stessi del frontend, più restrittivi)."""

    def __init__(self, app: ASGIApp, *, strict: bool) -> None:
        self.app = app
        headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Cross-Origin-Opener-Policy": "same-origin",
        }
        if strict:
            # In staging/produzione l'API restituisce solo JSON (la documentazione è spenta).
            headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
            headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        self.headers = headers

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                mutable = MutableHeaders(scope=message)
                for key, value in self.headers.items():
                    mutable.setdefault(key, value)
            await send(message)

        await self.app(scope, receive, send_wrapper)


class OriginCheckMiddleware:
    """Protezione CSRF: le richieste che modificano dati devono arrivare dal nostro sito.

    L'autenticazione usa un cookie (SameSite=Lax); in più si verifica l'header Origin (o Referer)
    delle richieste POST/PUT/PATCH/DELETE. Le future rotte per webhook esterni sono escluse.
    """

    UNSAFE = frozenset({"POST", "PUT", "PATCH", "DELETE"})

    def __init__(
        self, app: ASGIApp, *, allowed: set[str], exempt_prefixes: tuple[str, ...] = ()
    ) -> None:
        self.app = app
        self.allowed = {o.rstrip("/") for o in allowed}
        self.exempt_prefixes = exempt_prefixes

    def _origin_ok(self, headers: Headers) -> bool:
        origin = headers.get("origin")
        if origin:
            return origin.rstrip("/") in self.allowed
        referer = headers.get("referer")
        if referer:
            return any(referer == o or referer.startswith(o + "/") for o in self.allowed)
        return False

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] == "http"
            and scope["method"] in self.UNSAFE
            and not scope["path"].startswith(self.exempt_prefixes)
            and not self._origin_ok(Headers(scope=scope))
        ):
            body = b'{"error":{"code":"origine_non_valida","message":"Richiesta non consentita."}}'
            await send(
                {
                    "type": "http.response.start",
                    "status": 403,
                    "headers": [
                        (b"content-type", b"application/json"),
                        (b"content-length", str(len(body)).encode()),
                    ],
                }
            )
            await send({"type": "http.response.body", "body": body})
            return
        await self.app(scope, receive, send)
