"""
Sync service for orchestrating activity synchronization between Strava and Garmin.
"""
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional
from datetime import datetime
import re
import tempfile
import os
import logging

from app.models import User, ActivityFilter, SyncLog
from app.services.strava_service import StravaService
from app.services.garmin_service import GarminService
from app.utils.activity_converter import ActivityConverter

logger = logging.getLogger(__name__)


class SyncService:
    """Service for syncing activities from Strava to Garmin."""

    def __init__(self, db: Session, user: User):
        """
        Initialize sync service.

        Args:
            db: Database session
            user: User object
        """
        self.db = db
        self.user = user
        self.strava_service = StravaService(db)
        self.garmin_service = GarminService(db)
        self.converter = ActivityConverter()

    def should_sync_activity(self, activity_name: str) -> bool:
        """
        Check if activity should be synced based on user filters.

        Args:
            activity_name: Name/title of the activity

        Returns:
            True if activity should be synced, False otherwise
        """
        # Get active filters for user
        filters = self.db.query(ActivityFilter).filter(
            ActivityFilter.user_id == self.user.id,
            ActivityFilter.active == True
        ).all()

        # If no filters, sync all activities by default
        if not filters:
            return True

        # Check each filter
        for filter_rule in filters:
            pattern = filter_rule.pattern
            matches = False

            if filter_rule.is_regex:
                # Regex matching
                try:
                    matches = bool(re.search(pattern, activity_name, re.IGNORECASE))
                except re.error as e:
                    logger.error(f"Invalid regex pattern '{pattern}': {e}")
                    continue
            else:
                # Simple substring matching
                matches = pattern.lower() in activity_name.lower()

            if matches:
                # If include filter matches, sync it
                if filter_rule.filter_type == "include":
                    return True
                # If exclude filter matches, don't sync it
                elif filter_rule.filter_type == "exclude":
                    return False

        # Default behavior: sync if no exclude filters matched
        return True

    def sync_activity(self, strava_activity_id: int) -> Dict[str, Any]:
        """
        Sync a single activity from Strava to Garmin.

        Args:
            strava_activity_id: Strava activity ID

        Returns:
            Dictionary with sync result
        """
        result = {
            "status": "failed",
            "strava_activity_id": strava_activity_id,
            "message": ""
        }

        # Create sync log entry
        sync_log = SyncLog(
            user_id=self.user.id,
            strava_activity_id=str(strava_activity_id),
            status="pending"
        )
        self.db.add(sync_log)
        self.db.commit()

        try:
            # 1. Fetch activity from Strava
            logger.info(f"Fetching activity {strava_activity_id} from Strava")
            activity = self.strava_service.get_activity(self.user, strava_activity_id)

            if not activity:
                result["message"] = "Failed to fetch activity from Strava"
                self._update_sync_log(sync_log, "failed", result["message"])
                return result

            # Store activity metadata
            sync_log.activity_name = activity.name
            # Convert activity type to string (stravalib 2.x uses RelaxedActivityType)
            sync_log.activity_type = str(activity.type) if activity.type else None
            self.db.commit()

            # 2. Check if activity should be synced based on filters
            if not self.should_sync_activity(activity.name):
                result["status"] = "skipped"
                result["message"] = f"Activity '{activity.name}' filtered out by user rules"
                self._update_sync_log(sync_log, "skipped", result["message"])
                logger.info(result["message"])
                return result

            # 3. Fetch activity streams
            logger.info(f"Fetching activity streams for {strava_activity_id}")
            streams = self.strava_service.get_activity_streams(self.user, strava_activity_id)

            if not streams or "latlng" not in streams:
                result["message"] = "No GPS data available for this activity"
                self._update_sync_log(sync_log, "failed", result["message"])
                return result

            # 4. Convert to GPX format
            logger.info(f"Converting activity to GPX format")
            gpx_data = self.converter.strava_to_gpx(activity, streams)

            # 5. Save to temporary file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.gpx', delete=False) as temp_file:
                temp_file.write(gpx_data)
                temp_file_path = temp_file.name

            try:
                # 6. Connect to Garmin
                logger.info(f"Connecting to Garmin Connect")
                if not self.garmin_service.connect(self.user):
                    result["message"] = "Failed to connect to Garmin Connect"
                    self._update_sync_log(sync_log, "failed", result["message"])
                    return result

                # 7. Upload to Garmin
                logger.info(f"Uploading activity to Garmin Connect")
                upload_response = self.garmin_service.upload_activity(temp_file_path, ".gpx")

                if not upload_response:
                    result["message"] = "Failed to upload activity to Garmin"
                    self._update_sync_log(sync_log, "failed", result["message"])
                    return result

                # 8. Success!
                # Try different possible keys for activity ID
                garmin_activity_id = (
                    upload_response.get("activity_id") or
                    upload_response.get("activityId") or
                    upload_response.get("id") or
                    upload_response.get("activityID")
                )

                logger.info(f"Upload response keys: {list(upload_response.keys())}")
                logger.info(f"Extracted activity ID: {garmin_activity_id}")

                result["status"] = "success"
                result["message"] = "Activity synced successfully"
                result["garmin_activity_id"] = garmin_activity_id

                self._update_sync_log(
                    sync_log,
                    "success",
                    result["message"],
                    garmin_activity_id=str(garmin_activity_id) if garmin_activity_id else None
                )

                logger.info(f"Successfully synced activity {strava_activity_id} to Garmin")

            finally:
                # Clean up temporary file
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)

        except Exception as e:
            error_msg = f"Error syncing activity: {str(e)}"
            logger.error(error_msg, exc_info=True)
            result["message"] = error_msg
            self._update_sync_log(sync_log, "failed", error_msg)

        return result

    def _update_sync_log(
        self,
        sync_log: SyncLog,
        status: str,
        message: str,
        garmin_activity_id: Optional[str] = None
    ):
        """Update sync log with result."""
        sync_log.status = status
        sync_log.error_message = message if status == "failed" else None
        sync_log.completed_at = datetime.utcnow()

        if garmin_activity_id:
            sync_log.garmin_activity_id = garmin_activity_id

        self.db.commit()
