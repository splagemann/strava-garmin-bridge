"""
Celery application configuration.
"""

from celery.schedules import crontab
from datetime import timedelta

from celery import Celery

from app.config import settings

# Create Celery app
celery_app = Celery(
    "strava_garmin_sync",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.tasks.sync_tasks"],
)

# Build beat schedule: Garmin → Strava poll only when enabled
_beat_schedule = {
    "poll-strava-activities-every-5-minutes": {
        "task": "app.tasks.sync_tasks.poll_strava_activities_task",
        "schedule": timedelta(minutes=5),
        "kwargs": {
            "lookback_days": 7,
            "max_activities_per_user": 100,
        },
    },
    "poll-withings-weight-every-30-minutes": {
        "task": "app.tasks.sync_tasks.poll_withings_weight_task",
        "schedule": timedelta(minutes=30),
    },
    "apply-workout-schedules-daily": {
        "task": "app.tasks.sync_tasks.apply_workout_schedules_task",
        # Run at 06:00 UTC every day — early enough that workouts are on the calendar
        # before most users start their day.
        "schedule": crontab(hour=6, minute=0),
    },
}
if settings.GARMIN_TO_STRAVA_SYNC_ENABLED:
    _beat_schedule["poll-garmin-activities-every-5-minutes"] = {
        "task": "app.tasks.sync_tasks.poll_garmin_activities_task",
        "schedule": timedelta(minutes=5),
        "kwargs": {
            "lookback_days": 7,
            "max_activities_per_user": 100,
        },
    }

# Configure Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,  # 5 minutes max per task
    task_soft_time_limit=240,  # 4 minutes soft limit
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=100,
    beat_schedule=_beat_schedule,
)
