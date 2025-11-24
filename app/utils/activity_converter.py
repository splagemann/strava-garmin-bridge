"""
Utility for converting Strava activity data to Garmin-compatible formats.
"""

import tempfile
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import gpxpy
import gpxpy.gpx
from fit_tool.fit_file_builder import FitFileBuilder
from fit_tool.profile.messages.activity_message import ActivityMessage
from fit_tool.profile.messages.file_id_message import FileIdMessage
from fit_tool.profile.messages.lap_message import LapMessage
from fit_tool.profile.messages.record_message import RecordMessage
from fit_tool.profile.messages.session_message import SessionMessage
from fit_tool.profile.profile_type import (
    Event,
    EventType,
    FileType,
    LapTrigger,
    Manufacturer,
    Sport,
    SubSport,
)


class ActivityConverter:
    """Convert Strava activity data to GPX format for Garmin upload."""

    @staticmethod
    def extract_activity_type(activity_type: Any) -> str:
        """
        Extract the actual activity type string from various formats.

        Handles:
        - Pydantic models: "root='EBikeRide'" -> "EBikeRide"
        - Direct strings: "EBikeRide" -> "EBikeRide"
        - Objects with root attribute: obj.root -> "EBikeRide"
        """
        if activity_type is None:
            return None

        # If it's already a plain string without root=, return it
        type_str = str(activity_type)

        # Check if it's a Pydantic root model format: "root='Value'"
        if "root=" in type_str and "'" in type_str:
            # Extract the value between quotes: root='EBikeRide' -> EBikeRide
            import re

            match = re.search(r"root='([^']+)'", type_str)
            if match:
                return match.group(1)

        # Try to access .root attribute directly (for Pydantic RootModel)
        if hasattr(activity_type, "root"):
            return str(activity_type.root)

        # Otherwise return the string representation
        return type_str

    @staticmethod
    def strava_to_gpx(activity: Any, streams: Dict[str, Any]) -> str:
        """
        Convert Strava activity and streams to GPX format.

        Args:
            activity: Strava activity object
            streams: Dictionary of Stream objects from stravalib

        Returns:
            GPX data as string
        """
        # Create GPX object
        gpx = gpxpy.gpx.GPX()

        # Create track
        gpx_track = gpxpy.gpx.GPXTrack()
        gpx_track.name = activity.name
        # Extract activity type and map to Garmin-compatible type
        if activity.type:
            strava_type = ActivityConverter.extract_activity_type(activity.type)
            gpx_track.type = ActivityConverter.map_activity_type(strava_type)
        else:
            gpx_track.type = None
        gpx.tracks.append(gpx_track)

        # Create segment
        gpx_segment = gpxpy.gpx.GPXTrackSegment()
        gpx_track.segments.append(gpx_segment)

        # Extract stream data - stravalib returns Stream objects, not dicts
        # Access the data attribute directly from Stream objects
        latlng = streams.get("latlng").data if "latlng" in streams and streams.get("latlng") else []
        altitude = (
            streams.get("altitude").data
            if "altitude" in streams and streams.get("altitude")
            else []
        )
        time_data = streams.get("time").data if "time" in streams and streams.get("time") else []
        heartrate = (
            streams.get("heartrate").data
            if "heartrate" in streams and streams.get("heartrate")
            else []
        )

        # Build track points
        for i, coords in enumerate(latlng):
            if len(coords) != 2:
                continue

            lat, lng = coords
            point = gpxpy.gpx.GPXTrackPoint(
                latitude=lat,
                longitude=lng,
                elevation=altitude[i] if i < len(altitude) else None,
                time=(
                    activity.start_date + timedelta(seconds=time_data[i])
                    if i < len(time_data)
                    else None
                ),
            )

            # Add heart rate as extension if available
            if i < len(heartrate):
                # Note: GPX extensions for HR would need to be added here
                pass

            gpx_segment.points.append(point)

        return gpx.to_xml()

    @staticmethod
    def map_activity_type_to_fit(strava_type: str) -> Tuple[Sport, Optional[SubSport]]:
        """
        Map Strava activity type to FIT Sport and SubSport enums.

        Args:
            strava_type: Strava activity type

        Returns:
            Tuple of (Sport, SubSport) enums
        """
        type_mapping = {
            # Running activities
            "Run": (Sport.RUNNING, SubSport.GENERIC),
            "TrailRun": (Sport.RUNNING, SubSport.TRAIL),
            "VirtualRun": (Sport.RUNNING, SubSport.VIRTUAL_ACTIVITY),
            # Cycling activities
            "Ride": (Sport.CYCLING, SubSport.ROAD),
            "MountainBikeRide": (Sport.CYCLING, SubSport.MOUNTAIN),
            "GravelRide": (Sport.CYCLING, SubSport.GRAVEL_CYCLING),
            "VirtualRide": (Sport.CYCLING, SubSport.VIRTUAL_ACTIVITY),
            "EBikeRide": (Sport.E_BIKING, SubSport.E_BIKE_FITNESS),
            "EMountainBikeRide": (Sport.E_BIKING, SubSport.E_BIKE_MOUNTAIN),
            "Handcycle": (Sport.CYCLING, SubSport.HAND_CYCLING),
            "Velomobile": (Sport.CYCLING, SubSport.RECUMBENT),
            # Swimming activities
            "Swim": (Sport.SWIMMING, SubSport.LAP_SWIMMING),
            "OpenWaterSwim": (Sport.SWIMMING, SubSport.OPEN_WATER),
            # Walking/Hiking activities
            "Walk": (Sport.WALKING, SubSport.GENERIC),
            "Hike": (Sport.HIKING, SubSport.GENERIC),
            # Winter sports
            "AlpineSki": (Sport.ALPINE_SKIING, SubSport.GENERIC),
            "BackcountrySki": (Sport.ALPINE_SKIING, SubSport.BACKCOUNTRY),
            "NordicSki": (Sport.CROSS_COUNTRY_SKIING, SubSport.GENERIC),
            "Snowboard": (Sport.SNOWBOARDING, SubSport.GENERIC),
            "Snowshoe": (Sport.SNOWSHOEING, SubSport.GENERIC),
            "IceSkate": (Sport.ICE_SKATING, SubSport.GENERIC),
            # Water sports
            "Canoeing": (Sport.KAYAKING, SubSport.GENERIC),
            "Kayaking": (Sport.KAYAKING, SubSport.GENERIC),
            "Kitesurf": (Sport.KITESURFING, SubSport.GENERIC),
            "Rowing": (Sport.ROWING, SubSport.GENERIC),
            "StandUpPaddling": (Sport.STAND_UP_PADDLEBOARDING, SubSport.GENERIC),
            "Surfing": (Sport.SURFING, SubSport.GENERIC),
            "Windsurf": (Sport.WINDSURFING, SubSport.GENERIC),
            # Fitness activities
            "Workout": (Sport.FITNESS_EQUIPMENT, SubSport.CARDIO_TRAINING),
            "WeightTraining": (Sport.TRAINING, SubSport.STRENGTH_TRAINING),
            "Yoga": (Sport.TRAINING, SubSport.FLEXIBILITY_TRAINING),
            "Pilates": (Sport.TRAINING, SubSport.PILATES),
            "Crossfit": (Sport.TRAINING, SubSport.EXERCISE),
            "Elliptical": (Sport.FITNESS_EQUIPMENT, SubSport.ELLIPTICAL),
            "StairStepper": (Sport.FLOOR_CLIMBING, SubSport.STAIR_CLIMBING),
            "RockClimbing": (Sport.ROCK_CLIMBING, SubSport.GENERIC),
            # Other sports
            "InlineSkate": (Sport.INLINE_SKATING, SubSport.GENERIC),
            "Golf": (Sport.GOLF, SubSport.GENERIC),
            "Soccer": (Sport.SOCCER, SubSport.GENERIC),
            "Basketball": (Sport.BASKETBALL, SubSport.GENERIC),
            "Tennis": (Sport.TENNIS, SubSport.GENERIC),
        }
        return type_mapping.get(strava_type, (Sport.GENERIC, SubSport.GENERIC))

    @staticmethod
    def strava_to_fit(activity: Any, streams: Dict[str, Any]) -> bytes:
        """
        Convert Strava activity and streams to FIT format.

        Args:
            activity: Strava activity object
            streams: Dictionary of Stream objects from stravalib

        Returns:
            FIT data as bytes
        """
        import logging

        logger = logging.getLogger(__name__)

        # Helper function to convert Duration/timedelta to seconds
        def duration_to_seconds(duration):
            """Convert Duration or timedelta to seconds (float).
            stravalib Duration is an integer subclass representing seconds."""
            if duration is None:
                return None
            # Try timedelta first (has total_seconds method)
            if hasattr(duration, "total_seconds") and callable(getattr(duration, "total_seconds")):
                return float(duration.total_seconds())
            # Duration is an integer subclass, just convert to float
            try:
                return float(duration)
            except (TypeError, ValueError) as e:
                logger.warning(
                    f"Could not convert duration to seconds: {duration} (type: {type(duration)}), error: {e}"
                )
                return None

        # Convert datetime to Unix timestamp in milliseconds for fit_tool
        from datetime import timezone

        def datetime_to_fit_timestamp(dt):
            """Convert datetime to Unix timestamp in milliseconds.
            fit_tool expects timestamps in milliseconds, not seconds."""
            if dt.tzinfo is None:
                # Assume UTC if no timezone info
                dt = dt.replace(tzinfo=timezone.utc)
            else:
                # Convert to UTC
                dt = dt.astimezone(timezone.utc)

            # Return Unix timestamp in MILLISECONDS
            return round(dt.timestamp() * 1000)

        # Extract activity type
        activity_type_str = (
            ActivityConverter.extract_activity_type(activity.type) if activity.type else "Ride"
        )
        sport, sub_sport = ActivityConverter.map_activity_type_to_fit(activity_type_str)
        logger.info(f"Activity type: {activity_type_str} -> Sport: {sport}, SubSport: {sub_sport}")

        # Extract stream data
        latlng = streams.get("latlng").data if "latlng" in streams and streams.get("latlng") else []
        altitude = (
            streams.get("altitude").data
            if "altitude" in streams and streams.get("altitude")
            else []
        )
        time_data_raw = (
            streams.get("time").data if "time" in streams and streams.get("time") else []
        )
        heartrate = (
            streams.get("heartrate").data
            if "heartrate" in streams and streams.get("heartrate")
            else []
        )
        cadence = (
            streams.get("cadence").data if "cadence" in streams and streams.get("cadence") else []
        )

        # Convert time data to seconds (might be int, float, or timedelta)
        time_data = []
        for t in time_data_raw:
            if isinstance(t, timedelta):
                time_data.append(t.total_seconds())
            elif isinstance(t, (int, float)):
                time_data.append(float(t))
            else:
                # If it's something else, try to convert to float
                time_data.append(float(t))

        # Get start time and ensure it's a datetime object
        start_time = activity.start_date
        logger.info(f"activity.start_date type: {type(start_time)}, value: {start_time}")

        if not isinstance(start_time, datetime):
            # If it's a string or something else, try to parse it
            if isinstance(start_time, str):
                from dateutil import parser

                start_time = parser.parse(start_time)
            else:
                raise ValueError(
                    f"activity.start_date is not a datetime object: {type(start_time)}"
                )

        logger.info(
            f"start_time after conversion - type: {type(start_time)}, value: {start_time}, tzinfo: {start_time.tzinfo}"
        )

        # Test the timestamp conversion
        test_timestamp = datetime_to_fit_timestamp(start_time)
        logger.info(f"FIT timestamp (ms): {test_timestamp}")

        # Create FIT file builder
        builder = FitFileBuilder(auto_define=True, min_string_size=50)

        # 1. File ID Message
        file_id = FileIdMessage()
        file_id.type = FileType.ACTIVITY
        file_id.manufacturer = Manufacturer.STRAVA
        file_id.product = 0
        file_id.time_created = datetime_to_fit_timestamp(start_time)
        builder.add(file_id)

        # 2. Create Record Messages (GPS points)
        records = []
        for i, coords in enumerate(latlng):
            if len(coords) != 2:
                continue

            lat, lng = coords
            record = RecordMessage()

            # Position (fit_tool expects degrees, it handles conversion internally)
            record.position_lat = lat
            record.position_long = lng

            # Timestamp
            if i < len(time_data):
                point_time = start_time + timedelta(seconds=time_data[i])
                record.timestamp = datetime_to_fit_timestamp(point_time)

            # Altitude (meters)
            if i < len(altitude):
                record.altitude = altitude[i]

            # Heart rate (bpm)
            if i < len(heartrate):
                record.heart_rate = int(heartrate[i])

            # Cadence (rpm)
            if i < len(cadence):
                record.cadence = int(cadence[i])

            # Distance (meters)
            if hasattr(activity, "distance") and activity.distance and len(latlng) > 0:
                # Approximate distance based on position in stream
                record.distance = float(activity.distance) * (i / len(latlng))

            records.append(record)
            builder.add(record)

        # 3. Lap Message
        if records:
            lap = LapMessage()
            # timestamps are already in milliseconds from records
            lap.timestamp = (
                records[-1].timestamp
                if records[-1].timestamp
                else datetime_to_fit_timestamp(start_time)
            )
            lap.start_time = datetime_to_fit_timestamp(start_time)
            lap.sport = sport
            lap.sub_sport = sub_sport
            logger.info(
                f"Setting Lap: sport={sport} ({type(sport)}), sub_sport={sub_sport} ({type(sub_sport)})"
            )
            lap.total_elapsed_time = duration_to_seconds(activity.elapsed_time)
            lap.total_timer_time = duration_to_seconds(activity.moving_time)
            lap.total_distance = (
                float(activity.distance)
                if hasattr(activity, "distance") and activity.distance
                else None
            )
            lap.total_calories = (
                int(activity.calories)
                if hasattr(activity, "calories") and activity.calories
                else None
            )

            # Average/max heart rate
            if heartrate:
                lap.avg_heart_rate = int(sum(heartrate) / len(heartrate))
                lap.max_heart_rate = int(max(heartrate))

            # Average/max cadence
            if cadence:
                lap.avg_cadence = int(sum(cadence) / len(cadence))
                lap.max_cadence = int(max(cadence))

            # Elevation
            if hasattr(activity, "total_elevation_gain") and activity.total_elevation_gain:
                lap.total_ascent = int(activity.total_elevation_gain)

            lap.lap_trigger = LapTrigger.SESSION_END
            builder.add(lap)

        # 4. Session Message
        session = SessionMessage()
        session.timestamp = (
            records[-1].timestamp
            if records and records[-1].timestamp
            else datetime_to_fit_timestamp(start_time)
        )
        session.start_time = datetime_to_fit_timestamp(start_time)
        session.sport = sport
        session.sub_sport = sub_sport
        logger.info(
            f"Setting Session: sport={sport} ({type(sport)}), sub_sport={sub_sport} ({type(sub_sport)})"
        )
        session.total_elapsed_time = duration_to_seconds(activity.elapsed_time)
        session.total_timer_time = duration_to_seconds(activity.moving_time)
        session.total_distance = (
            float(activity.distance)
            if hasattr(activity, "distance") and activity.distance
            else None
        )
        session.total_calories = (
            int(activity.calories) if hasattr(activity, "calories") and activity.calories else None
        )

        # Average/max heart rate
        if heartrate:
            session.avg_heart_rate = int(sum(heartrate) / len(heartrate))
            session.max_heart_rate = int(max(heartrate))

        # Average/max cadence
        if cadence:
            session.avg_cadence = int(sum(cadence) / len(cadence))
            session.max_cadence = int(max(cadence))

        # Elevation
        if hasattr(activity, "total_elevation_gain") and activity.total_elevation_gain:
            session.total_ascent = int(activity.total_elevation_gain)

        builder.add(session)

        # 5. Activity Message
        activity_msg = ActivityMessage()
        activity_msg.timestamp = session.timestamp
        activity_msg.total_timer_time = session.total_timer_time
        activity_msg.num_sessions = 1
        activity_msg.type = Event.ACTIVITY
        activity_msg.event = Event.ACTIVITY
        activity_msg.event_type = EventType.STOP
        builder.add(activity_msg)

        # Build and return FIT file as bytes
        fit_file = builder.build()

        # Write to temporary file and read back as bytes
        with tempfile.NamedTemporaryFile(suffix=".fit", delete=False) as temp_file:
            fit_file.to_file(temp_file.name)
            temp_file.seek(0)
            with open(temp_file.name, "rb") as f:
                fit_data = f.read()

        import os

        os.unlink(temp_file.name)

        return fit_data
