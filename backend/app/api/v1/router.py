from fastapi import APIRouter

from app.api.v1 import auth, catalog, health, meta, tenants

api_v1_router = APIRouter()
api_v1_router.include_router(health.router)
api_v1_router.include_router(meta.router)
api_v1_router.include_router(auth.router)
api_v1_router.include_router(tenants.router)
api_v1_router.include_router(catalog.router)
