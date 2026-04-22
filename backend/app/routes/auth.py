"""
Authentication routes for Strava OAuth and Garmin credentials.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.middleware.auth import get_current_user
from app.models import User
from app.services.garmin_service import GarminService
from app.services.strava_service import StravaService
from app.services.withings_service import WithingsService
from app.utils.jwt import create_access_token, verify_state_token

logger = logging.getLogger(__name__)
router = APIRouter()


class GarminCredentials(BaseModel):
    """Request model for Garmin credentials."""

    email: str
    password: str


class GarminMfaRequest(BaseModel):
    """Request model for Garmin MFA verification."""

    code: str


class WithingsAuthRequest(BaseModel):
    """Request model for Withings authorization code exchange."""

    code: str
    state: str
    signed_state: str


class StravaAuthRequest(BaseModel):
    """Request model for Strava authorization code exchange."""

    code: str
    state: str
    signed_state: str
    scope: str = None


@router.get("/strava/auth-url")
async def get_strava_auth_url():
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
    try:
        logger.info(
            f"Strava exchange request - state: {auth_request.state[:20]}..., signed_state: {auth_request.signed_state[:20] if auth_request.signed_state else 'None'}..."
        )

        if not verify_state_token(auth_request.signed_state, auth_request.state):
            logger.warning(
                f"State token verification failed - state: {auth_request.state}, signed_state: {auth_request.signed_state[:50] if auth_request.signed_state else 'None'}"
            )
            raise HTTPException(
                status_code=400,
                detail="Invalid state token. Please restart the authentication process.",
            )

        strava_service = StravaService(db)
        token_response = strava_service.exchange_code_for_token(auth_request.code)

        logger.info(f"Token response keys: {token_response.keys()}")

        from stravalib.client import Client

        client = Client()
        client.access_token = token_response["access_token"]

        athlete = client.get_athlete()
        logger.info(f"Athlete ID: {athlete.id}")

        athlete_email = getattr(athlete, "email", None)
        athlete_id = athlete.id

        if not athlete_email:
            athlete_email = f"athlete_{athlete_id}@strava.local"
            logger.info(f"No email provided by Strava, using placeholder: {athlete_email}")

        user = db.query(User).filter(User.email == athlete_email).first()
        if not user:
            user = User(email=athlete_email)
            db.add(user)
            db.commit()
            db.refresh(user)

        strava_service.save_auth(user, token_response, athlete)
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
    user = current_user
    garmin_service = GarminService(db)

    try:
        garmin_service.save_credentials(user, credentials.email, credentials.password)
        connected = garmin_service.connect(user)
        db.refresh(user)

        if user.garmin_auth and user.garmin_auth.encrypted_mfa_token:
            return {
                "message": "Garmin credentials accepted. MFA code required to finish setup.",
                "requires_mfa": True,
            }

        if not connected:
            raise HTTPException(status_code=401, detail="Invalid Garmin credentials")

        return {
            "message": "Garmin credentials verified and saved successfully",
            "requires_mfa": False,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving Garmin credentials: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to save credentials")


@router.post("/garmin/mfa")
async def verify_garmin_mfa(
    request: GarminMfaRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    garmin_service = GarminService(db)
    success, error_message = garmin_service.complete_mfa(current_user, request.code)

    if not success:
        raise HTTPException(status_code=401, detail=error_message or "Garmin MFA verification failed")

    return {"message": "Garmin MFA verified successfully", "requires_mfa": False}


@router.get("/withings/auth-url")
async def get_withings_auth_url():
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
    db: Session = Depends(get_db)
):
    try:
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
async def auth_status(current_user: User = Depends(get_current_user)):
    return {
        "email": current_user.email,
        "strava_connected": current_user.strava_auth is not None,
        "garmin_connected": current_user.garmin_auth is not None and current_user.garmin_auth.session_data is not None,
        "garmin_requires_mfa": current_user.garmin_auth is not None and current_user.garmin_auth.encrypted_mfa_token is not None,
        "withings_connected": current_user.withings_auth is not None,
        "strava_athlete_id": (
            current_user.strava_auth.athlete_id if current_user.strava_auth else None
        ),
    }
