"""
Strava API service for handling OAuth and activity operations.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session
from stravalib.client import Client

from app.config import settings
from app.models import StravaAuth, User

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
        Get Strava OAuth authorization URL with CSRF state token.

        Args:
            redirect_uri: OAuth callback URL

        Returns:
            Tuple of (authorization_url, signed_state_token)
        """
        from app.utils.jwt import create_state_token, generate_state_token

        # Generate cryptographically secure random state
        state = generate_state_token()

        # Create signed JWT token containing the state
        signed_state = create_state_token(state)

        client = Client()
        # Pass the random state to Strava OAuth
        url = client.authorization_url(
            client_id=settings.STRAVA_CLIENT_ID,
            redirect_uri=redirect_uri,
            scope=["read", "activity:read", "activity:read_all", "activity:write"],
            state=state,  # CSRF protection
        )
        return url, signed_state

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
            code=code,
        )
        return token_response

    def save_auth(
        self, user: User, token_response: Dict[str, Any], athlete: Any = None
    ) -> StravaAuth:
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
        strava_auth = self.db.query(StravaAuth).filter(StravaAuth.user_id == user.id).first()

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
                expires_at=expires_at,
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
            refresh_token=strava_auth.refresh_token,
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

    def list_recent_activities(
        self, user: User, after: Optional[datetime] = None, limit: int = 50
    ) -> list[Any]:
        """
        List recent activities for a user.

        Args:
            user: User object
            after: Only return activities after this datetime (UTC)
            limit: Maximum number of activities to return

        Returns:
            List of Strava activity objects
        """
        client = self.get_authenticated_client(user)
        if not client:
            return []

        try:
            activities = client.get_activities(after=after, limit=limit)
            # stravalib returns a generator; convert to list so we can iterate multiple times
            return list(activities)
        except Exception as e:
            logger.error(f"Error listing activities for user {user.id}: {e}", exc_info=True)
            return []

    def upload_activity(
        self,
        user: User,
        file_path: str,
        activity_type: Optional[str] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Upload activity file (FIT, GPX, or TCX) to Strava.

        Args:
            user: User object
            file_path: Path to activity file
            activity_type: Optional activity type (e.g., 'ride', 'run')
            name: Optional activity name
            description: Optional activity description

        Returns:
            Dictionary with upload status and activity_id, or None if error
        """
        client = self.get_authenticated_client(user)
        if not client:
            logger.error(f"No authenticated Strava client for user {user.id}")
            return None

        try:
            import os
            import time

            if not os.path.exists(file_path):
                logger.error(f"Activity file does not exist: {file_path}")
                return None

            logger.info(f"Uploading activity to Strava from {file_path}")

            # Determine file format from extension
            file_ext = os.path.splitext(file_path)[1].lower()
            if file_ext not in [".fit", ".gpx", ".tcx"]:
                logger.error(f"Unsupported file format: {file_ext}")
                return None

            # Upload file to Strava
            with open(file_path, "rb") as f:
                uploader = client.upload_activity(
                    activity_file=f,
                    data_type=file_ext[1:],  # Remove the dot: 'fit', 'gpx', or 'tcx'
                    activity_type=activity_type,
                    name=name,
                    description=description,
                )

            logger.info(f"Upload initiated, waiting for processing...")

            # Wait for upload to complete (returns DetailedActivity on success)
            # The wait() method polls Strava until processing is complete
            try:
                activity = uploader.wait(timeout=60, poll_interval=2)

                # Check if the returned object is an ActivityUploader (error/timeout case)
                # or a DetailedActivity (success case)
                if hasattr(activity, "id") and not hasattr(activity, "upload_id"):
                    # This is a DetailedActivity with an id attribute
                    logger.info(f"Upload successful! Activity ID: {activity.id}")
                    return {"success": True, "activity_id": str(activity.id)}
                elif hasattr(uploader, "activity_id") and uploader.activity_id:
                    # Sometimes the uploader object has the activity_id even if wait() didn't return it
                    logger.info(f"Upload successful! Activity ID: {uploader.activity_id}")
                    return {"success": True, "activity_id": str(uploader.activity_id)}
                else:
                    logger.error("Upload completed but no activity ID returned")
                    return {
                        "success": False,
                        "error": "Upload completed but no activity ID returned",
                    }

            except Exception as wait_error:
                # Check if uploader has error information
                if hasattr(uploader, "is_error") and uploader.is_error:
                    error_msg = f"Upload failed during processing: {wait_error}"
                    logger.error(error_msg)
                    return {"success": False, "error": error_msg}
                else:
                    # Timeout or other error
                    logger.warning(f"Upload timeout or error: {wait_error}")
                    return {"success": False, "error": f"Upload timeout: {str(wait_error)}"}

        except Exception as e:
            logger.error(f"Error uploading activity to Strava: {e}", exc_info=True)
            return {"success": False, "error": str(e)}
