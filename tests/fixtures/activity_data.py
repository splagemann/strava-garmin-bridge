"""
Mock activity data for testing.
"""
from datetime import datetime, timedelta


class StravaActivityFactory:
    """Factory for creating mock Strava activities."""

    @staticmethod
    def create(
        activity_id: int = 1234567890,
        name: str = "Morning Run",
        activity_type: str = "Run",
        distance: float = 5000.0,
        external_id: str = None,
        start_date: datetime = None,
    ):
        """Create a mock Strava activity."""
        if start_date is None:
            start_date = datetime.utcnow()

        return {
            "id": activity_id,
            "name": name,
            "type": activity_type,
            "start_date": start_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "start_date_local": start_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "distance": distance,
            "moving_time": 1800,
            "elapsed_time": 1900,
            "total_elevation_gain": 50.0,
            "average_speed": 2.78,
            "max_speed": 3.5,
            "average_heartrate": 145.0,
            "max_heartrate": 165.0,
            "calories": 350.0,
            "external_id": external_id,
        }

    @staticmethod
    def create_from_garmin(garmin_id: int = 9876543210):
        """Create a Strava activity that originated from Garmin."""
        return StravaActivityFactory.create(
            activity_id=1234567890,
            name="Garmin Synced Activity",
            external_id=f"garmin_push_{garmin_id}",
        )

    @staticmethod
    def create_batch(count: int = 5):
        """Create multiple mock activities."""
        activities = []
        base_date = datetime.utcnow()
        for i in range(count):
            activities.append(
                StravaActivityFactory.create(
                    activity_id=1000000000 + i,
                    name=f"Activity {i+1}",
                    start_date=base_date - timedelta(days=i),
                )
            )
        return activities


class GarminActivityFactory:
    """Factory for creating mock Garmin activities."""

    @staticmethod
    def create(
        activity_id: int = 9876543210,
        name: str = "Evening Ride",
        activity_type: str = "cycling",
        distance: float = 20000.0,
        start_time: datetime = None,
        date_format: str = "iso",  # 'iso' or 'simple'
    ):
        """Create a mock Garmin activity."""
        if start_time is None:
            start_time = datetime.utcnow()

        # Garmin API returns different date formats
        if date_format == "iso":
            start_time_str = start_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        else:  # simple format from get_activities_by_date
            start_time_str = start_time.strftime("%Y-%m-%d %H:%M:%S")

        return {
            "activityId": activity_id,
            "activityName": name,
            "activityType": {"typeKey": activity_type, "typeId": 1},
            "startTimeGMT": start_time_str,
            "startTimeLocal": start_time_str,
            "distance": distance,
            "duration": 3600.0,
            "elevationGain": 150.0,
            "elevationLoss": 145.0,
            "averageSpeed": 5.56,
            "maxSpeed": 8.33,
            "averageHR": 135.0,
            "maxHR": 160.0,
            "calories": 450.0,
        }

    @staticmethod
    def create_from_strava(strava_id: int = 1234567890):
        """Create a Garmin activity that originated from Strava."""
        return GarminActivityFactory.create(
            activity_id=9876543210,
            name=f"Strava Activity {strava_id}",
        )

    @staticmethod
    def create_batch(count: int = 5, date_format: str = "iso"):
        """Create multiple mock activities."""
        activities = []
        base_date = datetime.utcnow()
        for i in range(count):
            activities.append(
                GarminActivityFactory.create(
                    activity_id=9000000000 + i,
                    name=f"Garmin Activity {i+1}",
                    start_time=base_date - timedelta(days=i),
                    date_format=date_format,
                )
            )
        return activities


# Pre-defined test scenarios
TEST_ACTIVITIES = {
    "strava_run": StravaActivityFactory.create(
        activity_id=1111111111,
        name="Morning Run",
        activity_type="Run",
        distance=5000.0,
    ),
    "strava_ride": StravaActivityFactory.create(
        activity_id=2222222222,
        name="Evening Ride",
        activity_type="Ride",
        distance=20000.0,
    ),
    "strava_from_garmin": StravaActivityFactory.create_from_garmin(9999999999),
    "garmin_cycling": GarminActivityFactory.create(
        activity_id=3333333333,
        name="Cycling Workout",
        activity_type="cycling",
        distance=15000.0,
    ),
    "garmin_running": GarminActivityFactory.create(
        activity_id=4444444444,
        name="Running Workout",
        activity_type="running",
        distance=8000.0,
    ),
    "garmin_simple_date": GarminActivityFactory.create(
        activity_id=5555555555,
        name="Walk",
        activity_type="walking",
        date_format="simple",
    ),
}
