from fastapi import APIRouter
from app.api.routes import webhooks, grants

api_router = APIRouter()
api_router.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
api_router.include_router(grants.router, prefix="/grants", tags=["grants"])
