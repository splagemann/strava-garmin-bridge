"""
Authentication routes for Strava OAuth and Garmin credentials.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.utils.user_settings import (
    KEY_ALLOW_EXPORT_WITHOUT_GPS,
    KEY_DISPLAY_TIME_FORMAT,
    KEY_DISPLAY_TIMEZONE,
    KEY_GARMIN_TO_STRAVA_SYNC_DISABLED,
    KEY_SYNC_SCHEDULE_MINUTES,
    SYNC_SCHEDULE_CHOICES,
    get_allow_export_without_gps,
    get_display_time_format,
    get_display_timezone,
    get_fit_device_settings,
    get_garmin_to_strava_sync_enabled,
    get_setting_override_bool,
    get_sync_schedule_minutes,
    set_fit_device_settings,
    set_setting,
)
from app.middleware.auth import get_current_user
from app.models import StravaAuth, User
from app.services.garmin_service import GarminService
from garminconnect import GarminConnectTooManyRequestsError
from app.services.strava_service import StravaService
from app.services.withings_service import WithingsService
from app.utils.jwt import create_access_token, verify_state_token

logger = logging.getLogger(__name__)
router = APIRouter()


class GarminCredentials(BaseModel):
    """Request model for Garmin credentials."""

    email: str
    password: str


class GarminMFAVerify(BaseModel):
    """Request model for Garmin MFA code verification."""

    mfa_token: str
    mfa_code: str


class FitDeviceSettingsBody(BaseModel):
    """FIT device settings (user-level): written into FIT files on export."""

    device_name: Optional[str] = None
    serial_number: Optional[str] = None
    manufacturer_id: Optional[str] = None
    software_version: Optional[str] = None
    product_id: Optional[str] = None


class SettingsUpdate(BaseModel):
    """Request model for user settings update."""

    garmin_to_strava_sync_disabled: Optional[bool] = (
        None  # None = use server default (True = sync off)
    )
    allow_export_without_gps: Optional[bool] = None  # None = use server default
    sync_schedule_minutes: Optional[int] = None  # One of 5, 10, 15, 30, 45, 60, 120, 240; default 5
    fit_device_settings: Optional[FitDeviceSettingsBody] = None


class ProfileUpdate(BaseModel):
    """Request model for profile update (email, username, first_name, last_name, display_timezone, display_time_format)."""

    email: Optional[str] = None
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    display_timezone: Optional[str] = None
    display_time_format: Optional[str] = None  # "12h" or "24h"


class WithingsAuthRequest(BaseModel):
    """Request model for Withings authorization code exchange."""

    code: str
    state: str
    signed_state: str


class StravaAuthRequest(BaseModel):
    """Request model for Strava authorization code exchange."""

    code: str
    state: str  # State returned from Strava OAuth
    signed_state: str  # Signed state token from initial auth request
    scope: str = None


@router.get("/strava/auth-url")
async def get_strava_auth_url():
    """
    Get Strava OAuth authorization URL.
    Frontend will redirect user to this URL to start OAuth flow.
    """
    try:
        redirect_uri = f"{settings.FRONTEND_URL}/auth/callback"
        logger.info(f"Generating Strava auth URL with redirect_uri: {redirect_uri}")

        auth_url, state = StravaService.get_authorization_url(redirect_uri)

        logger.info(f"Generated auth_url: {auth_url}")

        if not auth_url:
            logger.error("Auth URL is empty or None")
            raise HTTPException(
                status_code=500, detail="Failed to generate Strava authorization URL"
            )

        return {"auth_url": auth_url, "state": state}
    except Exception as e:
        logger.error(f"Error generating Strava auth URL: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/strava/exchange")
async def exchange_strava_code(auth_request: StravaAuthRequest, db: Session = Depends(get_db)):
    """
    Exchange Strava authorization code for access token with CSRF protection.
    Called by frontend after receiving callback from Strava.
    Returns JWT token for authenticated API access.
    """
    try:
        logger.info(
            f"Strava exchange request - state: {auth_request.state[:20]}..., signed_state: {auth_request.signed_state[:20] if auth_request.signed_state else 'None'}..."
        )

        # CSRF Protection: Verify state token
        if not verify_state_token(auth_request.signed_state, auth_request.state):
            logger.warning(
                f"State token verification failed - state: {auth_request.state}, signed_state: {auth_request.signed_state[:50] if auth_request.signed_state else 'None'}"
            )
            raise HTTPException(
                status_code=400,
                detail="Invalid state token. Please restart the authentication process.",
            )

        strava_service = StravaService(db)

        # Exchange code for token
        token_response = strava_service.exchange_code_for_token(auth_request.code)

        # Log the response structure for debugging
        logger.info(f"Token response keys: {token_response.keys()}")

        # Create a client with the access token to get athlete info
        from stravalib.client import Client

        client = Client()
        client.access_token = token_response["access_token"]

        # Get authenticated athlete information
        athlete = client.get_athlete()
        logger.info(f"Athlete ID: {athlete.id}")

        # Get or create user
        athlete_email = getattr(athlete, "email", None)
        athlete_id = athlete.id

        if not athlete_email:
            # If email not provided, use athlete ID as placeholder
            athlete_email = f"athlete_{athlete_id}@strava.local"
            logger.info(f"No email provided by Strava, using placeholder: {athlete_email}")

        # Look up by athlete_id first — this handles reconnects and prevents the
        # UniqueViolation that occurs when athlete_id already exists for another user row.
        existing_auth = (
            db.query(StravaAuth).filter(StravaAuth.athlete_id == str(athlete_id)).first()
        )
        if existing_auth:
            user = existing_auth.user
            logger.info(f"Returning user {user.id} matched by athlete_id {athlete_id}")
        else:
            user = db.query(User).filter(User.email == athlete_email).first()
            if not user:
                user = User(email=athlete_email)
                db.add(user)
                db.commit()
                db.refresh(user)

        # Save Strava auth with athlete info
        strava_auth = strava_service.save_auth(user, token_response, athlete)

        # Create JWT token for the user
        access_token = create_access_token(data={"sub": str(user.id)})

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "email": user.email,
            "athlete_id": str(athlete_id),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exchanging Strava code: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/garmin/credentials")
async def save_garmin_credentials(
    credentials: GarminCredentials,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Save Garmin Connect credentials for authenticated user.
    Supports MFA: if the account has 2FA/MFA enabled, the response will include
    mfa_required and mfa_token; submit the MFA code to POST /auth/garmin/mfa.

    Requires: Bearer token authentication
    """
    user = current_user
    garmin_service = GarminService(db)

    try:
        result, data = garmin_service.start_login_with_mfa(
            user.id, credentials.email, credentials.password
        )
    except GarminConnectTooManyRequestsError:
        raise HTTPException(
            status_code=429,
            detail="Garmin is rate-limiting login attempts. Please wait a few minutes before trying again.",
        )
    except Exception as e:
        detail = str(e) if str(e) else "Invalid Garmin credentials"
        logger.error(f"Garmin login failed for user {user.id}: {e}", exc_info=True)
        # Use 400, not 401 — a 401 would trigger the frontend's global logout interceptor
        raise HTTPException(status_code=400, detail=detail)

    if result == "mfa_required":
        return {
            "message": "MFA code required",
            "mfa_required": True,
            "mfa_token": data,
        }

    # Login succeeded without MFA; save credentials and session (disk + DB)
    garmin_client = data
    try:
        garmin_auth = garmin_service.save_credentials(user, credentials.email, credentials.password)
        garmin_service._persist_tokens(garmin_client, garmin_auth)
    except Exception as e:
        logger.error(f"Error saving Garmin credentials: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to save credentials")

    return {
        "message": "Garmin credentials verified and saved successfully",
        "mfa_required": False,
    }


