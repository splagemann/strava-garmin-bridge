"""
Database models.
"""

from app.models.auth import GarminAuth, StravaAuth, WithingsAuth
from app.models.filter import ActivityFilter
from app.models.scheduled_workout_instance import ScheduledWorkoutInstance
from app.models.sync_log import SyncLog
from app.models.user import User
from app.models.user_settings import UserSettings
from app.models.workout_schedule import WorkoutSchedule

__all__ = [
    "User",
    "UserSettings",
    "StravaAuth",
    "GarminAuth",
    "WithingsAuth",
    "ActivityFilter",
    "SyncLog",
    "WorkoutSchedule",
    "ScheduledWorkoutInstance",
]
