"""Errori di dominio e formato uniforme delle risposte di errore."""

from __future__ import annotations

from typing import Any, TypeVar

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = structlog.get_logger("errors")


class AppError(Exception):
    status_code = 400
    code = "bad_request"
    message = "Richiesta non valida."

    def __init__(
        self, message: str | None = None, *, code: str | None = None, details: Any = None
    ) -> None:
        self.message = message or self.message
        self.code = code or self.code
        self.details = details
        super().__init__(self.message)


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"
    message = "Risorsa non trovata."


class ForbiddenError(AppError):
    status_code = 403
    code = "forbidden"
    message = "Operazione non consentita."


class ConflictError(AppError):
    status_code = 409
    code = "conflict"
    message = "La risorsa è stata modificata o non è più disponibile."


class ServiceUnavailableError(AppError):
    status_code = 503
    code = "service_unavailable"
    message = "Servizio temporaneamente non disponibile."


def _body(request: Request, code: str, message: str, details: Any = None) -> dict[str, Any]:
    error: dict[str, Any] = {
        "code": code,
        "message": message,
        "request_id": request.scope.get("state", {}).get("request_id"),
    }
    if details is not None:
        error["details"] = details
    return {"error": error}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            _body(request, exc.code, exc.message, exc.details), status_code=exc.status_code
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Il valore inviato ("input") non viene restituito né loggato: può contenere dati personali.
        details = [
            {"loc": list(err.get("loc", ())), "msg": err.get("msg"), "type": err.get("type")}
            for err in exc.errors()
        ]
        return JSONResponse(
            _body(request, "validation_error", "Dati non validi.", details), status_code=422
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = {404: "not_found", 405: "method_not_allowed"}.get(exc.status_code, "http_error")
        message = "Risorsa non trovata." if exc.status_code == 404 else str(exc.detail)
        return JSONResponse(_body(request, code, message), status_code=exc.status_code)

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled_error")
        return JSONResponse(
            _body(request, "internal_error", "Errore interno. Riprovare più tardi."),
            status_code=500,
        )


T = TypeVar("T")


def must(value: T | None, what: str = "valore") -> T:
    """Invariante esplicita (a differenza di assert, non sparisce con python -O)."""
    if value is None:
        raise RuntimeError(f"{what} mancante: stato inatteso")
    return value
