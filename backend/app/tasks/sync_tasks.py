"""
Celery tasks for activity synchronization.
"""

import logging
from datetime import datetime, timedelta, timezone

from celery import Task

from app.celery_app import celery_app
from app.database import SessionLocal
from app.models import SyncLog, User
from app.models.workout_schedule import WorkoutSchedule
from app.services.garmin_service import GarminService
from app.services.garmin_to_strava_sync_service import GarminToStravaSyncService
from app.services.strava_service import StravaService
from app.services.sync_service import SyncService
from app.services.weight_sync_service import WeightSyncService
from app.services.workout_schedule_service import WorkoutScheduleService
from app.utils.user_settings import (
    KEY_LAST_GARMIN_POLL_AT,
    KEY_LAST_STRAVA_POLL_AT,
    get_garmin_to_strava_sync_enabled,
    get_last_poll_at,
    get_sync_schedule_minutes,
    set_last_poll_at,
)

logger = logging.getLogger(__name__)


class DatabaseTask(Task):
    """Base task that creates and closes database sessions."""

    _db = None

    @property
    def db(self):
        if self._db is None:
            self._db = SessionLocal()
        return self._db

    def after_return(self, *args, **kwargs):
        if self._db is not None:
            self._db.close()
            self._db = None


@celery_app.task(bind=True, base=DatabaseTask, max_retries=3, default_retry_delay=60)
def sync_activity_task(self, user_id: int, strava_activity_id: int):
    """
    Celery task to sync a single activity from Strava to Garmin.

    Args:
        user_id: User ID
        strava_activity_id: Strava activity ID

    Returns:
        Dictionary with sync result
    """
    logger.info(f"Starting sync task for activity {strava_activity_id}, user {user_id}")

    try:
        # Get user
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            logger.error(f"User {user_id} not found")
            return {"error": "User not found"}

        # Check if user has required auth
        if not user.strava_auth:
            logger.error(f"User {user_id} has no Strava auth")
            return {"error": "Strava not connected"}

        if not user.garmin_auth:
            logger.error(f"User {user_id} has no Garmin auth")
            return {"error": "Garmin not connected"}

        # Perform sync
        sync_service = SyncService(self.db, user)
        result = sync_service.sync_activity(strava_activity_id)

        logger.info(f"Sync task completed for activity {strava_activity_id}: {result['status']}")

        return result

    except Exception as e:
        logger.error(f"Error in sync task: {e}", exc_info=True)

        # Retry with exponential backoff
        try:
            raise self.retry(exc=e, countdown=2**self.request.retries)
        except self.MaxRetriesExceededError:
            logger.error(f"Max retries exceeded for activity {strava_activity_id}")
            return {"error": f"Max retries exceeded: {str(e)}"}


@celery_app.task(bind=True, base=DatabaseTask)
def sync_user_activities_task(self, user_id: int, activity_ids: list):
    """
    Celery task to sync multiple activities for a user.

    Args:
        user_id: User ID
        activity_ids: List of Strava activity IDs

    Returns:
        Dictionary with sync results
    """
    logger.info(f"Starting batch sync for user {user_id}: {len(activity_ids)} activities")

    results = []
    for activity_id in activity_ids:
        # Queue individual sync tasks
        task = sync_activity_task.delay(user_id, activity_id)
        results.append({"activity_id": activity_id, "task_id": task.id})

    return {"user_id": user_id, "queued": len(results), "tasks": results}


