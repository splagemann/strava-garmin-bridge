"""
WorkoutSchedule model — recurring Garmin workout assignments.
"""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import relationship

from app.database import Base


class WorkoutSchedule(Base):
    """Recurring weekly schedule that pushes a Garmin workout on chosen days."""

    __tablename__ = "workout_schedules"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    workout_id = Column(String, nullable=False)
    workout_name = Column(String, nullable=False)
    # List of ints using Python weekday() convention: 0=Mon … 6=Sun
    days_of_week = Column(JSON, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="workout_schedules")

    def __repr__(self) -> str:
        return (
            f"<WorkoutSchedule(id={self.id}, user_id={self.user_id}, "
            f"workout='{self.workout_name}', days={self.days_of_week})>"
        )
