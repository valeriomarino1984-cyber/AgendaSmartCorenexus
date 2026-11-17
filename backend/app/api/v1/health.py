from __future__ import annotations

from typing import Literal

import structlog
from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.core.db import Database
from app.core.errors import ServiceUnavailableError

router = APIRouter(prefix="/health", tags=["health"])
log = structlog.get_logger("health")


class HealthStatus(BaseModel):
    status: Literal["ok"]


@router.get("", response_model=HealthStatus, summary="Liveness: il processo risponde")
def liveness() -> HealthStatus:
    return HealthStatus(status="ok")


@router.get("/ready", response_model=HealthStatus, summary="Readiness: database raggiungibile")
def readiness(request: Request) -> HealthStatus:
    db: Database = request.app.state.db
    try:
        db.ping()
    except Exception as exc:
        log.warning("readiness_failed", error_type=type(exc).__name__)
        raise ServiceUnavailableError() from exc
    return HealthStatus(status="ok")
