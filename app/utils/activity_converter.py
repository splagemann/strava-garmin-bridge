"""
Utility for converting Strava activity data to Garmin-compatible formats.
"""
import gpxpy
import gpxpy.gpx
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional


class ActivityConverter:
    """Convert Strava activity data to GPX format for Garmin upload."""

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
        # Convert activity type to string (stravalib 2.x uses RelaxedActivityType)
        gpx_track.type = str(activity.type) if activity.type else None
        gpx.tracks.append(gpx_track)

        # Create segment
        gpx_segment = gpxpy.gpx.GPXTrackSegment()
        gpx_track.segments.append(gpx_segment)

        # Extract stream data - stravalib returns Stream objects, not dicts
        # Access the data attribute directly from Stream objects
        latlng = streams.get("latlng").data if "latlng" in streams and streams.get("latlng") else []
        altitude = streams.get("altitude").data if "altitude" in streams and streams.get("altitude") else []
        time_data = streams.get("time").data if "time" in streams and streams.get("time") else []
        heartrate = streams.get("heartrate").data if "heartrate" in streams and streams.get("heartrate") else []

        # Build track points
        for i, coords in enumerate(latlng):
            if len(coords) != 2:
                continue

            lat, lng = coords
            point = gpxpy.gpx.GPXTrackPoint(
                latitude=lat,
                longitude=lng,
                elevation=altitude[i] if i < len(altitude) else None,
                time=activity.start_date + timedelta(seconds=time_data[i]) if i < len(time_data) else None
            )

            # Add heart rate as extension if available
            if i < len(heartrate):
                # Note: GPX extensions for HR would need to be added here
                pass

            gpx_segment.points.append(point)

        return gpx.to_xml()

    @staticmethod
    def map_activity_type(strava_type: str) -> str:
        """
        Map Strava activity type to Garmin activity type.

        Args:
            strava_type: Strava activity type

        Returns:
            Garmin-compatible activity type
        """
        type_mapping = {
            "Run": "running",
            "Ride": "cycling",
            "VirtualRide": "cycling",
            "Swim": "swimming",
            "Walk": "walking",
            "Hike": "hiking",
            "AlpineSki": "skiing",
            "NordicSki": "cross_country_skiing",
            "Workout": "fitness_equipment",
            "WeightTraining": "strength_training",
            "Yoga": "yoga",
        }
        return type_mapping.get(strava_type, "other")
