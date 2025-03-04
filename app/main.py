from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import grants, keywords, webhooks, organizations

from app.core.config import settings

app = FastAPI(
    title="Grant Watchers API",
    description="API for managing grants and organizations",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(grants.router, prefix="/api/v1/grants", tags=["grants"])
app.include_router(keywords.router, prefix="/api/v1/keywords", tags=["keywords"])
app.include_router(webhooks.router, prefix="/api/v1/webhooks", tags=["webhooks"])
app.include_router(organizations.router, prefix="/api/v1/organizations", tags=["organizations"])

@app.get("/")
async def root():
    return {"message": "Welcome to the Grant Watchers API"}
