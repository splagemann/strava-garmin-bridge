"""
Test configuration and fixtures for pytest.
"""
import os
import sys
from datetime import datetime, timedelta
from typing import Generator
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database import Base, get_db
from app.main import app
from app.models.filter import ActivityFilter
from app.models.auth import GarminAuth, StravaAuth
from app.models.sync_log import SyncLog
from app.models.user import User
from app.utils.crypto import encrypt

# Test database URL - using in-memory SQLite for speed
SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture(scope="function")
def test_db_engine():
    """Create a test database engine."""
    engine = create_engine(
        SQLALCHEMY_TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture(scope="function")
def test_db(test_db_engine) -> Generator[Session, None, None]:
    """Create a test database session."""
    TestingSessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=test_db_engine
    )
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="function")
def client(test_db) -> Generator[TestClient, None, None]:
    """Create a test client with overridden database dependency."""

    def override_get_db():
        try:
            yield test_db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def test_user(test_db: Session) -> User:
    """Create a test user."""
    user = User(email="test@example.com")
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


@pytest.fixture
def test_user_with_strava(test_db: Session, test_user: User) -> User:
    """Create a test user with Strava authentication."""
    strava_auth = StravaAuth(
        user_id=test_user.id,
        access_token="test_strava_access_token",
        refresh_token="test_strava_refresh_token",
        expires_at=datetime.utcnow() + timedelta(hours=6),
        athlete_id="123456",
    )
    test_db.add(strava_auth)
    test_db.commit()
    test_db.refresh(test_user)
    return test_user


@pytest.fixture
def test_user_with_garmin(test_db: Session, test_user: User) -> User:
    """Create a test user with Garmin authentication."""
    garmin_auth = GarminAuth(
        user_id=test_user.id,
        encrypted_email=encrypt("garmin@example.com"),
        encrypted_password=encrypt("garmin_password"),
    )
    test_db.add(garmin_auth)
    test_db.commit()
    test_db.refresh(test_user)
    return test_user


@pytest.fixture
def test_user_full(test_db: Session, test_user_with_strava: User) -> User:
    """Create a test user with both Strava and Garmin authentication."""
    garmin_auth = GarminAuth(
        user_id=test_user_with_strava.id,
        encrypted_email=encrypt("garmin@example.com"),
        encrypted_password=encrypt("garmin_password"),
    )
    test_db.add(garmin_auth)
    test_db.commit()
    test_db.refresh(test_user_with_strava)
    return test_user_with_strava


@pytest.fixture
def test_activity_filters(test_db: Session, test_user: User) -> list[ActivityFilter]:
    """Create test activity filters."""
    filters = [
        ActivityFilter(
            user_id=test_user.id,
            filter_type="include",
            filter_field="name",
            pattern="Morning Run",
            is_regex=False,
        ),
        ActivityFilter(
            user_id=test_user.id,
            filter_type="exclude",
            filter_field="type",
            pattern="Virtual.*",
            is_regex=True,
        ),
    ]
    for f in filters:
        test_db.add(f)
    test_db.commit()
    for f in filters:
        test_db.refresh(f)
    return filters


@pytest.fixture
def mock_strava_client():
    """Create a mock Strava client."""
    mock = MagicMock()
    mock.get_athlete.return_value = MagicMock(id=123456)
    return mock


@pytest.fixture
def mock_garmin_client():
    """Create a mock Garmin client."""
    mock = MagicMock()
    mock.login.return_value = None
    mock.get_activities.return_value = []
    return mock


@pytest.fixture
def sample_strava_activity():
    """Sample Strava activity data."""
    return {
        "id": 1234567890,
        "name": "Morning Run",
        "type": "Run",
        "start_date": "2025-11-24T06:00:00Z",
        "distance": 5000.0,
        "moving_time": 1800,
        "elapsed_time": 1900,
        "total_elevation_gain": 50.0,
        "average_speed": 2.78,
        "max_speed": 3.5,
        "average_heartrate": 145.0,
        "max_heartrate": 165.0,
        "external_id": "garmin_push_9876543210",  # Originated from Garmin
    }


@pytest.fixture
def sample_garmin_activity():
    """Sample Garmin activity data (ISO format from get_activities)."""
    return {
        "activityId": 9876543210,
        "activityName": "Evening Ride",
        "activityType": {"typeKey": "cycling"},
        "startTimeGMT": "2025-11-24T18:00:00Z",
        "distance": 20000.0,
        "duration": 3600.0,
        "elevationGain": 150.0,
        "averageSpeed": 5.56,
        "maxSpeed": 8.33,
        "averageHR": 135.0,
        "maxHR": 160.0,
    }


@pytest.fixture
def sample_garmin_activity_simple_date():
    """Sample Garmin activity data (simple format from get_activities_by_date)."""
    return {
        "activityId": 9876543211,
        "activityName": "Lunch Walk",
        "activityType": {"typeKey": "walking"},
        "startTimeGMT": "2025-11-24 12:00:00",  # Simple format, no timezone
        "distance": 3000.0,
        "duration": 1800.0,
        "elevationGain": 20.0,
        "averageSpeed": 1.67,
        "maxSpeed": 2.0,
    }


@pytest.fixture
def sample_sync_log(test_db: Session, test_user: User) -> SyncLog:
    """Create a sample sync log entry."""
    sync_log = SyncLog(
        user_id=test_user.id,
        strava_activity_id=1234567890,
        garmin_activity_id=9876543210,
        sync_status="success",
        sync_direction="strava_to_garmin",
        synced_at=datetime.utcnow(),
    )
    test_db.add(sync_log)
    test_db.commit()
    test_db.refresh(sync_log)
    return sync_log
