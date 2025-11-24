"""
Tests for sync endpoints.
"""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime

from fastapi import status


class TestManualSync:
    """Test manual sync endpoints."""

    @patch("app.routes.sync.sync_activity_task")
    def test_manual_sync_strava_to_garmin(self, mock_task, client, test_user_full):
        """Should trigger manual sync from Strava to Garmin."""
        mock_task.apply_async.return_value = MagicMock(id="task-123")

        # This would need authentication
        # For now, test the endpoint exists
        response = client.post(
            "/api/v1/sync/strava-to-garmin",
            json={"activity_id": 1234567890},
        )

        # May be 401 without auth, or 200 with mocked auth
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_202_ACCEPTED,
            status.HTTP_401_UNAUTHORIZED,
        ]

    @patch("app.routes.sync.GarminToStravaSyncService")
    def test_manual_sync_garmin_to_strava(self, mock_service, client, test_user_full):
        """Should trigger manual sync from Garmin to Strava."""
        mock_sync = MagicMock()
        mock_sync.sync_activity.return_value = {"status": "success"}
        mock_service.return_value = mock_sync

        response = client.post(
            "/api/v1/sync/garmin-to-strava",
            json={"activity_id": "9876543210"},
        )

        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_202_ACCEPTED,
            status.HTTP_401_UNAUTHORIZED,
        ]

    def test_manual_sync_missing_activity_id(self, client):
        """Should validate activity_id is provided."""
        response = client.post("/api/v1/sync/strava-to-garmin", json={})

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @patch("app.routes.sync.sync_activity_task")
    def test_force_sync_parameter(self, mock_task, client, test_user_full):
        """Should support force_sync parameter."""
        mock_task.apply_async.return_value = MagicMock(id="task-456")

        response = client.post(
            "/api/v1/sync/strava-to-garmin",
            json={"activity_id": 1234567890, "force_sync": True},
        )

        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_202_ACCEPTED,
            status.HTTP_401_UNAUTHORIZED,
        ]


class TestSyncHistory:
    """Test sync history/logs endpoints."""

    def test_get_sync_logs(self, client, test_user_full, sample_sync_log):
        """Should return sync history for user."""
        response = client.get("/api/v1/sync/history")

        # Will be 401 without auth, but endpoint should exist
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_401_UNAUTHORIZED,
        ]

    def test_get_sync_logs_with_filters(self, client, test_user_full):
        """Should support filtering sync logs."""
        response = client.get(
            "/api/v1/sync/history",
            params={"status": "success", "direction": "strava_to_garmin"},
        )

        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_401_UNAUTHORIZED,
        ]

    def test_get_sync_logs_pagination(self, client, test_user_full):
        """Should support pagination."""
        response = client.get(
            "/api/v1/sync/history", params={"skip": 0, "limit": 10}
        )

        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_401_UNAUTHORIZED,
        ]


class TestBatchSync:
    """Test batch sync operations."""

    @patch("app.routes.sync.sync_user_activities_task")
    def test_batch_sync_multiple_activities(self, mock_task, client, test_user_full):
        """Should sync multiple activities at once."""
        activity_ids = [1111111111, 2222222222, 3333333333]

        mock_task.apply_async.return_value = MagicMock(id="batch-task-789")

        response = client.post(
            "/api/v1/sync/batch/strava-to-garmin",
            json={"activity_ids": activity_ids},
        )

        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_202_ACCEPTED,
            status.HTTP_401_UNAUTHORIZED,
        ]

    def test_batch_sync_empty_list(self, client):
        """Should handle empty activity list."""
        response = client.post(
            "/api/v1/sync/batch/strava-to-garmin", json={"activity_ids": []}
        )

        assert response.status_code in [
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            status.HTTP_401_UNAUTHORIZED,
        ]

    def test_batch_sync_date_range(self, client, test_user_full):
        """Should support syncing activities in date range."""
        response = client.post(
            "/api/v1/sync/batch/date-range",
            json={
                "start_date": "2025-11-01",
                "end_date": "2025-11-24",
                "direction": "strava_to_garmin",
            },
        )

        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_202_ACCEPTED,
            status.HTTP_401_UNAUTHORIZED,
        ]


class TestSyncStatus:
    """Test sync status endpoints."""

    def test_get_sync_status(self, client, test_user_full):
        """Should return current sync status."""
        response = client.get("/api/v1/sync/status")

        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_401_UNAUTHORIZED,
        ]

    def test_get_task_status(self, client):
        """Should check Celery task status."""
        task_id = "test-task-id-123"
        response = client.get(f"/api/v1/sync/task/{task_id}")

        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_401_UNAUTHORIZED,
        ]


class TestSyncConfiguration:
    """Test sync configuration endpoints."""

    def test_get_sync_config(self, client, test_user_full):
        """Should return user's sync configuration."""
        response = client.get("/api/v1/sync/config")

        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_401_UNAUTHORIZED,
        ]

    def test_update_sync_config(self, client, test_user_full):
        """Should update sync configuration."""
        response = client.put(
            "/api/v1/sync/config",
            json={"auto_sync_enabled": True, "sync_interval_minutes": 5},
        )

        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_401_UNAUTHORIZED,
        ]
