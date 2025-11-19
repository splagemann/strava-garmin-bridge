"""
Sync log model for tracking activity sync operations.
"""
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class SyncLog(Base):
    """Log of activity sync operations."""

    __tablename__ = "sync_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Activity identifiers
    strava_activity_id = Column(String, nullable=False, index=True)
    garmin_activity_id = Column(String, nullable=True)  # Set after successful upload

    # Sync status
    status = Column(String, nullable=False)  # "success", "failed", "skipped", "pending"
    error_message = Column(Text, nullable=True)  # Error details if failed

    # Activity metadata (for reference)
    activity_name = Column(String, nullable=True)
    activity_type = Column(String, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("User", back_populates="sync_logs")

    def __repr__(self):
        return f"<SyncLog(id={self.id}, strava_id={self.strava_activity_id}, status={self.status})>"
