"""
User model.
"""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base


class User(Base):
    """User model representing a registered user."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    # Relationships
    strava_auth = relationship("StravaAuth", back_populates="user", uselist=False)
    garmin_auth = relationship("GarminAuth", back_populates="user", uselist=False)
    withings_auth = relationship("WithingsAuth", back_populates="user", uselist=False)
    activity_filters = relationship("ActivityFilter", back_populates="user")
    sync_logs = relationship("SyncLog", back_populates="user")

    def __repr__(self):
        return f"<User(id={self.id}, email={self.email})>"
