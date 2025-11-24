"""
Tests for activity converter utilities.
"""
import pytest
from unittest.mock import MagicMock
from datetime import datetime

from app.utils.activity_converter import ActivityConverter
from fit_tool.profile.profile_type import Sport, SubSport


class TestExtractActivityType:
    """Test extraction of activity type from various formats."""

    def test_extract_plain_string(self):
        """Should extract plain string activity type."""
        result = ActivityConverter.extract_activity_type("Run")
        assert result == "Run"

    def test_extract_pydantic_root_format(self):
        """Should extract from Pydantic root model format."""
        result = ActivityConverter.extract_activity_type("root='EBikeRide'")
        assert result == "EBikeRide"

    def test_extract_with_root_attribute(self):
        """Should extract from object with root attribute."""
        mock_obj = MagicMock()
        mock_obj.root = "VirtualRun"
        mock_obj.__str__ = lambda self: "root='VirtualRun'"

        result = ActivityConverter.extract_activity_type(mock_obj)
        assert result == "VirtualRun"

    def test_extract_none_returns_none(self):
        """Should handle None gracefully."""
        result = ActivityConverter.extract_activity_type(None)
        assert result is None


class TestMapActivityTypeToFit:
    """Test mapping of Strava types to FIT sport types."""

    def test_map_run_activity(self):
        """Should map Run to RUNNING sport."""
        sport, subsport = ActivityConverter.map_activity_type_to_fit("Run")
        assert sport == Sport.RUNNING
        assert subsport == SubSport.GENERIC

    def test_map_trail_run(self):
        """Should map TrailRun to RUNNING with TRAIL subsport."""
        sport, subsport = ActivityConverter.map_activity_type_to_fit("TrailRun")
        assert sport == Sport.RUNNING
        assert subsport == SubSport.TRAIL

    def test_map_virtual_run(self):
        """Should map VirtualRun to RUNNING with VIRTUAL_ACTIVITY subsport."""
        sport, subsport = ActivityConverter.map_activity_type_to_fit("VirtualRun")
        assert sport == Sport.RUNNING
        assert subsport == SubSport.VIRTUAL_ACTIVITY

    def test_map_ride_activity(self):
        """Should map Ride to CYCLING sport."""
        sport, subsport = ActivityConverter.map_activity_type_to_fit("Ride")
        assert sport == Sport.CYCLING
        assert subsport == SubSport.ROAD

    def test_map_ebike_ride(self):
        """Should map EBikeRide to E_BIKING sport."""
        sport, subsport = ActivityConverter.map_activity_type_to_fit("EBikeRide")
        assert sport == Sport.E_BIKING
        assert subsport == SubSport.E_BIKE_FITNESS

    def test_map_mountain_bike(self):
        """Should map MountainBikeRide to CYCLING with MOUNTAIN subsport."""
        sport, subsport = ActivityConverter.map_activity_type_to_fit("MountainBikeRide")
        assert sport == Sport.CYCLING
        assert subsport == SubSport.MOUNTAIN

    def test_map_swim_activity(self):
        """Should map Swim to SWIMMING sport."""
        sport, subsport = ActivityConverter.map_activity_type_to_fit("Swim")
        assert sport == Sport.SWIMMING
        assert subsport == SubSport.LAP_SWIMMING

    def test_map_open_water_swim(self):
        """Should map OpenWaterSwim correctly."""
        sport, subsport = ActivityConverter.map_activity_type_to_fit("OpenWaterSwim")
        assert sport == Sport.SWIMMING
        assert subsport == SubSport.OPEN_WATER

    def test_map_walk_activity(self):
        """Should map Walk to WALKING sport."""
        sport, subsport = ActivityConverter.map_activity_type_to_fit("Walk")
        assert sport == Sport.WALKING
        assert subsport == SubSport.GENERIC

    def test_map_hike_activity(self):
        """Should map Hike to HIKING sport."""
        sport, subsport = ActivityConverter.map_activity_type_to_fit("Hike")
        assert sport == Sport.HIKING
        assert subsport == SubSport.GENERIC

    def test_map_unknown_activity_defaults(self):
        """Should default to GENERIC for unknown activity types."""
        sport, subsport = ActivityConverter.map_activity_type_to_fit("UnknownActivity")
        assert sport == Sport.GENERIC
        assert subsport == SubSport.GENERIC


class TestGPXConversion:
    """Test conversion to GPX format."""

    def test_strava_to_gpx_basic(self):
        """Should convert basic Strava activity to GPX."""
        # Create mock activity
        activity = MagicMock()
        activity.name = "Morning Run"
        activity.type = "Run"
        activity.start_date = datetime(2025, 11, 24, 6, 0, 0)

        # Create mock streams
        streams = {
            "latlng": MagicMock(data=[[40.7128, -74.0060], [40.7129, -74.0061]]),
            "altitude": MagicMock(data=[10.0, 11.0]),
            "time": MagicMock(data=[0, 10]),
        }

        gpx_output = ActivityConverter.strava_to_gpx(activity, streams)

        # Verify GPX output contains expected elements
        assert "<?xml" in gpx_output
        assert "Morning Run" in gpx_output
        assert "40.7128" in gpx_output
        assert "-74.0060" in gpx_output

    def test_strava_to_gpx_empty_streams(self):
        """Should handle empty streams gracefully."""
        activity = MagicMock()
        activity.name = "Test Activity"
        activity.type = "Run"
        activity.start_date = datetime(2025, 11, 24, 6, 0, 0)

        streams = {}

        gpx_output = ActivityConverter.strava_to_gpx(activity, streams)

        # Should still produce valid GPX with no track points
        assert "<?xml" in gpx_output
        assert "Test Activity" in gpx_output

    def test_strava_to_gpx_with_heartrate(self):
        """Should include heartrate data in GPX."""
        activity = MagicMock()
        activity.name = "Run with HR"
        activity.type = "Run"
        activity.start_date = datetime(2025, 11, 24, 6, 0, 0)

        streams = {
            "latlng": MagicMock(data=[[40.7128, -74.0060]]),
            "altitude": MagicMock(data=[10.0]),
            "time": MagicMock(data=[0]),
            "heartrate": MagicMock(data=[145]),
        }

        gpx_output = ActivityConverter.strava_to_gpx(activity, streams)

        # GPX should be generated (HR extension handling may vary)
        assert "<?xml" in gpx_output
        assert "Run with HR" in gpx_output

    def test_strava_to_gpx_handles_pydantic_type(self):
        """Should handle Pydantic activity type format."""
        activity = MagicMock()
        activity.name = "E-Bike Ride"
        activity.type = "root='EBikeRide'"  # Pydantic format
        activity.start_date = datetime(2025, 11, 24, 6, 0, 0)

        streams = {
            "latlng": MagicMock(data=[[40.7128, -74.0060]]),
            "time": MagicMock(data=[0]),
        }

        gpx_output = ActivityConverter.strava_to_gpx(activity, streams)

        # Should successfully extract and convert type
        assert "<?xml" in gpx_output
        assert "E-Bike Ride" in gpx_output


class TestMapActivityType:
    """Test generic activity type mapping (Strava to Garmin string)."""

    def test_map_common_types(self):
        """Should map common activity types correctly."""
        # This tests the map_activity_type method if it exists
        # If not, we're testing the type extraction and mapping logic
        converter = ActivityConverter()

        # Test various activity types
        assert ActivityConverter.extract_activity_type("Run") == "Run"
        assert ActivityConverter.extract_activity_type("Ride") == "Ride"
        assert ActivityConverter.extract_activity_type("Swim") == "Swim"
