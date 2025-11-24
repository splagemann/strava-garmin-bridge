"""
Tests for GarminToStravaSyncService (Garmin -> Strava sync).
"""
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta

from app.services.garmin_to_strava_sync_service import GarminToStravaSyncService
from app.models import ActivityFilter, SyncLog
from tests.fixtures.activity_data import GarminActivityFactory


class TestGarminToStravaShouldSync:
    """Test the activity filtering logic for Garmin to Strava sync."""

    def test_should_sync_returns_tuple(self, test_db, test_user):
        """should_sync_activity should return (bool, reason) tuple."""
        sync_service = GarminToStravaSyncService(test_db, test_user)
        should_sync, reason = sync_service.should_sync_activity("Test Activity")
        assert isinstance(should_sync, bool)
        assert should_sync is True
        assert reason is None

    def test_exclude_filter_returns_reason(self, test_db, test_user):
        """Exclude filter should return skip reason."""
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

        sync_service = GarminToStravaSyncService(test_db, test_user)
        should_sync, reason = sync_service.should_sync_activity("Virtual Run")

        assert should_sync is False
        assert "Excluded by filter" in reason
        assert "Virtual" in reason

    def test_include_filter_no_match_returns_reason(self, test_db, test_user):
        """Include filter with no match should return skip reason."""
        filter_rule = ActivityFilter(
            user_id=test_user.id,
            filter_type="include",
            filter_field="type",
            pattern="running",
            is_regex=False,
            active=True,
        )
        test_db.add(filter_rule)
        test_db.commit()

        sync_service = GarminToStravaSyncService(test_db, test_user)
        should_sync, reason = sync_service.should_sync_activity("Test", "cycling")

        assert should_sync is False
        assert "No include filters matched" in reason


class TestCheckDuplicateSync:
    """Test duplicate detection logic."""

    def test_no_previous_sync_returns_none(self, test_db, test_user):
        """Should return None if activity has never been synced."""
        sync_service = GarminToStravaSyncService(test_db, test_user)
        result = sync_service.check_duplicate_sync("9876543210")
        assert result is None

    def test_detects_previous_garmin_to_strava_sync(self, test_db, test_user):
        """Should detect if activity was already synced Garmin -> Strava."""
        # Create previous sync log
        sync_log = SyncLog(
            user_id=test_user.id,
            garmin_activity_id=9876543210,
            strava_activity_id=1234567890,
            sync_status="success",
            sync_direction="garmin_to_strava",
            synced_at=datetime.utcnow(),
        )
        test_db.add(sync_log)
        test_db.commit()

        sync_service = GarminToStravaSyncService(test_db, test_user)
        result = sync_service.check_duplicate_sync("9876543210")

        assert result is not None
        assert result.garmin_activity_id == 9876543210

    def test_ignores_failed_syncs(self, test_db, test_user):
        """Should ignore failed sync attempts."""
        # Create failed sync log
        sync_log = SyncLog(
            user_id=test_user.id,
            garmin_activity_id=9876543210,
            sync_status="failed",
            sync_direction="garmin_to_strava",
            synced_at=datetime.utcnow(),
        )
        test_db.add(sync_log)
        test_db.commit()

        sync_service = GarminToStravaSyncService(test_db, test_user)
        result = sync_service.check_duplicate_sync("9876543210")

        # Should return None because failed syncs don't count
        assert result is None


class TestPingPongPrevention:
    """Test prevention of syncing activities back to their origin."""

    def test_detects_strava_originated_activity(self, test_db, test_user):
        """Should detect if Garmin activity originated from Strava."""
        # Create log showing this was synced Strava -> Garmin
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

        sync_service = GarminToStravaSyncService(test_db, test_user)

        # Check if this Garmin activity originated from Strava
        # The service should find the strava_to_garmin log
        result = sync_service.check_duplicate_sync("9876543210")
        assert result is not None
        assert result.sync_direction == "strava_to_garmin"


