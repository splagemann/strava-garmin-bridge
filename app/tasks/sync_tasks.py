"""
Celery tasks for activity synchronization.
"""
from celery import Task
from app.celery_app import celery_app
from app.database import SessionLocal
from app.models import User, SyncLog
from app.services.sync_service import SyncService
from app.services.strava_service import StravaService
import logging
from datetime import datetime, timedelta, timezone

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
            raise self.retry(exc=e, countdown=2 ** self.request.retries)
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
        results.append({
            "activity_id": activity_id,
            "task_id": task.id
        })

    return {
        "user_id": user_id,
        "queued": len(results),
        "tasks": results
    }


@celery_app.task(bind=True, base=DatabaseTask)
def poll_strava_activities_task(
    self,
    lookback_days: int = 7,
    max_activities_per_user: int = 100
):
    """
    Periodically poll Strava for new activities per user and sync them.

    Args:
        lookback_days: How far back to look for activities (in days)
        max_activities_per_user: Cap on activities fetched per user per run
    """
    logger.info(f"Starting periodic Strava poll (looking back {lookback_days} days)")
    lookback_start = datetime.now(timezone.utc) - timedelta(days=lookback_days)

    users = self.db.query(User).filter(
        User.is_active == True
    ).all()

    for user in users:
        # Only process users with both Strava and Garmin connected
        if not user.strava_auth or not user.garmin_auth:
            continue

        try:
            strava_service = StravaService(self.db)
            sync_service = SyncService(self.db, user)

            activities = strava_service.list_recent_activities(
                user,
                after=lookback_start,
                limit=max_activities_per_user
            )

            logger.info(f"User {user.id}: fetched {len(activities)} activities since {lookback_start.isoformat()}")

            for activity in activities:
                strava_id = str(getattr(activity, "id", None))
                if not strava_id:
                    continue

                # Skip if we've already synced/attempted this activity
                existing = self.db.query(SyncLog).filter(
                    SyncLog.user_id == user.id,
                    SyncLog.strava_activity_id == strava_id
                ).first()

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

                logger.info(f"Queueing sync for user {user.id} activity {strava_id} '{activity_name}'")
                sync_service.sync_activity(int(strava_id))

        except Exception as e:
            logger.error(f"Error polling Strava for user {user.id}: {e}", exc_info=True)