@router.post("/garmin/mfa")
async def verify_garmin_mfa(
    body: GarminMFAVerify,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Complete Garmin login with MFA code (after POST /auth/garmin/credentials
    returned mfa_required and mfa_token).
    """
    garmin_service = GarminService(db)
    success, error_message = garmin_service.complete_mfa(
        body.mfa_token, body.mfa_code, current_user
    )
    if not success:
        raise HTTPException(status_code=400, detail=error_message)
    return {"message": "Garmin credentials verified and saved successfully"}


@router.get("/withings/auth-url")
async def get_withings_auth_url():
    """
    Get Withings OAuth authorization URL.
    """
    try:
        redirect_uri = f"{settings.FRONTEND_URL}/auth/withings/callback"
        logger.info(f"Generating Withings auth URL with redirect_uri: {redirect_uri}")

        auth_url, state = WithingsService.get_authorization_url(redirect_uri)

        return {"auth_url": auth_url, "state": state}
    except Exception as e:
        logger.error(f"Error generating Withings auth URL: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/withings/exchange")
async def exchange_withings_code(
    auth_request: WithingsAuthRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Exchange Withings authorization code for access token.
    """
    try:
        # Verify state
        if not verify_state_token(auth_request.signed_state, auth_request.state):
            raise HTTPException(status_code=400, detail="Invalid state token")

        withings_service = WithingsService(db)
        redirect_uri = f"{settings.FRONTEND_URL}/auth/withings/callback"

        token_response = withings_service.exchange_code_for_token(auth_request.code, redirect_uri)

        withings_service.save_auth(current_user, token_response)

        return {"message": "Withings connected successfully"}
    except Exception as e:
        logger.error(f"Error exchanging Withings code: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/status")
async def auth_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Check authentication status for Strava, Garmin, and Withings for the authenticated user.

    Requires: Bearer token authentication
    """
    return {
        "email": current_user.email,
        "username": current_user.username,
        "first_name": current_user.first_name,
        "last_name": current_user.last_name,
        "display_timezone": get_display_timezone(db, current_user.id),
        "display_time_format": get_display_time_format(db, current_user.id),
        "strava_connected": current_user.strava_auth is not None,
        "garmin_connected": current_user.garmin_auth is not None,
        "withings_connected": current_user.withings_auth is not None,
        "strava_athlete_id": (
            current_user.strava_auth.athlete_id if current_user.strava_auth else None
        ),
        "garmin_to_strava_sync_disabled": not get_garmin_to_strava_sync_enabled(current_user, db),
    }


@router.patch("/profile")
async def update_profile(
    body: ProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update current user profile (email, username, first_name, last_name)."""
    user = db.query(User).filter(User.id == current_user.id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if body.email is not None:
        existing = db.query(User).filter(User.email == body.email, User.id != user.id).first()
        if existing:
            raise HTTPException(status_code=400, detail="Email already in use")
        user.email = body.email.strip()
    if body.username is not None:
        val = body.username.strip() or None
        if val:
            existing = db.query(User).filter(User.username == val, User.id != user.id).first()
            if existing:
                raise HTTPException(status_code=400, detail="Username already in use")
        user.username = val
    if body.first_name is not None:
        user.first_name = body.first_name.strip() or None
    if body.last_name is not None:
        user.last_name = body.last_name.strip() or None
    if body.display_timezone is not None:
        tz = (body.display_timezone or "").strip() or "UTC"
        set_setting(db, user.id, KEY_DISPLAY_TIMEZONE, tz[:64])
    if body.display_time_format is not None:
        fmt = (body.display_time_format or "").strip().lower()
        if fmt in ("12h", "24h"):
            set_setting(db, user.id, KEY_DISPLAY_TIME_FORMAT, fmt)
    db.commit()
    db.refresh(user)
    return {
        "email": user.email,
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "display_timezone": get_display_timezone(db, user.id),
        "display_time_format": get_display_time_format(db, user.id),
    }


@router.get("/settings")
async def get_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get current user settings (for Settings tab).
    Returns effective values and user overrides (null = using server default).
    """
    enabled = get_garmin_to_strava_sync_enabled(current_user, db)
    device = get_fit_device_settings(db, current_user.id)
    return {
        "garmin_to_strava_sync_disabled": not enabled,
        "garmin_to_strava_sync_disabled_override": get_setting_override_bool(
            db, current_user.id, KEY_GARMIN_TO_STRAVA_SYNC_DISABLED
        ),
        "allow_export_without_gps": get_allow_export_without_gps(current_user, db),
        "allow_export_without_gps_override": get_setting_override_bool(
            db, current_user.id, KEY_ALLOW_EXPORT_WITHOUT_GPS
        ),
        "sync_schedule_minutes": get_sync_schedule_minutes(db, current_user.id),
        "fit_device_settings": {
            "device_name": device.get("device_name") or None,
            "serial_number": device.get("serial_number") or None,
            "manufacturer_id": device.get("manufacturer_id") or None,
            "software_version": device.get("software_version") or None,
            "product_id": device.get("product_id") or None,
        },
    }


@router.patch("/settings")
async def update_settings(
    body: SettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update current user settings."""
    try:
        user = db.query(User).filter(User.id == current_user.id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        if body.garmin_to_strava_sync_disabled is not None:
            set_setting(
                db,
                user.id,
                KEY_GARMIN_TO_STRAVA_SYNC_DISABLED,
                "true" if body.garmin_to_strava_sync_disabled else "false",
            )
        if body.allow_export_without_gps is not None:
            set_setting(
                db,
                user.id,
                KEY_ALLOW_EXPORT_WITHOUT_GPS,
                "true" if body.allow_export_without_gps else "false",
            )
        if body.sync_schedule_minutes is not None:
            if body.sync_schedule_minutes in SYNC_SCHEDULE_CHOICES:
                set_setting(db, user.id, KEY_SYNC_SCHEDULE_MINUTES, str(body.sync_schedule_minutes))
            # else ignore invalid value
        if body.fit_device_settings is not None:
            data = get_fit_device_settings(db, user.id)
            for k, v in body.fit_device_settings.model_dump().items():
                if v is not None and (isinstance(v, str) and v.strip()):
                    data[k] = v.strip()
                elif k in data:
                    data.pop(k, None)
            set_fit_device_settings(db, user.id, data)
        db.commit()
        enabled = get_garmin_to_strava_sync_enabled(user, db)
        device = get_fit_device_settings(db, user.id)
        return {
            "garmin_to_strava_sync_disabled": not enabled,
            "garmin_to_strava_sync_disabled_override": get_setting_override_bool(
                db, user.id, KEY_GARMIN_TO_STRAVA_SYNC_DISABLED
            ),
            "allow_export_without_gps": get_allow_export_without_gps(user, db),
            "allow_export_without_gps_override": get_setting_override_bool(
                db, user.id, KEY_ALLOW_EXPORT_WITHOUT_GPS
            ),
            "sync_schedule_minutes": get_sync_schedule_minutes(db, user.id),
            "fit_device_settings": {
                "device_name": device.get("device_name") or None,
                "serial_number": device.get("serial_number") or None,
                "manufacturer_id": device.get("manufacturer_id") or None,
                "software_version": device.get("software_version") or None,
                "product_id": device.get("product_id") or None,
            },
        }
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.exception("Failed to update user settings")
        msg = str(e)
        if (
            "garmin_to_strava_sync" in msg
            or "allow_export_without_gps" in msg
            or "does not exist" in msg
            or "column" in msg.lower()
        ):
            msg = "Database schema may be outdated. Run: alembic upgrade head"
        raise HTTPException(status_code=500, detail=msg)
