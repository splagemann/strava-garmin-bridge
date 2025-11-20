"""
Authentication routes for Strava OAuth and Garmin credentials.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.database import get_db
from app.models import User
from app.services.strava_service import StravaService
from app.services.garmin_service import GarminService
from app.config import settings
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


class GarminCredentials(BaseModel):
    """Request model for Garmin credentials."""
    email: str
    password: str


class StravaAuthRequest(BaseModel):
    """Request model for Strava authorization code exchange."""
    code: str
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
            raise HTTPException(status_code=500, detail="Failed to generate Strava authorization URL")

        return {
            "auth_url": auth_url,
            "state": state
        }
    except Exception as e:
        logger.error(f"Error generating Strava auth URL: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/strava/exchange")
async def exchange_strava_code(
    auth_request: StravaAuthRequest,
    db: Session = Depends(get_db)
):
    """
    Exchange Strava authorization code for access token.
    Called by frontend after receiving callback from Strava.
    """
    try:
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

        user = db.query(User).filter(User.email == athlete_email).first()
        if not user:
            user = User(email=athlete_email)
            db.add(user)
            db.commit()
            db.refresh(user)

        # Save Strava auth with athlete info
        strava_auth = strava_service.save_auth(user, token_response, athlete)

        return {
            "success": True,
            "user_id": user.id,
            "email": user.email,
            "athlete_id": str(athlete_id)
        }

    except Exception as e:
        logger.error(f"Error exchanging Strava code: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/garmin/credentials")
async def save_garmin_credentials(
    credentials: GarminCredentials,
    user_id: int = Query(..., description="User ID"),
    db: Session = Depends(get_db)
):
    """
    Save Garmin Connect credentials for a user.
    Credentials are encrypted before storage and verified before saving.

    Note: Credentials must be valid. If you have 2FA/MFA enabled on Garmin,
    you may need to use an app-specific password or ensure you complete
    the authentication flow properly.
    """
    # Get user
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Initialize Garmin service
    garmin_service = GarminService(db)

    # Verify credentials first
    logger.info(f"Verifying Garmin credentials for user {user_id}")
    is_valid, error_message = garmin_service.verify_credentials(credentials.email, credentials.password)

    if not is_valid:
        detail = f"Invalid Garmin credentials: {error_message}" if error_message else "Invalid Garmin credentials"
        logger.error(f"Failed to verify Garmin credentials for user {user_id}: {detail}")

        # Provide helpful message if it's likely 2FA
        if "AssertionError" in detail or "2FA" in detail or "MFA" in detail:
            detail += "\n\nNote: If you have 2FA/MFA enabled on your Garmin account, you may need to use an app-specific password or ensure proper authentication flow."

        raise HTTPException(status_code=401, detail=detail)

    logger.info(f"Garmin credentials verified successfully for user {user_id}")

    # Save credentials
    try:
        garmin_auth = garmin_service.save_credentials(
            user,
            credentials.email,
            credentials.password
        )

        return {
            "message": "Garmin credentials verified and saved successfully",
            "user_id": user.id
        }

    except Exception as e:
        logger.error(f"Error saving Garmin credentials: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to save credentials")


@router.get("/status")
async def auth_status(
    user_id: int = Query(..., description="User ID"),
    db: Session = Depends(get_db)
):
    """
    Check authentication status for both Strava and Garmin.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "user_id": user.id,
        "email": user.email,
        "strava_connected": user.strava_auth is not None,
        "garmin_connected": user.garmin_auth is not None,
        "strava_athlete_id": user.strava_auth.athlete_id if user.strava_auth else None
    }
