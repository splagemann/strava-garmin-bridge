"""
Celery tasks for activity synchronization.
"""
from celery import Task
from app.celery_app import celery_app
from app.database import SessionLocal
from app.models import User
from app.services.sync_service import SyncService
import logging

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
