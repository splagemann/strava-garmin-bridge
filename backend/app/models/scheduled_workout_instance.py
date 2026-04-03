"""
ScheduledWorkoutInstance — tracks individual (user, workout, date) pushes to Garmin
so that re-running a sync never creates duplicates.
"""

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database import Base


class ScheduledWorkoutInstance(Base):
    """One scheduled workout on one specific date for one user."""

    __tablename__ = "scheduled_workout_instances"
    __table_args__ = (
        # Prevent scheduling the same workout on the same date twice
        UniqueConstraint("user_id", "workout_id", "scheduled_date", name="uq_user_workout_date"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Garmin workout ID (string to be safe with large IDs)
    workout_id = Column(String, nullable=False)
    # ISO date string YYYY-MM-DD
    scheduled_date = Column(String, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")

    def __repr__(self) -> str:
        return (
            f"<ScheduledWorkoutInstance(user={self.user_id}, "
            f"workout={self.workout_id}, date={self.scheduled_date})>"
        )
