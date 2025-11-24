"""
Tests for authentication endpoints.
"""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

from fastapi import status


class TestStravaAuth:
    """Test Strava OAuth endpoints."""

    def test_get_auth_url(self, client):
        """Should return Strava authorization URL."""
        response = client.get("/api/v1/auth/strava/auth-url")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "auth_url" in data
        assert "state" in data
        assert "strava.com/oauth/authorize" in data["auth_url"]

    def test_auth_url_contains_state(self, client):
        """Auth URL should contain state parameter."""
        response = client.get("/api/v1/auth/strava/auth-url")
        data = response.json()

        assert "state=" in data["auth_url"]
        assert len(data["state"]) > 0

    @patch("app.routes.auth.StravaService")
    def test_oauth_callback_success(self, mock_strava_service, client, test_db):
        """Should handle successful OAuth callback."""
        # Mock Strava service
        mock_service = MagicMock()
        mock_service.exchange_token.return_value = {
            "access_token": "test_access_token",
            "refresh_token": "test_refresh_token",
            "expires_at": int((datetime.utcnow() + timedelta(hours=6)).timestamp()),
            "athlete": {"id": 123456},
        }
        mock_strava_service.return_value = mock_service

        # Make callback request
        response = client.get(
            "/api/v1/auth/strava/callback",
            params={"code": "test_code", "state": "test_state"},
        )

        # Should redirect or return success
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_302_FOUND,
            status.HTTP_307_TEMPORARY_REDIRECT,
        ]

    def test_oauth_callback_missing_code(self, client):
        """Should handle missing authorization code."""
        response = client.get(
            "/api/v1/auth/strava/callback", params={"state": "test_state"}
        )

        assert response.status_code in [
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        ]

    def test_oauth_callback_missing_state(self, client):
        """Should handle missing state parameter."""
        response = client.get(
            "/api/v1/auth/strava/callback", params={"code": "test_code"}
        )

        assert response.status_code in [
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        ]


class TestGarminAuth:
    """Test Garmin authentication endpoints."""

    @patch("app.routes.auth.GarminService")
    def test_garmin_login_success(self, mock_garmin_service, client, test_user):
        """Should authenticate with Garmin credentials."""
        # Mock Garmin service
        mock_service = MagicMock()
        mock_service.login.return_value = True
        mock_garmin_service.return_value = mock_service

        # Make login request
        response = client.post(
            "/api/v1/auth/garmin/login",
            json={"email": "garmin@example.com", "password": "garmin_password"},
        )

        # Should return success or create auth record
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_201_CREATED]

    def test_garmin_login_invalid_credentials(self, client):
        """Should handle invalid credentials."""
        with patch("app.routes.auth.GarminService") as mock_service:
            mock_service.return_value.login.side_effect = Exception("Invalid credentials")

            response = client.post(
                "/api/v1/auth/garmin/login",
                json={"email": "bad@example.com", "password": "wrong_password"},
            )

            assert response.status_code >= status.HTTP_400_BAD_REQUEST

    def test_garmin_login_missing_fields(self, client):
        """Should validate required fields."""
        response = client.post("/api/v1/auth/garmin/login", json={"email": "test@example.com"})

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestAuthStatus:
    """Test authentication status endpoints."""

    def test_check_auth_status_no_user(self, client):
        """Should return unauthenticated status."""
        response = client.get("/api/v1/auth/status")

        # Will depend on how auth middleware works
        # May return 401 or 200 with status: false
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_401_UNAUTHORIZED,
        ]

    def test_check_strava_connected(self, client, test_user_with_strava):
        """Should check if Strava is connected."""
        # This would require auth token in request
        # Depends on authentication implementation
        pass

    def test_check_garmin_connected(self, client, test_user_with_garmin):
        """Should check if Garmin is connected."""
        # This would require auth token in request
        # Depends on authentication implementation
        pass
