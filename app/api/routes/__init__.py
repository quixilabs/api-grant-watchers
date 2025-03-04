from app.api.routes.grants import router as grants_router
from app.api.routes.keywords import router as keywords_router
from app.api.routes.webhooks import router as webhooks_router
from app.api.routes.organizations import router as organizations_router

# Export the routers with their router attribute
grants = type('RouterWrapper', (), {'router': grants_router})
keywords = type('RouterWrapper', (), {'router': keywords_router})
webhooks = type('RouterWrapper', (), {'router': webhooks_router})
organizations = type('RouterWrapper', (), {'router': organizations_router})

__all__ = ['grants', 'keywords', 'webhooks', 'organizations']
