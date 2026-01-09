"""
Application configuration using Pydantic Settings.
"""

from functools import lru_cache

from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    DATABASE_URL: str

    # Strava API
    STRAVA_CLIENT_ID: str
    STRAVA_CLIENT_SECRET: str

    # Withings API
    WITHINGS_CLIENT_ID: str
    WITHINGS_CLIENT_SECRET: str

    # Redis/Celery
    REDIS_URL: str = "redis://localhost:6379/0"

    # Encryption (for Garmin credentials)
    ENCRYPTION_KEY: str

    # Application
    SECRET_KEY: str
    BASE_URL: str = "http://localhost:8000"
    FRONTEND_URL: str = "http://localhost:3000"
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"

    # API Configuration
    API_V1_PREFIX: str = "/api/v1"

    model_config = ConfigDict(env_file=".env", case_sensitive=True)


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Create a global settings instance
settings = get_settings()
