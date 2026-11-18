"""Informazioni pubbliche per il frontend (configurazione, categorie)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import get_db, get_settings_dep
from app.core.config import Settings
from app.core.db import Database
from app.modules.accounts import service

router = APIRouter(prefix="/meta", tags=["meta"])


@router.get("/config")
def config(settings: Annotated[Settings, Depends(get_settings_dep)]) -> dict[str, object]:
    return {"signup_open": settings.signup_open}


@router.get("/business-types")
def business_types(db: Annotated[Database, Depends(get_db)]) -> list[dict[str, object]]:
    return service.business_types(db)
