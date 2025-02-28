from fastapi import APIRouter
from app.api.routes import webhooks, grants, keyword_grants

api_router = APIRouter()
api_router.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
api_router.include_router(grants.router, prefix="/grants", tags=["grants"])
api_router.include_router(keyword_grants.router, prefix="/keywords", tags=["keywords"])
