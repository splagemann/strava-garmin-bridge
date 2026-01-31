"""
Main FastAPI application.
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import Base, engine

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)

# Create database tables
Base.metadata.create_all(bind=engine)

# Initialize FastAPI app
app = FastAPI(
    title="Strava-Garmin Sync Bridge",
    description="Sync activities from Strava to Garmin Connect automatically",
    version="1.0.0",
)

# Configure CORS - restrict to specific origins for security
# allow_origins=["*"] with allow_credentials=True is insecure and invalid
allowed_origins = [
    settings.FRONTEND_URL,  # Frontend URL from settings
]

# Allow development origins if in dev mode
if settings.ENVIRONMENT == "development":
    allowed_origins.extend(
        [
            "http://localhost:3000",
            "http://localhost:5173",  # Vite default port
            "http://127.0.0.1:3000",
            "http://127.0.0.1:5173",
        ]
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,  # Specific origins only
    allow_credentials=True,  # Allow cookies/auth headers
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],  # Explicit methods
    allow_headers=["Content-Type", "Authorization"],  # Explicit headers
    max_age=600,  # Cache preflight requests for 10 minutes
)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Strava-Garmin Sync Bridge API",
        "version": "1.0.0",
        "docs": f"{settings.BASE_URL}/docs",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


# Import and include routers
from app.routes import activities, auth, filters, sync

app.include_router(auth.router, prefix=f"{settings.API_V1_PREFIX}/auth", tags=["Authentication"])
app.include_router(filters.router, prefix=f"{settings.API_V1_PREFIX}/filters", tags=["Filters"])
app.include_router(sync.router, prefix=f"{settings.API_V1_PREFIX}/sync", tags=["Sync"])
app.include_router(
    activities.router, prefix=f"{settings.API_V1_PREFIX}/activities", tags=["Activities"]
)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app", host="0.0.0.0", port=8000, reload=settings.ENVIRONMENT == "development"
    )
