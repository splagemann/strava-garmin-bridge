"""
Strava API service for handling OAuth and activity operations.
"""
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from stravalib.client import Client
from sqlalchemy.orm import Session
from app.models import User, StravaAuth
from app.config import settings
import logging

logger = logging.getLogger(__name__)


class StravaService:
    """Service for interacting with Strava API."""

    def __init__(self, db: Session):
        """
        Initialize Strava service.

        Args:
            db: Database session
        """
        self.db = db
        self.client = Client()

    @staticmethod
    def get_authorization_url(redirect_uri: str) -> tuple[str, str]:
        """
        Get Strava OAuth authorization URL.

        Args:
            redirect_uri: OAuth callback URL

        Returns:
            Tuple of (authorization_url, state)
        """
        client = Client()
        url = client.authorization_url(
            client_id=settings.STRAVA_CLIENT_ID,
            redirect_uri=redirect_uri,
            scope=["read", "activity:read", "activity:read_all"]
        )
        return url, ""

    def exchange_code_for_token(self, code: str) -> Dict[str, Any]:
        """
        Exchange authorization code for access token.

        Args:
            code: Authorization code from OAuth callback

        Returns:
            Dictionary containing token information
        """
        token_response = self.client.exchange_code_for_token(
            client_id=settings.STRAVA_CLIENT_ID,
            client_secret=settings.STRAVA_CLIENT_SECRET,
            code=code
        )
        return token_response

    def save_auth(self, user: User, token_response: Dict[str, Any], athlete: Any = None) -> StravaAuth:
        """
        Save Strava authentication data for a user.

        Args:
            user: User object
            token_response: Token response from Strava OAuth
            athlete: Athlete object from Strava API (optional)

        Returns:
            Created or updated StravaAuth object
        """
        # Check if auth already exists
        strava_auth = self.db.query(StravaAuth).filter(
            StravaAuth.user_id == user.id
        ).first()

        # Extract athlete ID
        if athlete:
            athlete_id = str(athlete.id)
        else:
            # Fallback to token response if athlete not provided
            athlete_info = token_response.get("athlete", {})
            athlete_id = str(athlete_info.get("id", "unknown"))

        expires_at = datetime.fromtimestamp(token_response["expires_at"])

        if strava_auth:
            # Update existing auth
            strava_auth.access_token = token_response["access_token"]
            strava_auth.refresh_token = token_response["refresh_token"]
            strava_auth.expires_at = expires_at
            strava_auth.athlete_id = athlete_id
            strava_auth.updated_at = datetime.utcnow()
        else:
            # Create new auth
            strava_auth = StravaAuth(
                user_id=user.id,
                athlete_id=athlete_id,
                access_token=token_response["access_token"],
                refresh_token=token_response["refresh_token"],
                expires_at=expires_at
            )
            self.db.add(strava_auth)

        self.db.commit()
        self.db.refresh(strava_auth)
        return strava_auth

    def get_authenticated_client(self, user: User) -> Optional[Client]:
        """
        Get authenticated Strava client for a user.

        Args:
            user: User object

        Returns:
            Authenticated Strava client or None if not authenticated
        """
        strava_auth = user.strava_auth
        if not strava_auth:
            return None

        # Check if token needs refresh
        if datetime.utcnow() >= strava_auth.expires_at:
            strava_auth = self._refresh_token(strava_auth)

        client = Client()
        client.access_token = strava_auth.access_token
        return client

    def _refresh_token(self, strava_auth: StravaAuth) -> StravaAuth:
        """
        Refresh expired access token.

        Args:
            strava_auth: StravaAuth object with expired token

        Returns:
            Updated StravaAuth object
        """
        logger.info(f"Refreshing Strava token for user {strava_auth.user_id}")

        token_response = self.client.refresh_access_token(
            client_id=settings.STRAVA_CLIENT_ID,
            client_secret=settings.STRAVA_CLIENT_SECRET,
            refresh_token=strava_auth.refresh_token
        )

        strava_auth.access_token = token_response["access_token"]
        strava_auth.refresh_token = token_response["refresh_token"]
        strava_auth.expires_at = datetime.fromtimestamp(token_response["expires_at"])
        strava_auth.updated_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(strava_auth)

        return strava_auth

    def get_activity(self, user: User, activity_id: int) -> Optional[Any]:
        """
        Get activity details from Strava.

        Args:
            user: User object
            activity_id: Strava activity ID

        Returns:
            Activity object or None if not found
        """
        client = self.get_authenticated_client(user)
        if not client:
            return None

        try:
            activity = client.get_activity(activity_id)
            return activity
        except Exception as e:
            logger.error(f"Error fetching activity {activity_id}: {e}")
            return None

    def get_activity_streams(self, user: User, activity_id: int) -> Optional[Dict]:
        """
        Get activity stream data (GPS, heart rate, etc.).

        Args:
            user: User object
            activity_id: Strava activity ID

        Returns:
            Dictionary of streams or None if error
        """
        client = self.get_authenticated_client(user)
        if not client:
            return None

        try:
            types = ["time", "latlng", "altitude", "heartrate", "cadence", "watts", "temp"]
            streams = client.get_activity_streams(activity_id, types=types)
            return streams
        except Exception as e:
            logger.error(f"Error fetching streams for activity {activity_id}: {e}")
            return None

    @staticmethod
    def create_webhook_subscription(callback_url: str) -> Dict[str, Any]:
        """
        Create a webhook subscription with Strava.

        Args:
            callback_url: URL to receive webhook events

        Returns:
            Subscription details
        """
        client = Client()
        subscription = client.create_subscription(
            client_id=settings.STRAVA_CLIENT_ID,
            client_secret=settings.STRAVA_CLIENT_SECRET,
            callback_url=callback_url,
            verify_token=settings.STRAVA_WEBHOOK_VERIFY_TOKEN
        )
        return subscription
