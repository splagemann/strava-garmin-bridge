"""
Authentication models for Strava and Garmin.
"""

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class StravaAuth(Base):
    """Strava OAuth authentication credentials."""

    __tablename__ = "strava_auth"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    athlete_id = Column(String, unique=True, index=True, nullable=False)
    access_token = Column(String, nullable=False)
    refresh_token = Column(String, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="strava_auth")

    def __repr__(self):
        return f"<StravaAuth(user_id={self.user_id}, athlete_id={self.athlete_id})>"


class GarminAuth(Base):
    """Garmin Connect authentication credentials (encrypted)."""

    __tablename__ = "garmin_auth"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )

    # Encrypted credentials
    encrypted_email = Column(Text, nullable=False)
    encrypted_password = Column(Text, nullable=False)

    # Optional: MFA token if user has 2FA enabled
    encrypted_mfa_token = Column(Text, nullable=True)

    # Optional: Store session data to avoid repeated logins
    session_data = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="garmin_auth")

    def __repr__(self):
        return f"<GarminAuth(user_id={self.user_id})>"


class WithingsAuth(Base):
    """Withings OAuth authentication credentials."""

    __tablename__ = "withings_auth"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    withings_userid = Column(String, unique=True, index=True, nullable=False)
    access_token = Column(String, nullable=False)
    refresh_token = Column(String, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="withings_auth")

    def __repr__(self):
        return f"<WithingsAuth(user_id={self.user_id}, withings_userid={self.withings_userid})>"
