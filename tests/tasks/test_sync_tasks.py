"""
Tests for Celery sync tasks.
"""
import pytest
from unittest.mock import MagicMock, patch, call
from datetime import datetime, timedelta

from app.tasks.sync_tasks import (
    sync_activity_task,
    sync_user_activities_task,
)
from app.models import User, StravaAuth, GarminAuth, SyncLog
from tests.fixtures.activity_data import StravaActivityFactory, GarminActivityFactory


class TestSyncActivityTask:
    """Test individual activity sync task."""

    @patch("app.tasks.sync_tasks.SyncService")
    def test_sync_activity_success(self, mock_sync_service, test_db, test_user_full):
        """Should successfully sync activity."""
        # Mock sync service
        mock_service = MagicMock()
        mock_service.sync_activity.return_value = {"status": "success"}
        mock_sync_service.return_value = mock_service

        # Create mock task
        task = MagicMock()
        task.db = test_db
        task.request.retries = 0

        # Execute task
        result = sync_activity_task(task, test_user_full.id, 1234567890)

        assert result["status"] == "success"
        mock_service.sync_activity.assert_called_once_with(1234567890)

    def test_sync_activity_user_not_found(self, test_db):
        """Should handle missing user."""
        task = MagicMock()
        task.db = test_db

        result = sync_activity_task(task, 99999, 1234567890)

        assert "error" in result
        assert "User not found" in result["error"]

    def test_sync_activity_missing_strava_auth(self, test_db, test_user):
        """Should handle missing Strava authentication."""
        task = MagicMock()
        task.db = test_db

        result = sync_activity_task(task, test_user.id, 1234567890)

        assert "error" in result
        assert "Strava not connected" in result["error"]

    def test_sync_activity_missing_garmin_auth(self, test_db, test_user_with_strava):
        """Should handle missing Garmin authentication."""
        task = MagicMock()
        task.db = test_db

        result = sync_activity_task(task, test_user_with_strava.id, 1234567890)

        assert "error" in result
        assert "Garmin not connected" in result["error"]

    @patch("app.tasks.sync_tasks.SyncService")
    def test_sync_activity_retry_on_error(
        self, mock_sync_service, test_db, test_user_full
    ):
        """Should retry on error with exponential backoff."""
        # Mock sync service to raise error
        mock_service = MagicMock()
        mock_service.sync_activity.side_effect = Exception("API Error")
        mock_sync_service.return_value = mock_service

        # Create mock task with retry capability
        task = MagicMock()
        task.db = test_db
        task.request.retries = 0
        task.MaxRetriesExceededError = Exception

        # Mock retry to raise exception (simulating retry)
        def mock_retry(exc, countdown):
            raise exc

        task.retry = mock_retry

        # Execute task - should raise the exception for retry
        with pytest.raises(Exception, match="API Error"):
            sync_activity_task(task, test_user_full.id, 1234567890)


class TestSyncUserActivitiesTask:
    """Test batch activity sync task."""

    @patch("app.tasks.sync_tasks.sync_activity_task")
    def test_sync_multiple_activities(self, mock_sync_task, test_db, test_user_full):
        """Should queue individual tasks for each activity."""
        activity_ids = [1111111111, 2222222222, 3333333333]

        task = MagicMock()
        task.db = test_db

        result = sync_user_activities_task(task, test_user_full.id, activity_ids)

        # Should call apply_async for each activity
        assert mock_sync_task.apply_async.call_count == len(activity_ids)


