"""
Sync service for orchestrating activity synchronization from Garmin to Strava.
"""

import logging
import os
import tempfile
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.models import ActivityFilter, SyncLog, User
from app.services.garmin_service import GarminService
from app.services.strava_service import StravaService
from app.utils.fit_utils import NO_GPS_MESSAGE, fit_file_has_gps
from app.utils.user_settings import get_allow_export_without_gps

logger = logging.getLogger(__name__)

class GarminToStravaSyncService:
    """Service for syncing activities from Garmin to Strava."""

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

    def should_sync_activity(
        self, activity_name: str, activity_type: Optional[str] = None
    ) -> tuple[bool, Optional[str]]:
        """
        Check if activity should be synced based on user filters.

        Args:
            activity_name: Name/title of the activity
            activity_type: Type of the activity (e.g., "running", "cycling")

        Returns:
            Tuple of (should_sync: bool, skip_reason: Optional[str])
        """
        # Get active filters for user
        filters = (
            self.db.query(ActivityFilter)
            .filter(ActivityFilter.user_id == self.user.id, ActivityFilter.active == True)
            .all()
        )

        # If no filters, sync all activities by default
        if not filters:
            return True, None

        # Determine if we have include filters (affects default behavior)
        has_include_filters = any(f.filter_type == "include" for f in filters)

        # Check each filter
        import re

        for filter_rule in filters:
            pattern = filter_rule.pattern
            matches = False

            # Determine which field to match against
            filter_field = getattr(filter_rule, "filter_field", "name")
            if filter_field == "type" and activity_type:
                match_value = activity_type
            else:
                match_value = activity_name

            if filter_rule.is_regex:
                # Regex matching
                try:
                    matches = bool(re.search(pattern, match_value, re.IGNORECASE))
                except re.error as e:
                    logger.error(f"Invalid regex pattern '{pattern}': {e}")
                    continue
            else:
                # Simple substring matching
                matches = pattern.lower() in match_value.lower()

            if matches:
                # If include filter matches, sync it
                if filter_rule.filter_type == "include":
                    return True, None
                # If exclude filter matches, don't sync it
                elif filter_rule.filter_type == "exclude":
                    skip_reason = f"Excluded by filter: {filter_field}={pattern}"
                    return False, skip_reason

        # Default behavior depends on filter types
        if has_include_filters:
            return False, "No include filters matched"
        return True, None

    def check_duplicate_sync(self, garmin_activity_id: str) -> Optional[SyncLog]:
        """
        Check if activity has already been synced in either direction.

        Args:
            garmin_activity_id: Garmin activity ID

        Returns:
            Existing SyncLog if found, None otherwise
        """
        # Check if already synced Garmin→Strava (any status - don't retry failed/skipped activities)
        existing_sync = (
            self.db.query(SyncLog)
            .filter(
                SyncLog.user_id == self.user.id,
                SyncLog.sync_direction == "garmin_to_strava",
                SyncLog.source_activity_id == str(garmin_activity_id),
            )
            .first()
        )

        if existing_sync:
            logger.info(
                f"Activity {garmin_activity_id} already in sync log with status '{existing_sync.status}'"
            )
            return existing_sync

        # Check if this Garmin activity was originally synced FROM Strava (prevent ping-pong)
        reverse_sync = (
            self.db.query(SyncLog)
            .filter(
                SyncLog.user_id == self.user.id,
                SyncLog.sync_direction == "strava_to_garmin",
                SyncLog.target_activity_id == str(garmin_activity_id),
                SyncLog.status == "success",
            )
            .first()
        )

        if reverse_sync:
            logger.info(
                f"Activity {garmin_activity_id} was originally from Strava (preventing ping-pong)"
            )
            return reverse_sync

        return None

    def sync_activity(
        self,
        garmin_activity_id: str,
        force_sync: bool = False,
        skip_date_filter: bool = False,
        activity_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Sync a single activity from Garmin to Strava.

        Args:
            garmin_activity_id: Garmin activity ID
            force_sync: If True, sync even if activity was already synced (for manual/retry)
            skip_date_filter: If True, don't apply 7-day lookback filter (for manual sync of old activities)
            activity_data: Optional pre-fetched activity data (from cron job) to avoid redundant API calls

        Returns:
            Dictionary with sync result
        """
        result = {"status": "failed", "garmin_activity_id": garmin_activity_id, "message": ""}

        # Check for duplicate sync (skip if force_sync is True)
        if not force_sync:
            existing_sync = self.check_duplicate_sync(garmin_activity_id)
            if existing_sync:
                result["status"] = "skipped"
                if existing_sync.sync_direction == "strava_to_garmin":
                    result["message"] = (
                        "Activity originally from Strava (preventing ping-pong sync)"
                    )
                else:
                    result["message"] = "Activity already synced to Strava"
                result["sync_log_id"] = existing_sync.id
                return result

        # Create sync log entry
        sync_log = SyncLog(
            user_id=self.user.id,
            sync_direction="garmin_to_strava",
            source_activity_id=str(garmin_activity_id),
            # Keep legacy fields for backward compatibility
            strava_activity_id="",  # Will be updated after successful upload
            status="pending",
        )
        self.db.add(sync_log)
        self.db.commit()

        temp_file_path = None

        try:
            # 1. Connect to Garmin
            logger.info(f"Connecting to Garmin Connect")
            if not self.garmin_service.connect(self.user):
                result["message"] = "Failed to connect to Garmin Connect"
                self._update_sync_log(sync_log, "failed", result["message"])
                return result

            # 2. Fetch activity details from Garmin (if not already provided)
            if activity_data:
                # Activity data already provided (e.g., from cron job)
                logger.info(f"Using pre-fetched activity data for {garmin_activity_id}")
                activity = activity_data
            else:
                # Need to fetch activity by ID (e.g., manual sync)
                logger.info(f"Fetching activity {garmin_activity_id} details from Garmin")
                activity = self.garmin_service.get_activity_by_id(garmin_activity_id)

                if not activity:
                    result["message"] = f"Activity {garmin_activity_id} not found in Garmin"
                    self._update_sync_log(sync_log, "failed", result["message"])
                    return result

            # Store activity metadata
            activity_name = activity.get("activityName", "Untitled")
            activity_type = activity.get("activityType", {}).get("typeKey", "")

            sync_log.activity_name = activity_name
            sync_log.activity_type = activity_type

            # Store debug data
            try:
                garmin_dict = {
                    "activityId": activity.get("activityId"),
                    "activityName": activity_name,
                    "activityType": activity_type,
                    "distance": activity.get("distance"),
                    "duration": activity.get("duration"),
                    "startTimeGMT": activity.get("startTimeGMT"),
                }
                sync_log.strava_data = garmin_dict  # Reusing the JSON field for Garmin data
                logger.info(f"Stored Garmin activity data: {activity_name}")
            except Exception as e:
                logger.error(f"Failed to serialize Garmin activity data: {e}", exc_info=True)
                sync_log.strava_data = {"error": str(e)}

            self.db.commit()

            # 3. Check if activity should be synced based on filters
            should_sync, skip_reason = self.should_sync_activity(activity_name, activity_type)
            if not should_sync:
                result["status"] = "skipped"
                result["message"] = (
                    skip_reason or f"Activity '{activity_name}' filtered out by user rules"
                )
                self._update_sync_log(sync_log, "skipped", result["message"])
                logger.info(result["message"])
                return result

            # 4. Download original FIT file from Garmin
            logger.info(f"Downloading original FIT file for activity {garmin_activity_id}")
            temp_file_path = tempfile.mktemp(suffix=".fit")
            fit_file_path = self.garmin_service.download_activity_original(
                garmin_activity_id, temp_file_path
            )

            if not fit_file_path or not os.path.exists(fit_file_path):
                result["message"] = "Failed to download FIT file from Garmin"
                self._update_sync_log(sync_log, "failed", result["message"])
                return result

            # Store FIT file info
            fit_size = os.path.getsize(fit_file_path)
            sync_log.gpx_data = f"FIT file downloaded: {fit_size} bytes"
            self.db.commit()

            # 4b. If FIT has no GPS, respect "Enable export without GPS" (same setting as Strava→Garmin)
            if not fit_file_has_gps(fit_file_path):
                if not get_allow_export_without_gps(self.user, self.db):
                    result["status"] = "skipped"
                    result["message"] = NO_GPS_MESSAGE
                    self._update_sync_log(sync_log, "skipped", result["message"])
                    logger.info(result["message"])
                    return result
                logger.info(
                    f"FIT has no GPS for activity {garmin_activity_id}; uploading anyway (export without GPS enabled)"
                )

            # 5. Upload to Strava
            logger.info(f"Uploading activity to Strava")
            upload_result = self.strava_service.upload_activity(
                user=self.user,
                file_path=fit_file_path,
                name=activity_name,
                description="Synced from Garmin",
            )

            if not upload_result or not upload_result.get("success"):
                error_msg = upload_result.get("error") if upload_result else "Unknown error"
                # Strava rejects no-GPS uploads; show friendly message
                err_lower = error_msg.lower()
                if "gps" in err_lower or "no gps" in err_lower or "gps data" in err_lower:
                    result["status"] = "skipped"
                    result["message"] = NO_GPS_MESSAGE
                    self._update_sync_log(sync_log, "skipped", result["message"])
                    return result
                result["message"] = f"Failed to upload activity to Strava: {error_msg}"
                self._update_sync_log(sync_log, "failed", result["message"])
                return result

            # 6. Success!
            strava_activity_id = upload_result.get("activity_id")

            result["status"] = "success"
            result["message"] = "Activity synced successfully"
            result["strava_activity_id"] = strava_activity_id

            self._update_sync_log(
                sync_log,
                "success",
                result["message"],
                strava_activity_id=str(strava_activity_id) if strava_activity_id else None,
            )

            logger.info(
                f"Successfully synced activity {garmin_activity_id} to Strava (ID: {strava_activity_id})"
            )

        except Exception as e:
            error_msg = f"Error syncing activity: {str(e)}"
            logger.error(error_msg, exc_info=True)
            result["message"] = error_msg

            # Rollback any failed transaction before attempting to update sync log
            try:
                self.db.rollback()
            except Exception as rollback_error:
                logger.error(f"Error during rollback: {rollback_error}")

            # Now update the sync log with the error
            try:
                self._update_sync_log(sync_log, "failed", error_msg)
            except Exception as update_error:
                logger.error(f"Error updating sync log: {update_error}")

        finally:
            # Clean up temporary file
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.unlink(temp_file_path)
                except Exception as e:
                    logger.error(f"Error deleting temporary file: {e}")

        return result

    def _update_sync_log(
        self, sync_log: SyncLog, status: str, message: str, strava_activity_id: Optional[str] = None
    ) -> None:
        """
        Update sync log with final status.

        Args:
            sync_log: SyncLog object
            status: Final status ("success", "failed", "skipped")
            message: Status message
            strava_activity_id: Strava activity ID if successful
        """
        sync_log.status = status
        sync_log.error_message = message if status != "success" else None
        sync_log.completed_at = datetime.utcnow()

        if strava_activity_id:
            sync_log.target_activity_id = strava_activity_id
            # Update legacy field for backward compatibility
            sync_log.strava_activity_id = strava_activity_id

        self.db.commit()
