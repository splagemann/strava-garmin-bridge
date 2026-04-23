from datetime import datetime, timedelta

from app.main import app
from app.middleware.auth import get_current_user
from app.models.auth import GarminAuth, StravaAuth, WithingsAuth
from app.utils.crypto import encrypt


def test_disconnect_garmin_removes_auth_and_updates_status(client, test_db, test_user):
    test_db.add(
        StravaAuth(
            user_id=test_user.id,
            access_token="strava-access",
            refresh_token="strava-refresh",
            expires_at=datetime.utcnow() + timedelta(hours=1),
            athlete_id="12345",
        )
    )
    test_db.add(
        GarminAuth(
            user_id=test_user.id,
            encrypted_email=encrypt("garmin@example.com"),
            encrypted_password=encrypt("garmin-password"),
            session_data="stored-session",
        )
    )
    test_db.commit()
    test_db.refresh(test_user)

    app.dependency_overrides[get_current_user] = lambda: test_user

    response = client.delete("/api/v1/auth/garmin")

    assert response.status_code == 200
    assert response.json() == {"message": "Garmin disconnected successfully"}
    assert test_db.query(GarminAuth).filter(GarminAuth.user_id == test_user.id).first() is None

    status_response = client.get("/api/v1/auth/status")
    assert status_response.status_code == 200
    assert status_response.json()["garmin_connected"] is False
    assert status_response.json()["garmin_requires_mfa"] is False


def test_disconnect_garmin_is_idempotent_for_pending_mfa(client, test_db, test_user):
    test_db.add(
        GarminAuth(
            user_id=test_user.id,
            encrypted_email=encrypt("garmin@example.com"),
            encrypted_password=encrypt("garmin-password"),
            encrypted_mfa_token=encrypt("pending-mfa-token"),
        )
    )
    test_db.commit()
    test_db.refresh(test_user)

    app.dependency_overrides[get_current_user] = lambda: test_user

    first_response = client.delete("/api/v1/auth/garmin")
    second_response = client.delete("/api/v1/auth/garmin")

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert test_db.query(GarminAuth).filter(GarminAuth.user_id == test_user.id).first() is None


def test_disconnect_withings_removes_auth_and_updates_status(client, test_db, test_user):
    test_db.add(
        StravaAuth(
            user_id=test_user.id,
            access_token="strava-access",
            refresh_token="strava-refresh",
            expires_at=datetime.utcnow() + timedelta(hours=1),
            athlete_id="12345",
        )
    )
    test_db.add(
        WithingsAuth(
            user_id=test_user.id,
            withings_userid="withings-user",
            access_token="withings-access",
            refresh_token="withings-refresh",
            expires_at=datetime.utcnow() + timedelta(hours=1),
        )
    )
    test_db.commit()
    test_db.refresh(test_user)

    app.dependency_overrides[get_current_user] = lambda: test_user

    response = client.delete("/api/v1/auth/withings")

    assert response.status_code == 200
    assert response.json() == {"message": "Withings disconnected successfully"}
    assert test_db.query(WithingsAuth).filter(WithingsAuth.user_id == test_user.id).first() is None

    status_response = client.get("/api/v1/auth/status")
    assert status_response.status_code == 200
    assert status_response.json()["withings_connected"] is False


def test_disconnect_withings_is_idempotent(client, test_user):
    app.dependency_overrides[get_current_user] = lambda: test_user

    response = client.delete("/api/v1/auth/withings")

    assert response.status_code == 200
    assert response.json() == {"message": "Withings disconnected successfully"}
