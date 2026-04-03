"""
Sync log model for tracking activity sync operations.
"""

from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class SyncLog(Base):
    """Log of activity sync operations."""

    __tablename__ = "sync_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Sync direction: "strava_to_garmin" or "garmin_to_strava"
    sync_direction = Column(String, nullable=False, default="strava_to_garmin", index=True)

    # Activity identifiers (flexible based on direction)
    source_activity_id = Column(
        String, nullable=False, index=True
    )  # Strava ID or Garmin ID (based on direction)
    target_activity_id = Column(String, nullable=True)  # Result ID from target platform

    # Legacy fields (kept for backwards compatibility)
    strava_activity_id = Column(String, nullable=False, index=True)
    garmin_activity_id = Column(String, nullable=True)  # Set after successful upload

    # Sync status
    status = Column(String, nullable=False)  # "success", "failed", "skipped", "pending"
    error_message = Column(Text, nullable=True)  # Error details if failed

    # Activity metadata (for reference)
    activity_name = Column(String, nullable=True)
    activity_type = Column(String, nullable=True)

    # Debug data (for troubleshooting)
    strava_data = Column(JSON, nullable=True)  # Raw Strava activity object
    garmin_data = Column(Text, nullable=True)  # File summary or Garmin response data

    # Stored file data (for download feature)
    uploaded_file_path = Column(String(255), nullable=True)  # Path to file on filesystem
    uploaded_file_extension = Column(String(10), nullable=True)  # File extension: "fit", "gpx", "tcx", etc.

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("User", back_populates="sync_logs")

    def __repr__(self):
        return f"<SyncLog(id={self.id}, strava_id={self.strava_activity_id}, status={self.status})>"
