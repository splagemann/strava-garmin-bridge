"""
Withings API service for handling OAuth and weight data.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional
import httpx
from urllib.parse import urlencode

from sqlalchemy.orm import Session

from app.config import settings
from app.models import WithingsAuth, User
from app.utils.jwt import create_state_token, generate_state_token

logger = logging.getLogger(__name__)


class WithingsService:
    """Service for interacting with Withings API."""

    AUTH_URL = "https://account.withings.com/oauth2_user/authorize2"
    TOKEN_URL = "https://wbsapi.withings.net/v2/oauth2"
    MEASURE_URL = "https://wbsapi.withings.net/measure"

    def __init__(self, db: Session):
        """
        Initialize Withings service.

        Args:
            db: Database session
        """
        self.db = db

    @staticmethod
    def get_authorization_url(redirect_uri: str) -> tuple[str, str]:
        """
        Get Withings OAuth authorization URL with CSRF state token.

        Args:
            redirect_uri: OAuth callback URL

        Returns:
            Tuple of (authorization_url, signed_state_token)
        """
        # Generate cryptographically secure random state
        state = generate_state_token()

        # Create signed JWT token containing the state
        signed_state = create_state_token(state)

        params = {
            "response_type": "code",
            "client_id": settings.WITHINGS_CLIENT_ID,
            "redirect_uri": redirect_uri,
            "scope": "user.metrics",
            "state": state,
        }

        url = f"{WithingsService.AUTH_URL}?{urlencode(params)}"
        return url, signed_state

    def exchange_code_for_token(self, code: str, redirect_uri: str) -> Dict[str, Any]:
        """
        Exchange authorization code for access token.

        Args:
            code: Authorization code from OAuth callback
            redirect_uri: The redirect URI used in the authorization request

        Returns:
            Dictionary containing token information
        """
        data = {
            "action": "requesttoken",
            "grant_type": "authorization_code",
            "client_id": settings.WITHINGS_CLIENT_ID,
            "client_secret": settings.WITHINGS_CLIENT_SECRET,
            "code": code,
            "redirect_uri": redirect_uri,
        }

        try:
            response = httpx.post(self.TOKEN_URL, data=data)
            response.raise_for_status()
            result = response.json()

            if result.get("status") != 0:
                raise Exception(f"Withings API error: {result.get('error', 'Unknown error')}")

            return result["body"]
        except Exception as e:
            logger.error(f"Error exchanging Withings code: {e}")
            raise

    def save_auth(self, user: User, token_response: Dict[str, Any]) -> WithingsAuth:
        """
        Save Withings authentication data for a user.

        Args:
            user: User object
            token_response: Token response from Withings OAuth

        Returns:
            Created or updated WithingsAuth object
        """
        withings_auth = self.db.query(WithingsAuth).filter(WithingsAuth.user_id == user.id).first()

        # Calculate expiration (expires_in is usually seconds)
        expires_in = token_response.get("expires_in", 10800)  # Default 3 hours
        expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

        if withings_auth:
            # Update existing auth
            withings_auth.access_token = token_response["access_token"]
            withings_auth.refresh_token = token_response["refresh_token"]
            withings_auth.expires_at = expires_at
            withings_auth.withings_userid = str(token_response["userid"])
            withings_auth.updated_at = datetime.utcnow()
        else:
            # Create new auth
            withings_auth = WithingsAuth(
                user_id=user.id,
                withings_userid=str(token_response["userid"]),
                access_token=token_response["access_token"],
                refresh_token=token_response["refresh_token"],
                expires_at=expires_at,
            )
            self.db.add(withings_auth)

        self.db.commit()
        self.db.refresh(withings_auth)
        return withings_auth

    def _refresh_token(self, withings_auth: WithingsAuth) -> WithingsAuth:
        """
        Refresh expired access token.

        Args:
            withings_auth: WithingsAuth object with expired token

        Returns:
            Updated WithingsAuth object
        """
        logger.info(f"Refreshing Withings token for user {withings_auth.user_id}")

        data = {
            "action": "requesttoken",
            "grant_type": "refresh_token",
            "client_id": settings.WITHINGS_CLIENT_ID,
            "client_secret": settings.WITHINGS_CLIENT_SECRET,
            "refresh_token": withings_auth.refresh_token,
        }

        try:
            response = httpx.post(self.TOKEN_URL, data=data)
            response.raise_for_status()
            result = response.json()

            if result.get("status") != 0:
                raise Exception(f"Withings API error during refresh: {result.get('error', 'Unknown error')}")

            token_data = result["body"]
            
            expires_in = token_data.get("expires_in", 10800)
            withings_auth.access_token = token_data["access_token"]
            withings_auth.refresh_token = token_data["refresh_token"]
            withings_auth.expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
            withings_auth.updated_at = datetime.utcnow()

            self.db.commit()
            self.db.refresh(withings_auth)
            return withings_auth

        except Exception as e:
            logger.error(f"Error refreshing Withings token: {e}")
            raise

    def get_recent_weights(self, user: User) -> list[Dict[str, Any]]:
        """
        Get recent weight measurements from Withings (last 365 days).

        Args:
            user: User object

        Returns:
            List of dictionaries with weight (kg) and timestamp
        """
        withings_auth = user.withings_auth
        if not withings_auth:
            return []

        # Check if token needs refresh
        if datetime.utcnow() >= withings_auth.expires_at:
            withings_auth = self._refresh_token(withings_auth)

        # Fetch measurements from the last year
        start_date = int((datetime.utcnow() - timedelta(days=365)).timestamp())

        params = {
            "action": "getmeas",
            "meastype": 1,  # Weight
            "category": 1,  # Real measurements
            "startdate": start_date,
        }

        headers = {"Authorization": f"Bearer {withings_auth.access_token}"}

        try:
            response = httpx.post(self.MEASURE_URL, params=params, headers=headers)
            response.raise_for_status()
            result = response.json()

            if result.get("status") != 0:
                logger.error(f"Withings API error fetching measurements: {result.get('error')}")
                return []

            body = result.get("body", {})
            measuregrps = body.get("measuregrps", [])

            if not measuregrps:
                return []

            # Sort by date ascending (oldest first) so we process them in order?
            # Or descending? Order doesn't matter much for syncing individually, 
            # but maybe processing oldest first makes more logical sense for logs.
            # Let's keep it default order (usually descending from API?) or just sort.
            # Sorting by date ascending to sync chronologically.
            measuregrps.sort(key=lambda x: x.get("date"))
            
            measurements = []
            for grp in measuregrps:
                timestamp = grp.get("date")
                measures = grp.get("measures", [])
                
                weight_measure = next((m for m in measures if m.get("type") == 1), None)
                if weight_measure:
                    weight_kg = weight_measure.get("value") * (10 ** weight_measure.get("unit"))
                    measurements.append({
                        "weight": weight_kg,
                        "timestamp": timestamp,
                        "date": datetime.fromtimestamp(timestamp)
                    })
            
            return measurements

        except Exception as e:
            logger.error(f"Error fetching weight from Withings: {e}")
            return []
