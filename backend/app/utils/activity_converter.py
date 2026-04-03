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
from fit_tool.profile.messages.device_info_message import DeviceInfoMessage
from fit_tool.profile.messages.event_message import EventMessage
from fit_tool.profile.messages.file_id_message import FileIdMessage
from fit_tool.profile.messages.lap_message import LapMessage
from fit_tool.profile.messages.record_message import RecordMessage
from fit_tool.profile.messages.session_message import SessionMessage
from fit_tool.profile.profile_type import (
    Activity,
    Event,
    EventType,
    FileType,
    LapTrigger,
    Manufacturer,
    Sport,
    SourceType,
    SubSport,
    TimerTrigger,
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
    def strava_to_fit(
        activity: Any,
        streams: Dict[str, Any],
        device_settings: Optional[Dict[str, Any]] = None,
    ) -> bytes:
        """
        Convert Strava activity and streams to FIT format.

        Args:
            activity: Strava activity object
            streams: Dictionary of Stream objects from stravalib
            device_settings: Optional dict from admin: device_name, serial_number,
                manufacturer_id, software_version, product_id (strings). Maps to FIT product_name,
                serial_number, manufacturer, software_version, product. Timestamp and device_index set on DeviceInfo.

        Returns:
            FIT data as bytes
        """
        import logging

        logger = logging.getLogger(__name__)
        if streams is None:
            streams = {}
        device_settings = device_settings or {}

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

        # FIT local_timestamp: seconds since 00:00 Dec 31, 1989 UTC (used for local time in Activity message)
        _FIT_LOCAL_EPOCH = datetime(1989, 12, 31, 0, 0, 0, tzinfo=timezone.utc)

        def datetime_to_fit_local_timestamp(dt):
            """Convert datetime to FIT local_timestamp (seconds since 1989-12-31 00:00:00 UTC).
            Use activity's local start time so the stored value displays as the timezone the
            activity was in (e.g. Strava start_date_local); naive is treated as local-as-UTC
            so viewers showing UTC display the correct local time."""
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            else:
                dt = dt.astimezone(timezone.utc)
            return int((dt - _FIT_LOCAL_EPOCH).total_seconds())

        # Extract activity type
        activity_type_str = (
            ActivityConverter.extract_activity_type(activity.type) if activity.type else "Ride"
        )
        sport, sub_sport = ActivityConverter.map_activity_type_to_fit(activity_type_str)
        logger.info(f"Activity type: {activity_type_str} -> Sport: {sport}, SubSport: {sub_sport}")

        # Extract stream data (latlng may be missing for indoor/manual activities)
        latlng = []
        if streams:
            latlng = (
                streams.get("latlng").data if "latlng" in streams and streams.get("latlng") else []
            )
        altitude = (
            streams.get("altitude").data
            if streams and "altitude" in streams and streams.get("altitude")
            else []
        )
        time_data_raw = (
            streams.get("time").data
            if streams and "time" in streams and streams.get("time")
            else []
        )
        heartrate = (
            streams.get("heartrate").data
            if streams and "heartrate" in streams and streams.get("heartrate")
            else []
        )
        cadence = (
            streams.get("cadence").data
            if streams and "cadence" in streams and streams.get("cadence")
            else []
        )
        watts = (
            streams.get("watts").data
            if streams and "watts" in streams and streams.get("watts")
            else []
        )
        velocity_smooth = (
            streams.get("velocity_smooth").data
            if streams and "velocity_smooth" in streams and streams.get("velocity_smooth")
            else []
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

        # start_date_local = activity start time in the activity's local timezone (Strava may send "Z" but it's local)
        start_time_local = getattr(activity, "start_date_local", None)
        if start_time_local is not None and not isinstance(start_time_local, datetime):
            if isinstance(start_time_local, str):
                from dateutil import parser as _parser

                start_time_local = _parser.parse(start_time_local)
            else:
                start_time_local = None
        if start_time_local is None:
            start_time_local = start_time
        elif start_time_local.tzinfo is not None:
            start_time_local = start_time_local.replace(tzinfo=None)  # keep as naive local time

        # Test the timestamp conversion
        test_timestamp = datetime_to_fit_timestamp(start_time)
        logger.info(f"FIT timestamp (ms): {test_timestamp}")

        # Create FIT file builder
        builder = FitFileBuilder(auto_define=True, min_string_size=50)

        # 1. File ID Message (optionally use admin device_settings)
        file_id = FileIdMessage()
        file_id.type = FileType.ACTIVITY
        try:
            m = device_settings.get("manufacturer_id")
            file_id.manufacturer = (
                int(m) if (m is not None and str(m).strip()) else Manufacturer.STRAVA
            )
            p = device_settings.get("product_id")
            if p is not None and str(p).strip():
                try:
                    pv = int(str(p).strip())
                    file_id.product = max(0, min(65535, pv))
                except ValueError:
                    file_id.product = 0
            else:
                file_id.product = 0
            if device_settings.get("device_name"):
                file_id.product_name = str(device_settings["device_name"]).strip()[:20]
            s = device_settings.get("serial_number")
            if s is not None and str(s).strip():
                file_id.serial_number = int(s)
        except (ValueError, TypeError):
            file_id.manufacturer = Manufacturer.STRAVA
            file_id.product = 0
        file_id.time_created = datetime_to_fit_timestamp(start_time)
        builder.add(file_id)

        # 1a. Device Info Message (when device_settings provided; timestamp + device_index)
        if device_settings:
            try:
                dev = DeviceInfoMessage()
                dev.timestamp = datetime_to_fit_timestamp(start_time)
                dev.device_index = 0
                dev.source_type = SourceType.LOCAL  # 5 = local
                if device_settings.get("device_name"):
                    dev.product_name = str(device_settings["device_name"]).strip()[:20]
                p = device_settings.get("product_id")
                if p is not None and str(p).strip():
                    try:
                        pv = int(str(p).strip())
                        dev.product = max(0, min(65535, pv))
                    except ValueError:
                        pass
                s = device_settings.get("serial_number")
                if s is not None and str(s).strip():
                    dev.serial_number = int(s)
                m = device_settings.get("manufacturer_id")
                if m is not None and str(m).strip():
                    dev.manufacturer = int(m)
                sv = device_settings.get("software_version")
                if sv is not None and str(sv).strip():
                    # fit_tool DeviceInfo has software_version with scale=100: encoded = round(value * 100) as UINT16 [0, 65535].
                    # Pass semantic version (e.g. 20.29); framework multiplies by 100. Max semantic value = 655.35.
                    sv_str = str(sv).strip()
                    try:
                        val = float(sv_str)
                        if 0 <= val <= 655.35:
                            dev.software_version = val
                    except (ValueError, TypeError):
                        pass
                builder.add(dev)
            except (ValueError, TypeError):
                pass

        # 1b. Event: timer start at activity start time (data=manual)
        timer_start_evt = EventMessage()
        timer_start_evt.timestamp = datetime_to_fit_timestamp(start_time)
        timer_start_evt.event = Event.TIMER
        timer_start_evt.event_type = EventType.START
        timer_start_evt.timer_trigger = TimerTrigger.MANUAL
        timer_start_evt.event_group = 0
        builder.add(timer_start_evt)

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

            # Power (watts)
            if i < len(watts):
                record.power = int(watts[i])

            # Speed (m/s, Strava velocity_smooth)
            if i < len(velocity_smooth):
                record.speed = float(velocity_smooth[i])

            # Distance (meters)
            if hasattr(activity, "distance") and activity.distance and len(latlng) > 0:
                # Approximate distance based on position in stream
                record.distance = float(activity.distance) * (i / len(latlng))

            records.append(record)
            builder.add(record)

        # 2b. No GPS but we have time + HR/cadence/watts/velocity_smooth: create record messages
        if not records and (time_data or heartrate or cadence or watts or velocity_smooth):
            n_points = (
                len(time_data)
                if time_data
                else max(
                    len(heartrate) if heartrate else 0,
                    len(cadence) if cadence else 0,
                    len(watts) if watts else 0,
                    len(velocity_smooth) if velocity_smooth else 0,
                    1,
                )
            )
            total_dist = (
                float(activity.distance)
                if hasattr(activity, "distance") and activity.distance
                else None
            )
            for i in range(n_points):
                record = RecordMessage()
                if time_data and i < len(time_data):
                    point_time = start_time + timedelta(seconds=time_data[i])
                    record.timestamp = datetime_to_fit_timestamp(point_time)
                else:
                    point_time = start_time + timedelta(seconds=i)
                    record.timestamp = datetime_to_fit_timestamp(point_time)
                if i < len(heartrate):
                    record.heart_rate = int(heartrate[i])
                if i < len(cadence):
                    record.cadence = int(cadence[i])
                if i < len(watts):
                    record.power = int(watts[i])
                if i < len(velocity_smooth):
                    record.speed = float(velocity_smooth[i])
                if total_dist is not None and n_points > 0:
                    record.distance = total_dist * (i / n_points)
                records.append(record)
                builder.add(record)

        # 3. Lap Message (required for Garmin; create from records or from activity summary)
        lap = LapMessage()
        if records:
            lap.timestamp = (
                records[-1].timestamp
                if records[-1].timestamp
                else datetime_to_fit_timestamp(start_time)
            )
        else:
            # No GPS: use start_time + duration for end timestamp
            elapsed = duration_to_seconds(activity.elapsed_time) or 0
            end_time = start_time
            if end_time.tzinfo is None:
                end_time = end_time.replace(tzinfo=timezone.utc)
            end_time = end_time + timedelta(seconds=elapsed)
            lap.timestamp = datetime_to_fit_timestamp(end_time)

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
            int(activity.calories) if hasattr(activity, "calories") and activity.calories else None
        )

        # Average/max heart rate
        if heartrate:
            lap.avg_heart_rate = int(sum(heartrate) / len(heartrate))
            lap.max_heart_rate = int(max(heartrate))

        # Average/max cadence
        if cadence:
            lap.avg_cadence = int(sum(cadence) / len(cadence))
            lap.max_cadence = int(max(cadence))

        # Average/max power (watts)
        if watts:
            lap.avg_power = int(sum(watts) / len(watts))
            lap.max_power = int(max(watts))

        # Elevation
        if hasattr(activity, "total_elevation_gain") and activity.total_elevation_gain:
            lap.total_ascent = int(activity.total_elevation_gain)

        lap.lap_trigger = LapTrigger.SESSION_END
        builder.add(lap)

        # 4. Session Message
        session = SessionMessage()
        if records and records[-1].timestamp:
            session.timestamp = records[-1].timestamp
        else:
            session.timestamp = lap.timestamp  # use same end time as lap (no-GPS case)
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

        # Average/max power (watts)
        if watts:
            session.avg_power = int(sum(watts) / len(watts))
            session.max_power = int(max(watts))

        # Normalized power (Strava weighted_average_watts) when available
        if hasattr(activity, "weighted_average_watts") and activity.weighted_average_watts:
            session.normalized_power = int(activity.weighted_average_watts)

        # Elevation
        if hasattr(activity, "total_elevation_gain") and activity.total_elevation_gain:
            session.total_ascent = int(activity.total_elevation_gain)

        builder.add(session)

        # 5. Activity Message: event=ACTIVITY, event_type=STOP (stop is on Activity, not a separate Event)
        # local_timestamp = seconds since 1989-12-31 00:00:00 in local time (use start_date_local, no timezone field)
        elapsed_secs = duration_to_seconds(activity.elapsed_time) or 0
        end_time_utc = (
            start_time if start_time.tzinfo else start_time.replace(tzinfo=timezone.utc)
        ) + timedelta(seconds=elapsed_secs)
        if start_time_local is not None:
            # start_date_local is local time; end in local = start_local + elapsed
            end_time_local_naive = start_time_local + timedelta(seconds=elapsed_secs)
            epoch_local_naive = datetime(1989, 12, 31, 0, 0, 0)
            local_ts = int((end_time_local_naive - epoch_local_naive).total_seconds())
        else:
            local_ts = datetime_to_fit_local_timestamp(end_time_utc)
        local_ts = max(0, min(0xFFFFFFFF, local_ts))  # FIT local_timestamp is uint32
        activity_msg = ActivityMessage()
        activity_msg.timestamp = session.timestamp
        activity_msg.total_timer_time = session.total_timer_time
        activity_msg.num_sessions = 1
        activity_msg.type = Activity.AUTO_MULTI_SPORT
        activity_msg.event = Event.ACTIVITY
        activity_msg.event_type = EventType.STOP
        activity_msg.local_timestamp = local_ts
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
