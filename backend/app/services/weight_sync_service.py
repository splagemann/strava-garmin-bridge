"""
Service for syncing weight data from Withings to Garmin.
"""

import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.models import User, SyncLog
from app.services.garmin_service import GarminService
from app.services.withings_service import WithingsService

logger = logging.getLogger(__name__)


class WeightSyncService:
    """Service for syncing weight measurements."""

    def __init__(self, db: Session):
        """
        Initialize weight sync service.

        Args:
            db: Database session
        """
        self.db = db
        self.withings_service = WithingsService(db)
        self.garmin_service = GarminService(db)

    def sync_weight(self, user: User) -> bool:
        """
        Sync recent weights from Withings to Garmin (last 365 days).

        Args:
            user: User object

        Returns:
            True if sync process completed (even if individual items failed or were skipped), False if critical error
        """
        try:
            # 1. Check if user is connected to both
            if not user.withings_auth:
                logger.info(f"User {user.id} not connected to Withings, skipping weight sync")
                return False
            
            if not user.garmin_auth:
                logger.info(f"User {user.id} not connected to Garmin, skipping weight sync")
                return False

            # 2. Get recent weights from Withings
            measurements = self.withings_service.get_recent_weights(user)
            if not measurements:
                logger.info(f"No weight data found for user {user.id}")
                return True # No data is not an error

            # 3. Connect to Garmin (once for all uploads)
            if not self.garmin_service.connect(user):
                logger.error(f"Failed to connect to Garmin for user {user.id}")
                # Log failure for the first measurement just to record the attempt? 
                # Or just return False. We can't log for every single one if we can't connect.
                # Let's log a generic failure or just return.
                return False

            # 4. Iterate and sync
            synced_count = 0
            skipped_count = 0
            failed_count = 0
            
            for measurement in measurements:
                weight_kg = measurement["weight"]
                timestamp = measurement["date"]
                
                # We use source_activity_id to store the unique ID (timestamp in this case)
                source_id = str(int(timestamp.timestamp()))
                
                # Check if already synced
                existing_log = self.db.query(SyncLog).filter(
                    SyncLog.user_id == user.id,
                    SyncLog.activity_type == "weight",
                    SyncLog.source_activity_id == source_id
                ).first()

                if existing_log and existing_log.status == "success":
                    skipped_count += 1
                    continue

                # Upload to Garmin
                success = self.garmin_service.upload_weight(weight_kg, timestamp)
                
                if success:
                    logger.info(f"Successfully synced weight {weight_kg}kg from {timestamp} for user {user.id}")
                    self._log_sync(user, "success", source_id, timestamp)
                    synced_count += 1
                else:
                    logger.error(f"Failed to upload weight for user {user.id} at {timestamp}")
                    self._log_sync(user, "failed", source_id, timestamp, "Upload failed")
                    failed_count += 1
            
            logger.info(f"Weight sync complete for user {user.id}: {synced_count} synced, {skipped_count} skipped, {failed_count} failed")
            return True

        except Exception as e:
            logger.error(f"Error syncing weight for user {user.id}: {e}", exc_info=True)
            return False

    def _log_sync(
        self, 
        user: User, 
        status: str, 
        source_id: str,
        activity_date: datetime,
        message: Optional[str] = None,
    ):
        """Log sync result to database."""
        try:
            log = SyncLog(
                user_id=user.id,
                sync_direction="withings_to_garmin",
                status=status,
                error_message=message,
                # Use source_activity_id as the canonical ID
                source_activity_id=source_id,
                # Legacy field required by DB schema (non-nullable)
                strava_activity_id=f"withings_{source_id}",
                activity_type="weight",
                activity_name=f"Weight {activity_date.strftime('%Y-%m-%d')}",
                completed_at=datetime.utcnow()
            )
            self.db.add(log)
            self.db.commit()
        except Exception as e:
            logger.error(f"Error creating sync log: {e}")
