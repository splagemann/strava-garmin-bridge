"""
Authentication models for Strava and Garmin.
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class StravaAuth(Base):
    """Strava OAuth authentication credentials."""

    __tablename__ = "strava_auth"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
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
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)

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