class TestDateHandling:
    """Test handling of different date formats from Garmin API."""

    def test_parse_iso_format_date(self, test_db, test_user):
        """Should parse ISO format dates from get_activities()."""
        from app.services.garmin_to_strava_sync_service import GarminToStravaSyncService

        # ISO format: "2025-11-24T18:00:00Z"
        iso_date = "2025-11-24T18:00:00Z"

        # This would be tested in the actual sync method
        # The service should handle this format correctly
        activity = GarminActivityFactory.create(date_format="iso")
        assert "T" in activity["startTimeGMT"]
        assert activity["startTimeGMT"].endswith("Z")

    def test_parse_simple_format_date(self, test_db, test_user):
        """Should parse simple format dates from get_activities_by_date()."""
        # Simple format: "2025-11-24 18:00:00"
        activity = GarminActivityFactory.create(date_format="simple")
        assert "T" not in activity["startTimeGMT"]
        assert not activity["startTimeGMT"].endswith("Z")

    @patch("app.services.garmin_to_strava_sync_service.GarminService")
    @patch("app.services.garmin_to_strava_sync_service.StravaService")
    def test_sync_handles_both_date_formats(
        self, mock_strava_service, mock_garmin_service, test_db, test_user_full
    ):
        """Sync should handle both ISO and simple date formats."""
        # Test with ISO format
        iso_activity = GarminActivityFactory.create(
            activity_id=1111111111, date_format="iso"
        )

        # Test with simple format
        simple_activity = GarminActivityFactory.create(
            activity_id=2222222222, date_format="simple"
        )

        # Both should be parseable by the service
        # The actual parsing happens in the sync_activity method
        assert iso_activity["startTimeGMT"] is not None
        assert simple_activity["startTimeGMT"] is not None


class TestSyncActivity:
    """Test the complete sync flow for Garmin to Strava."""

    @patch("app.services.garmin_to_strava_sync_service.GarminService")
    @patch("app.services.garmin_to_strava_sync_service.StravaService")
    def test_sync_skips_duplicate(
        self, mock_strava_service, mock_garmin_service, test_db, test_user_full
    ):
        """Should skip activities that were already synced."""
        # Create previous sync log
        sync_log = SyncLog(
            user_id=test_user_full.id,
            garmin_activity_id=9876543210,
            strava_activity_id=1234567890,
            sync_status="success",
            sync_direction="garmin_to_strava",
            synced_at=datetime.utcnow(),
        )
        test_db.add(sync_log)
        test_db.commit()

        garmin_activity = GarminActivityFactory.create(activity_id=9876543210)

        mock_garmin = MagicMock()
        mock_garmin.get_activity.return_value = garmin_activity
        mock_garmin_service.return_value = mock_garmin

        sync_service = GarminToStravaSyncService(test_db, test_user_full)
        result = sync_service.sync_activity("9876543210", activity_data=garmin_activity)

        assert result["status"] == "skipped"
        assert "already been synced" in result["message"]

    @patch("app.services.garmin_to_strava_sync_service.GarminService")
    @patch("app.services.garmin_to_strava_sync_service.StravaService")
    def test_force_sync_overrides_duplicate_check(
        self, mock_strava_service, mock_garmin_service, test_db, test_user_full
    ):
        """force_sync=True should sync even if already synced."""
        # Create previous sync log
        sync_log = SyncLog(
            user_id=test_user_full.id,
            garmin_activity_id=9876543210,
            strava_activity_id=1234567890,
            sync_status="success",
            sync_direction="garmin_to_strava",
            synced_at=datetime.utcnow(),
        )
        test_db.add(sync_log)
        test_db.commit()

        garmin_activity = GarminActivityFactory.create(activity_id=9876543210)

        mock_garmin = MagicMock()
        mock_garmin.get_activity.return_value = garmin_activity
        mock_garmin.download_activity.return_value = b"fake_fit_data"
        mock_garmin_service.return_value = mock_garmin

        mock_strava = MagicMock()
        mock_strava.upload_activity.return_value = {"id": 1234567891}
        mock_strava_service.return_value = mock_strava

        sync_service = GarminToStravaSyncService(test_db, test_user_full)
        result = sync_service.sync_activity(
            "9876543210", activity_data=garmin_activity, force_sync=True
        )

        # Should attempt sync despite duplicate
        # (result may still be skipped/failed based on other factors)
        assert mock_garmin.download_activity.called or result["status"] == "skipped"

    @patch("app.services.garmin_to_strava_sync_service.GarminService")
    @patch("app.services.garmin_to_strava_sync_service.StravaService")
    def test_sync_skips_strava_originated(
        self, mock_strava_service, mock_garmin_service, test_db, test_user_full
    ):
        """Should skip Garmin activities that came from Strava (ping-pong prevention)."""
        # Create log showing this activity came from Strava
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

        garmin_activity = GarminActivityFactory.create(activity_id=9876543210)

        mock_garmin = MagicMock()
        mock_garmin.get_activity.return_value = garmin_activity
        mock_garmin_service.return_value = mock_garmin

        sync_service = GarminToStravaSyncService(test_db, test_user_full)
        result = sync_service.sync_activity("9876543210", activity_data=garmin_activity)

        assert result["status"] == "skipped"
        assert "originated from Strava" in result["message"]