@celery_app.task(bind=True, base=DatabaseTask)
def poll_strava_activities_task(self, lookback_days: int = 7, max_activities_per_user: int = 100):
    """
    Periodically poll Strava for new activities per user and sync them.

    Args:
        lookback_days: How far back to look for activities (in days)
        max_activities_per_user: Cap on activities fetched per user per run
    """
    logger.info(f"Starting periodic Strava poll (looking back {lookback_days} days)")
    lookback_start = datetime.now(timezone.utc) - timedelta(days=lookback_days)

    users = self.db.query(User).filter(User.is_active == True).all()
    now = datetime.now(timezone.utc)

    for user in users:
        # Only process users with both Strava and Garmin connected
        if not user.strava_auth or not user.garmin_auth:
            continue

        # Skip if user's sync schedule interval has not elapsed since last poll
        interval_minutes = get_sync_schedule_minutes(self.db, user.id)
        last_at = get_last_poll_at(self.db, user.id, KEY_LAST_STRAVA_POLL_AT)
        if last_at is not None and (last_at + timedelta(minutes=interval_minutes)) > now:
            continue

        set_last_poll_at(self.db, user.id, KEY_LAST_STRAVA_POLL_AT, now)
        self.db.commit()

        try:
            strava_service = StravaService(self.db)
            sync_service = SyncService(self.db, user)

            activities = strava_service.list_recent_activities(
                user, after=lookback_start, limit=max_activities_per_user
            )

            logger.info(
                f"User {user.id}: fetched {len(activities)} activities since {lookback_start.isoformat()}"
            )

            for activity in activities:
                strava_id = str(getattr(activity, "id", None))
                if not strava_id:
                    continue

                # Skip if we've already synced/attempted this activity
                existing = (
                    self.db.query(SyncLog)
                    .filter(SyncLog.user_id == user.id, SyncLog.strava_activity_id == strava_id)
                    .first()
                )

                if existing:
                    continue

                # Apply user's activity filters before syncing
                activity_name = str(getattr(activity, "name", ""))
                activity_type = None
                if hasattr(activity, "type") and activity.type:
                    # Extract activity type string (handles stravalib's format)
                    from app.utils.activity_converter import ActivityConverter

                    converter = ActivityConverter()
                    activity_type = converter.extract_activity_type(activity.type)

                # Check if activity matches user's filters
                if not sync_service.should_sync_activity(activity_name, activity_type):
                    logger.info(
                        f"Skipping activity {strava_id} '{activity_name}' (type: {activity_type}) "
                        f"for user {user.id} - doesn't match filters"
                    )
                    continue

                logger.info(
                    f"Queueing sync for user {user.id} activity {strava_id} '{activity_name}'"
                )
                sync_service.sync_activity(int(strava_id))

        except Exception as e:
            logger.error(f"Error polling Strava for user {user.id}: {e}", exc_info=True)


@celery_app.task(bind=True, base=DatabaseTask)
def poll_garmin_activities_task(self, lookback_days: int = 7, max_activities_per_user: int = 100):
    """
    Periodically poll Garmin for new activities per user and sync them to Strava.

    Args:
        lookback_days: How far back to look for activities (in days)
        max_activities_per_user: Cap on activities fetched per user per run
    """
    logger.info(f"Starting periodic Garmin poll (looking back {lookback_days} days)")
    lookback_start = datetime.now(timezone.utc) - timedelta(days=lookback_days)

    users = self.db.query(User).filter(User.is_active == True).all()
    now = datetime.now(timezone.utc)

    for user in users:
        # Only process users with both Strava and Garmin connected
        if not user.strava_auth or not user.garmin_auth:
            continue

        if not get_garmin_to_strava_sync_enabled(user, self.db):
            continue

        # Skip if user's sync schedule interval has not elapsed since last Garmin poll
        interval_minutes = get_sync_schedule_minutes(self.db, user.id)
        last_at = get_last_poll_at(self.db, user.id, KEY_LAST_GARMIN_POLL_AT)
        if last_at is not None and (last_at + timedelta(minutes=interval_minutes)) > now:
            continue

        set_last_poll_at(self.db, user.id, KEY_LAST_GARMIN_POLL_AT, now)
        self.db.commit()

        try:
            garmin_service = GarminService(self.db)
            sync_service = GarminToStravaSyncService(self.db, user)

            # Connect to Garmin
            if not garmin_service.connect(user):
                logger.error(f"Failed to connect to Garmin for user {user.id}")
                continue

            # Fetch recent activities from Garmin
            activities = garmin_service.get_activities(
                start_date=lookback_start.strftime("%Y-%m-%d"), limit=max_activities_per_user
            )

            if not activities:
                logger.info(f"User {user.id}: no Garmin activities found")
                continue

            logger.info(
                f"User {user.id}: fetched {len(activities)} Garmin activities from last {lookback_days} days"
            )

            for activity in activities:
                garmin_id = str(activity.get("activityId"))
                if not garmin_id:
                    continue

                # Double-check activity date as a safety measure
                # (Garmin API should already filter, but we verify here)
                # Try different date fields that Garmin might provide
                activity_date_str = (
                    activity.get("startTimeGMT")
                    or activity.get("startTimeLocal")
                    or activity.get("beginTimestamp")
                )
                if not activity_date_str:
                    # If no date field found, skip the activity to be safe
                    logger.warning(
                        f"Skipping Garmin activity {garmin_id} - no date field found (tried startTimeGMT, startTimeLocal, beginTimestamp)"
                    )
                    continue

                try:
                    # Parse datetime string from Garmin (handles multiple formats)
                    if "T" in activity_date_str or "Z" in activity_date_str:
                        # ISO format with timezone: '2025-11-21T14:21:56Z'
                        activity_date = datetime.fromisoformat(
                            activity_date_str.replace("Z", "+00:00")
                        )
                    else:
                        # Simple format without timezone: '2025-11-21 14:21:56'
                        # Assume UTC since Garmin stores times in UTC
                        activity_date = datetime.strptime(activity_date_str, "%Y-%m-%d %H:%M:%S")
                        activity_date = activity_date.replace(tzinfo=timezone.utc)

                    # Calculate age in days for logging
                    age_days = (datetime.now(timezone.utc) - activity_date).days

                    # Safety check: skip if somehow older than lookback window
                    if activity_date < lookback_start:
                        logger.warning(
                            f"Skipping old Garmin activity {garmin_id} from {activity_date_str} ({age_days} days old, limit is {lookback_days} days) - should have been filtered by API"
                        )
                        continue

                    logger.debug(f"Processing Garmin activity {garmin_id} ({age_days} days old)")
                except (ValueError, TypeError) as e:
                    # If date parsing fails, skip the activity to be safe
                    logger.warning(
                        f"Skipping Garmin activity {garmin_id} - could not parse date '{activity_date_str}': {e}"
                    )
                    continue

                # Skip if we've already synced this activity (either direction)
                existing_sync = sync_service.check_duplicate_sync(garmin_id)
                if existing_sync:
                    continue

                # Apply user's activity filters before syncing
                activity_name = activity.get("activityName", "Untitled")
                activity_type = activity.get("activityType", {}).get("typeKey", "")

                # Check if activity matches user's filters
                should_sync, skip_reason = sync_service.should_sync_activity(
                    activity_name, activity_type
                )
                if not should_sync:
                    logger.info(
                        f"Skipping Garmin activity {garmin_id} '{activity_name}' (type: {activity_type}) "
                        f"for user {user.id} - {skip_reason}"
                    )
                    continue

                logger.info(
                    f"Queueing Garmin→Strava sync for user {user.id} activity {garmin_id} '{activity_name}'"
                )
                # Pass the activity data to avoid redundant API call
                sync_service.sync_activity(garmin_id, activity_data=activity)

        except Exception as e:
            logger.error(f"Error polling Garmin for user {user.id}: {e}", exc_info=True)


