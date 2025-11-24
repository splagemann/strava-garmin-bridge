"""
Tests for SyncService (Strava -> Garmin sync).
"""
import pytest
from unittest.mock import MagicMock, patch, ANY
from datetime import datetime

from app.services.sync_service import SyncService
from app.models import ActivityFilter, SyncLog, User
from tests.fixtures.activity_data import StravaActivityFactory


class TestShouldSyncActivity:
    """Test the activity filtering logic."""

    def test_no_filters_syncs_all(self, test_db, test_user):
        """When no filters exist, all activities should sync."""
        sync_service = SyncService(test_db, test_user)
        assert sync_service.should_sync_activity("Any Activity") is True
        assert sync_service.should_sync_activity("Morning Run", "Run") is True

    def test_include_filter_name_match(self, test_db, test_user):
        """Include filter should sync matching activities."""
        # Create include filter
        filter_rule = ActivityFilter(
            user_id=test_user.id,
            filter_type="include",
            filter_field="name",
            pattern="Morning",
            is_regex=False,
            active=True,
        )
        test_db.add(filter_rule)
        test_db.commit()

        sync_service = SyncService(test_db, test_user)
        assert sync_service.should_sync_activity("Morning Run") is True
        assert sync_service.should_sync_activity("Evening Run") is False

    def test_include_filter_type_match(self, test_db, test_user):
        """Include filter on type should work correctly."""
        filter_rule = ActivityFilter(
            user_id=test_user.id,
            filter_type="include",
            filter_field="type",
            pattern="Run",
            is_regex=False,
            active=True,
        )
        test_db.add(filter_rule)
        test_db.commit()

        sync_service = SyncService(test_db, test_user)
        assert sync_service.should_sync_activity("Any Name", "Run") is True
        assert sync_service.should_sync_activity("Any Name", "Ride") is False

    def test_exclude_filter_blocks_matching(self, test_db, test_user):
        """Exclude filter should block matching activities."""
        filter_rule = ActivityFilter(
            user_id=test_user.id,
            filter_type="exclude",
            filter_field="name",
            pattern="Virtual",
            is_regex=False,
            active=True,
        )
        test_db.add(filter_rule)
        test_db.commit()

        sync_service = SyncService(test_db, test_user)
        assert sync_service.should_sync_activity("Virtual Run") is False
        assert sync_service.should_sync_activity("Real Run") is True

    def test_regex_filter_matching(self, test_db, test_user):
        """Regex filters should work correctly."""
        filter_rule = ActivityFilter(
            user_id=test_user.id,
            filter_type="include",
            filter_field="type",
            pattern="^(Run|Ride)$",
            is_regex=True,
            active=True,
        )
        test_db.add(filter_rule)
        test_db.commit()

        sync_service = SyncService(test_db, test_user)
        assert sync_service.should_sync_activity("Test", "Run") is True
        assert sync_service.should_sync_activity("Test", "Ride") is True
        assert sync_service.should_sync_activity("Test", "Swim") is False

    def test_invalid_regex_continues(self, test_db, test_user, caplog):
        """Invalid regex should be logged and skipped."""
        filter_rule = ActivityFilter(
            user_id=test_user.id,
            filter_type="include",
            filter_field="name",
            pattern="[invalid(",
            is_regex=True,
            active=True,
        )
        test_db.add(filter_rule)
        test_db.commit()

        sync_service = SyncService(test_db, test_user)
        # Should default to False with include filter that doesn't match
        result = sync_service.should_sync_activity("Test")
        assert result is False
        assert "Invalid regex pattern" in caplog.text

    def test_include_and_exclude_combination(self, test_db, test_user):
        """Include and exclude filters should work together."""
        # Include all "Run" activities
        include_filter = ActivityFilter(
            user_id=test_user.id,
            filter_type="include",
            filter_field="type",
            pattern="Run",
            is_regex=False,
            active=True,
        )
        # Exclude "Virtual" activities
        exclude_filter = ActivityFilter(
            user_id=test_user.id,
            filter_type="exclude",
            filter_field="name",
            pattern="Virtual",
            is_regex=False,
            active=True,
        )
        test_db.add_all([include_filter, exclude_filter])
        test_db.commit()

        sync_service = SyncService(test_db, test_user)
        # Real run - should sync
        assert sync_service.should_sync_activity("Morning Run", "Run") is True
        # Virtual run - should not sync (excluded)
        assert sync_service.should_sync_activity("Virtual Run", "Run") is False
        # Ride - should not sync (not included)
        assert sync_service.should_sync_activity("Morning Ride", "Ride") is False

    def test_inactive_filters_ignored(self, test_db, test_user):
        """Inactive filters should not affect sync decisions."""
        filter_rule = ActivityFilter(
            user_id=test_user.id,
            filter_type="exclude",
            filter_field="name",
            pattern="Test",
            is_regex=False,
            active=False,  # Inactive
        )
        test_db.add(filter_rule)
        test_db.commit()

        sync_service = SyncService(test_db, test_user)
        # Should sync because filter is inactive
        assert sync_service.should_sync_activity("Test Activity") is True

    def test_case_insensitive_matching(self, test_db, test_user):
        """Filter matching should be case-insensitive."""
        filter_rule = ActivityFilter(
            user_id=test_user.id,
            filter_type="include",
            filter_field="name",
            pattern="morning",
            is_regex=False,
            active=True,
        )
        test_db.add(filter_rule)
        test_db.commit()

        sync_service = SyncService(test_db, test_user)
        assert sync_service.should_sync_activity("MORNING RUN") is True
        assert sync_service.should_sync_activity("Morning Run") is True
        assert sync_service.should_sync_activity("morning run") is True


