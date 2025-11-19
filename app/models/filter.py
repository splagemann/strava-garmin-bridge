"""
Activity filter model.
"""
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class ActivityFilter(Base):
    """Activity filter rules for controlling sync behavior."""

    __tablename__ = "activity_filters"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Filter configuration
    filter_type = Column(String, nullable=False)  # "include" or "exclude"
    pattern = Column(String, nullable=False)  # Text pattern or regex
    is_regex = Column(Boolean, default=False)  # Whether pattern is a regex
    active = Column(Boolean, default=True)  # Whether filter is enabled

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="activity_filters")

    def __repr__(self):
        return f"<ActivityFilter(id={self.id}, type={self.filter_type}, pattern={self.pattern})>"
