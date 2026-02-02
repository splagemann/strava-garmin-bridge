"""Helpers for user-specific settings (key-value store, override vs server default)."""

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.config import settings
from app.models import User, UserSettings

# Setting keys (add new keys here when adding settings)
KEY_GARMIN_TO_STRAVA_SYNC_DISABLED = "garmin_to_strava_sync_disabled"
KEY_ALLOW_EXPORT_WITHOUT_GPS = "allow_export_without_gps"
KEY_DISPLAY_TIMEZONE = "display_timezone"
KEY_DISPLAY_TIME_FORMAT = "display_time_format"  # "12h" or "24h"
KEY_SYNC_SCHEDULE_MINUTES = "sync_schedule_minutes"
KEY_LAST_STRAVA_POLL_AT = "last_strava_poll_at"
KEY_LAST_GARMIN_POLL_AT = "last_garmin_poll_at"
KEY_FIT_DEVICE_SETTINGS = (
    "fit_device_settings"  # JSON: device_name, serial_number, manufacturer_id, software_version
)
# Allowed sync schedule interval values (minutes)
SYNC_SCHEDULE_CHOICES = (5, 10, 15, 30, 45, 60, 120, 240)
DEFAULT_SYNC_SCHEDULE_MINUTES = 5


def get_setting(db: Session, user_id: int, key: str) -> str | None:
    """Get raw string value for a key, or None if not set."""
    row = (
        db.query(UserSettings)
        .filter(UserSettings.user_id == user_id, UserSettings.key == key)
        .first()
    )
    return row.value if row else None


def set_setting(db: Session, user_id: int, key: str, value: str) -> None:
    """Set a key to a string value (upsert)."""
    row = (
        db.query(UserSettings)
        .filter(UserSettings.user_id == user_id, UserSettings.key == key)
        .first()
    )
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


def get_display_timezone(db: Session, user_id: int) -> str:
    """Return display timezone for the user (for formatting dates). Default UTC."""
    v = get_setting(db, user_id, KEY_DISPLAY_TIMEZONE)
    return (v or "UTC").strip() or "UTC"


def get_display_time_format(db: Session, user_id: int) -> str:
    """Return display time format: '12h' or '24h'. Default 12h."""
    v = get_setting(db, user_id, KEY_DISPLAY_TIME_FORMAT)
    if v and v.strip().lower() in ("12h", "24h"):
        return v.strip().lower()
    return "12h"


def get_setting_override_bool(db: Session, user_id: int, key: str) -> bool | None:
    """Get override as bool for API (True/False) or None if using server default."""
    v = get_setting(db, user_id, key)
    if v is None:
        return None
    return v == "true"


def get_sync_schedule_minutes(db: Session, user_id: int) -> int:
    """Return sync schedule interval in minutes. Default 5. One of SYNC_SCHEDULE_CHOICES."""
    v = get_setting(db, user_id, KEY_SYNC_SCHEDULE_MINUTES)
    if v is None:
        return DEFAULT_SYNC_SCHEDULE_MINUTES
    try:
        n = int(v)
        if n in SYNC_SCHEDULE_CHOICES:
            return n
    except ValueError:
        pass
    return DEFAULT_SYNC_SCHEDULE_MINUTES


def get_last_poll_at(db: Session, user_id: int, key: str) -> datetime | None:
    """Return last poll timestamp (UTC) from stored ISO string, or None."""
    v = get_setting(db, user_id, key)
    if not v or not v.strip():
        return None
    try:
        return datetime.fromisoformat(v.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def set_last_poll_at(db: Session, user_id: int, key: str, when: datetime) -> None:
    """Store poll timestamp as ISO string (UTC)."""
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    set_setting(db, user_id, key, when.isoformat())


# FIT device settings (per-user, stored as JSON in UserSettings)
FIT_DEVICE_KEYS = (
    "device_name",
    "serial_number",
    "manufacturer_id",
    "software_version",
    "product_id",
)


def get_fit_device_settings(db: Session, user_id: int) -> dict[str, Any]:
    """
    Return FIT device settings for the user (device_name, serial_number, manufacturer_id, software_version, product_id).
    Stored as JSON in UserSettings. Used when generating FIT files. Empty dict if not set.
    """
    v = get_setting(db, user_id, KEY_FIT_DEVICE_SETTINGS)
    if not v or not v.strip():
        return {}
    try:
        out = json.loads(v)
        return out if isinstance(out, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def set_fit_device_settings(db: Session, user_id: int, data: dict[str, Any]) -> None:
    """Store FIT device settings as JSON in UserSettings (device_name, serial_number, manufacturer_id, software_version, product_id)."""
    clean = {}
    for k, v in data.items():
        if k not in FIT_DEVICE_KEYS or v is None:
            continue
        if isinstance(v, (int, float)):
            clean[k] = str(v)
        elif isinstance(v, str) and v.strip():
            clean[k] = v.strip()
    set_setting(db, user_id, KEY_FIT_DEVICE_SETTINGS, json.dumps(clean))
