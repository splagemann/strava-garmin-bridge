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
        Sync latest weight from Withings to Garmin.

        Args:
            user: User object

        Returns:
            True if sync successful or no new data, False if error
        """
        try:
            # 1. Check if user is connected to both
            if not user.withings_auth:
                logger.info(f"User {user.id} not connected to Withings, skipping weight sync")
                return False
            
            if not user.garmin_auth:
                logger.info(f"User {user.id} not connected to Garmin, skipping weight sync")
                return False

            # 2. Get latest weight from Withings
            measurement = self.withings_service.get_latest_weight(user)
            if not measurement:
                logger.info(f"No weight data found for user {user.id}")
                return True # No data is not an error

            weight_kg = measurement["weight"]
            timestamp = measurement["date"]
            
            # 3. Check if already synced
            # For simplicity, we'll check if we have a sync log for this timestamp
            # Ideally we should store the measurement ID, but timestamp is a good proxy for weight
            existing_log = self.db.query(SyncLog).filter(
                SyncLog.user_id == user.id,
                SyncLog.activity_type == "weight",
                SyncLog.source_id == str(int(timestamp.timestamp())) # Use timestamp as ID
            ).first()

            if existing_log and existing_log.status == "success":
                logger.info(f"Weight for {timestamp} already synced for user {user.id}")
                return True

            # 4. Connect to Garmin
            if not self.garmin_service.connect(user):
                logger.error(f"Failed to connect to Garmin for user {user.id}")
                self._log_sync(user, "failed", "Garmin connection failed", str(int(timestamp.timestamp())), timestamp)
                return False

            # 5. Upload to Garmin
            success = self.garmin_service.upload_weight(weight_kg, timestamp)
            
            if success:
                logger.info(f"Successfully synced weight {weight_kg}kg from {timestamp} for user {user.id}")
                self._log_sync(user, "success", f"Synced {weight_kg:.2f}kg", str(int(timestamp.timestamp())), timestamp)
                return True
            else:
                logger.error(f"Failed to upload weight for user {user.id}")
                self._log_sync(user, "failed", "Upload failed", str(int(timestamp.timestamp())), timestamp)
                return False

        except Exception as e:
            logger.error(f"Error syncing weight for user {user.id}: {e}", exc_info=True)
            return False

    def _log_sync(
        self, 
        user: User, 
        status: str, 
        message: str, 
        source_id: str,
        activity_date: datetime
    ):
        """Log sync result to database."""
        try:
            log = SyncLog(
                user_id=user.id,
                source_platform="withings",
                destination_platform="garmin",
                activity_type="weight",
                status=status,
                message=message,
                source_id=source_id,
                activity_date=activity_date
            )
            self.db.add(log)
            self.db.commit()
        except Exception as e:
            logger.error(f"Error creating sync log: {e}")