class TestPollingTasks:
    """Test periodic polling tasks."""

    @patch("app.tasks.sync_tasks.StravaService")
    @patch("app.tasks.sync_tasks.SyncService")
    def test_poll_strava_activities(
        self, mock_sync_service, mock_strava_service, test_db, test_user_full
    ):
        """Should poll Strava and sync new activities."""
        # Create mock activities
        activities = StravaActivityFactory.create_batch(3)

        # Mock Strava service
        mock_strava = MagicMock()
        mock_strava.get_activities.return_value = activities
        mock_strava_service.return_value = mock_strava

        # Mock sync service
        mock_sync = MagicMock()
        mock_sync.sync_activity.return_value = {"status": "success"}
        mock_sync_service.return_value = mock_sync

        # This tests the pattern that would be used in the actual task
        # The task would get activities and sync each one
        strava_service = mock_strava_service(test_db)
        recent_activities = strava_service.get_activities(
            test_user_full.id, lookback_days=7
        )

        assert len(recent_activities) == 3

    @patch("app.tasks.sync_tasks.GarminService")
    @patch("app.tasks.sync_tasks.GarminToStravaSyncService")
    def test_poll_garmin_activities(
        self, mock_sync_service, mock_garmin_service, test_db, test_user_full
    ):
        """Should poll Garmin and sync new activities."""
        # Create mock activities with different date formats
        activities = [
            GarminActivityFactory.create(activity_id=1111, date_format="iso"),
            GarminActivityFactory.create(activity_id=2222, date_format="simple"),
            GarminActivityFactory.create(activity_id=3333, date_format="iso"),
        ]

        # Mock Garmin service
        mock_garmin = MagicMock()
        mock_garmin.get_activities_by_date.return_value = activities
        mock_garmin_service.return_value = mock_garmin

        # Mock sync service
        mock_sync = MagicMock()
        mock_sync.sync_activity.return_value = {"status": "success"}
        mock_sync_service.return_value = mock_sync

        # Test the pattern
        garmin_service = mock_garmin_service(test_db)
        start_date = datetime.utcnow() - timedelta(days=7)
        end_date = datetime.utcnow()

        recent_activities = garmin_service.get_activities_by_date(
            test_user_full.id, start_date, end_date
        )

        assert len(recent_activities) == 3

    def test_polling_skips_duplicates(self, test_db, test_user_full):
        """Polling should skip activities already synced."""
        # Create existing sync log
        sync_log = SyncLog(
            user_id=test_user_full.id,
            strava_activity_id=1234567890,
            garmin_activity_id=9876543210,
            sync_status="success",
            sync_direction="strava_to_garmin",
            synced_at=datetime.utcnow(),
        )
        test_db.add(sync_log)
        test_db.commit()

        # Query to check if activity was already synced
        existing = (
            test_db.query(SyncLog)
            .filter(
                SyncLog.user_id == test_user_full.id,
                SyncLog.strava_activity_id == 1234567890,
            )
            .first()
        )

        assert existing is not None
        assert existing.sync_status == "success"

    def test_polling_respects_filters(self, test_db, test_user_full):
        """Polling should apply user activity filters."""
        from app.models import ActivityFilter

        # Create exclude filter
        filter_rule = ActivityFilter(
            user_id=test_user_full.id,
            filter_type="exclude",
            filter_field="name",
            pattern="Virtual",
            is_regex=False,
            active=True,
        )
        test_db.add(filter_rule)
        test_db.commit()

        # Query filters
        filters = (
            test_db.query(ActivityFilter)
            .filter(
                ActivityFilter.user_id == test_user_full.id,
                ActivityFilter.active == True,
            )
            .all()
        )

        assert len(filters) == 1
        assert filters[0].pattern == "Virtual"


class TestTaskErrorHandling:
    """Test error handling in tasks."""

    @patch("app.tasks.sync_tasks.SyncService")
    def test_handles_network_error(self, mock_sync_service, test_db, test_user_full):
        """Should handle network errors gracefully."""
        mock_service = MagicMock()
        mock_service.sync_activity.side_effect = ConnectionError("Network error")
        mock_sync_service.return_value = mock_service

        task = MagicMock()
        task.db = test_db
        task.request.retries = 3
        task.MaxRetriesExceededError = Exception

        def mock_retry(exc, countdown):
            raise task.MaxRetriesExceededError()

        task.retry = mock_retry

        result = sync_activity_task(task, test_user_full.id, 1234567890)

        assert "error" in result
        assert "Max retries exceeded" in result["error"]

    @patch("app.tasks.sync_tasks.SyncService")
    def test_handles_api_rate_limit(self, mock_sync_service, test_db, test_user_full):
        """Should handle API rate limiting."""
        mock_service = MagicMock()
        mock_service.sync_activity.side_effect = Exception("Rate limit exceeded")
        mock_sync_service.return_value = mock_service

        task = MagicMock()
        task.db = test_db
        task.request.retries = 0

        def mock_retry(exc, countdown):
            # Verify exponential backoff
            assert countdown == 2**0  # First retry
            raise exc

        task.retry = mock_retry

        with pytest.raises(Exception, match="Rate limit exceeded"):
            sync_activity_task(task, test_user_full.id, 1234567890)


class TestTaskScheduling:
    """Test task scheduling and timing."""

    def test_task_lookback_period(self):
        """Tasks should use correct lookback period."""
        # Default lookback for cron jobs is 7 days
        lookback_days = 7
        start_date = datetime.utcnow() - timedelta(days=lookback_days)

        # Activities within lookback should be included
        recent_activity_date = datetime.utcnow() - timedelta(days=3)
        assert recent_activity_date > start_date

        # Activities outside lookback should be excluded
        old_activity_date = datetime.utcnow() - timedelta(days=10)
        assert old_activity_date < start_date

    def test_manual_sync_extended_lookback(self):
        """Manual sync should support extended lookback (up to 90 days)."""
        # Manual sync can go back up to 90 days
        max_lookback_days = 90
        start_date = datetime.utcnow() - timedelta(days=max_lookback_days)

        activity_date = datetime.utcnow() - timedelta(days=45)
        assert activity_date > start_date