class TestSyncActivity:
    """Test individual activity sync."""

    @patch("app.services.sync_service.StravaService")
    @patch("app.services.sync_service.GarminService")
    def test_sync_skips_garmin_originated_activity(
        self, mock_garmin_service, mock_strava_service, test_db, test_user_full
    ):
        """Should skip activities that originated from Garmin."""
        # Create activity that came from Garmin
        strava_activity = StravaActivityFactory.create_from_garmin(9876543210)

        # Mock Strava service
        mock_strava = MagicMock()
        mock_strava.get_activity.return_value = strava_activity
        mock_strava_service.return_value = mock_strava

        sync_service = SyncService(test_db, test_user_full)
        result = sync_service.sync_activity(1234567890)

        assert result["status"] == "skipped"
        assert "originated from Garmin" in result["message"]
        # Should not call Garmin service
        mock_strava.get_activity.assert_called_once()

    @patch("app.services.sync_service.StravaService")
    @patch("app.services.sync_service.GarminService")
    def test_sync_checks_filters(
        self, mock_garmin_service, mock_strava_service, test_db, test_user_full
    ):
        """Should apply user filters before syncing."""
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

        # Create virtual activity
        strava_activity = StravaActivityFactory.create(
            name="Virtual Run", activity_type="VirtualRun"
        )

        mock_strava = MagicMock()
        mock_strava.get_activity.return_value = strava_activity
        mock_strava_service.return_value = mock_strava

        sync_service = SyncService(test_db, test_user_full)
        result = sync_service.sync_activity(1234567890)

        assert result["status"] == "skipped"
        assert "does not match activity filters" in result["message"]

    @patch("app.services.sync_service.StravaService")
    @patch("app.services.sync_service.GarminService")
    @patch("app.services.sync_service.ActivityConverter")
    def test_sync_success_creates_log(
        self,
        mock_converter,
        mock_garmin_service,
        mock_strava_service,
        test_db,
        test_user_full,
    ):
        """Successful sync should create a sync log entry."""
        strava_activity = StravaActivityFactory.create()

        # Mock services
        mock_strava = MagicMock()
        mock_strava.get_activity.return_value = strava_activity
        mock_strava.download_activity.return_value = b"fake_fit_data"
        mock_strava_service.return_value = mock_strava

        mock_garmin = MagicMock()
        mock_garmin.upload_activity.return_value = {"activityId": 9876543210}
        mock_garmin_service.return_value = mock_garmin

        mock_conv = MagicMock()
        mock_conv.strava_to_fit.return_value = "/tmp/fake.fit"
        mock_converter.return_value = mock_conv

        sync_service = SyncService(test_db, test_user_full)
        result = sync_service.sync_activity(1234567890)

        assert result["status"] == "success"

        # Check sync log was created
        sync_log = (
            test_db.query(SyncLog)
            .filter(SyncLog.strava_activity_id == 1234567890)
            .first()
        )
        assert sync_log is not None
        assert sync_log.sync_status == "success"
        assert sync_log.sync_direction == "strava_to_garmin"

    @patch("app.services.sync_service.StravaService")
    def test_sync_handles_strava_error(
        self, mock_strava_service, test_db, test_user_full
    ):
        """Should handle errors from Strava API."""
        mock_strava = MagicMock()
        mock_strava.get_activity.side_effect = Exception("Strava API Error")
        mock_strava_service.return_value = mock_strava

        sync_service = SyncService(test_db, test_user_full)
        result = sync_service.sync_activity(1234567890)

        assert result["status"] == "failed"
        assert "Strava API Error" in result["message"]

        # Check error is logged
        sync_log = (
            test_db.query(SyncLog)
            .filter(SyncLog.strava_activity_id == 1234567890)
            .first()
        )
        assert sync_log.sync_status == "failed"
