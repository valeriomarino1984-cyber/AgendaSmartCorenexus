from fastapi import APIRouter

from app.api.v1 import (
    agenda,
    auth,
    catalog,
    client_portal,
    health,
    meta,
    notifications,
    platform,
    public,
    tenants,
)

api_v1_router = APIRouter()
api_v1_router.include_router(health.router)
api_v1_router.include_router(meta.router)
api_v1_router.include_router(auth.router)
api_v1_router.include_router(tenants.router)
api_v1_router.include_router(catalog.router)
api_v1_router.include_router(agenda.router)
api_v1_router.include_router(client_portal.router)
api_v1_router.include_router(platform.router)
api_v1_router.include_router(notifications.router)
api_v1_router.include_router(public.router)
