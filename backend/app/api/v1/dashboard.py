"""Numeri dello studio per la dashboard."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import current_auth, get_db
from app.core.db import Database
from app.modules.accounts.service import AuthContext
from app.modules.dashboard import service

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

Db = Annotated[Database, Depends(get_db)]
Member = Annotated[AuthContext, Depends(current_auth)]


@router.get("/stats", summary="KPI del periodo (default: mese in corso)")
def stats(
    ctx: Member,
    db: Db,
    first: Annotated[date | None, Query(alias="from")] = None,
    last: Annotated[date | None, Query(alias="to")] = None,
    professional_id: uuid.UUID | None = None,
) -> dict[str, object]:
    if first is None or last is None:
        d_first, d_last = service.default_period(service.local_today(db, ctx))
        first, last = first or d_first, last or d_last
    return service.stats(db, ctx, first=first, last=last, professional_id=professional_id)
