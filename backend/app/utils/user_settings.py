"""Helpers for user-specific settings (key-value store, override vs server default)."""

from sqlalchemy.orm import Session

from app.config import settings
from app.models import User, UserSettings

# Setting keys (add new keys here when adding settings)
KEY_GARMIN_TO_STRAVA_SYNC_DISABLED = "garmin_to_strava_sync_disabled"
KEY_ALLOW_EXPORT_WITHOUT_GPS = "allow_export_without_gps"


def get_setting(db: Session, user_id: int, key: str) -> str | None:
    """Get raw string value for a key, or None if not set."""
    row = db.query(UserSettings).filter(UserSettings.user_id == user_id, UserSettings.key == key).first()
    return row.value if row else None


def set_setting(db: Session, user_id: int, key: str, value: str) -> None:
    """Set a key to a string value (upsert)."""
    row = db.query(UserSettings).filter(UserSettings.user_id == user_id, UserSettings.key == key).first()
    if row:
        row.value = value
    else:
        db.add(UserSettings(user_id=user_id, key=key, value=value))


def get_garmin_to_strava_sync_enabled(user: User, db: Session) -> bool:
    """Return effective Garmin→Strava sync enabled for this user (not disabled = enabled)."""
    v = get_setting(db, user.id, KEY_GARMIN_TO_STRAVA_SYNC_DISABLED)
    default_disabled = not settings.GARMIN_TO_STRAVA_SYNC_ENABLED
    disabled = (v == "true") if v is not None else default_disabled
    return not disabled


def get_allow_export_without_gps(user: User, db: Session) -> bool:
    """Return effective allow-export-without-GPS for this user (both directions)."""
    v = get_setting(db, user.id, KEY_ALLOW_EXPORT_WITHOUT_GPS)
    if v is not None:
        return v == "true"
    return settings.ALLOW_EXPORT_WITHOUT_GPS


def get_setting_override_bool(db: Session, user_id: int, key: str) -> bool | None:
    """Get override as bool for API (True/False) or None if using server default."""
    v = get_setting(db, user_id, key)
    if v is None:
        return None
    return v == "true"