@celery_app.task(bind=True, base=DatabaseTask)
def apply_workout_schedules_task(self):
    """
    Daily task: push each user's active workout schedules whose weekday matches today to Garmin.
    Runs once per day so workouts appear on the calendar without manual intervention.
    """
    from datetime import date

    today = date.today()
    day_of_week = today.weekday()  # 0=Mon … 6=Sun
    logger.info(f"Applying workout schedules for {today.isoformat()} (weekday {day_of_week})")

    # Find users who have at least one active schedule for today's weekday
    schedules_today = (
        self.db.query(WorkoutSchedule)
        .filter(WorkoutSchedule.is_active.is_(True))
        .all()
    )
    user_ids = {
        s.user_id for s in schedules_today if day_of_week in (s.days_of_week or [])
    }

    if not user_ids:
        logger.info("No active workout schedules match today — nothing to push")
        return

    users = self.db.query(User).filter(User.id.in_(user_ids), User.is_active == True).all()

    for user in users:
        if not user.garmin_auth:
            continue
        try:
            svc = WorkoutScheduleService(self.db, user)
            results = svc.apply_for_date(today)
            success = sum(1 for r in results if r.get("success"))
            failed = len(results) - success
            logger.info(
                f"Workout schedule task for user {user.id} on {today}: "
                f"{success} succeeded, {failed} failed"
            )
        except Exception as exc:
            logger.error(
                f"Workout schedule task failed for user {user.id}: {exc}", exc_info=True
            )


@celery_app.task(bind=True, base=DatabaseTask)
def poll_withings_weight_task(self):
    """
    Periodically poll Withings for new weight measurements and sync to Garmin.
    """
    logger.info("Starting periodic Withings weight poll")

    users = self.db.query(User).filter(User.is_active == True).all()

    for user in users:
        # Only process users with both Withings and Garmin connected
        if not user.withings_auth or not user.garmin_auth:
            continue

        try:
            sync_service = WeightSyncService(self.db)
            sync_service.sync_weight(user)
        except Exception as e:
            logger.error(f"Error syncing weight for user {user.id}: {e}", exc_info=True)
