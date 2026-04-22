"""
Garmin Connect service for authentication and activity upload.
"""

import base64
import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional

import requests
from garminconnect import Garmin, GarminConnectAuthenticationError, GarminConnectConnectionError
from sqlalchemy.orm import Session

from app.models import GarminAuth, User
from app.utils.crypto import decrypt, encrypt

logger = logging.getLogger(__name__)


class _StoredResponse:
    """Minimal response object needed by garminconnect's widget MFA completion."""

    def __init__(self, text: str, url: str):
        self.text = text
        self.url = url


class GarminService:
    """Service for interacting with Garmin Connect."""

    PENDING_MFA_PREFIX = "pending_mfa:"

    def __init__(self, db: Session):
        """
        Initialize Garmin service.

        Args:
            db: Database session
        """
        self.db = db
        self.client: Optional[Garmin] = None

    def _encode_pending_mfa_state(self, garmin_client: Garmin) -> str:
        """Serialize pending MFA client state for temporary storage."""
        mfa_session = garmin_client.client._mfa_session
        state = {
            "cookies": mfa_session.cookies.get_dict(),
            "session_module": mfa_session.__class__.__module__,
            "session_class": mfa_session.__class__.__name__,
            "flow": getattr(garmin_client.client, "_mfa_flow", None),
            "method": getattr(garmin_client.client, "_mfa_method", None),
            "login_params": getattr(garmin_client.client, "_mfa_login_params", None),
            "post_headers": getattr(garmin_client.client, "_mfa_post_headers", None),
            "service_url": getattr(garmin_client.client, "_mfa_service_url", None),
            "portal_service_url": getattr(garmin_client.client, "_portal_service_url", None),
            "sso": getattr(garmin_client.client, "_sso", None),
            "widget_last_resp_text": getattr(
                getattr(garmin_client.client, "_widget_last_resp", None), "text", None
            ),
            "widget_last_resp_url": getattr(
                getattr(garmin_client.client, "_widget_last_resp", None), "url", None
            ),
        }
        payload = json.dumps(state)
        return self.PENDING_MFA_PREFIX + base64.b64encode(payload.encode()).decode()

    def _decode_pending_mfa_state(self, encoded_state: str) -> Dict[str, Any]:
        """Load pending MFA client state from storage."""
        if not encoded_state or not encoded_state.startswith(self.PENDING_MFA_PREFIX):
            raise ValueError("No pending MFA state found")

        raw = encoded_state[len(self.PENDING_MFA_PREFIX) :]
        decoded = base64.b64decode(raw.encode()).decode()
        return json.loads(decoded)

    def _restore_pending_mfa_state(self, garmin_client: Garmin, encoded_state: str) -> None:
        """Restore pending MFA challenge state onto the Garmin client."""
        state = self._decode_pending_mfa_state(encoded_state)

        session = self._create_mfa_session(state)
        cookies = state.get("cookies") or {}
        for key, value in cookies.items():
            session.cookies.set(key, value)

        garmin_client.client._mfa_session = session
        garmin_client.client._mfa_flow = state.get("flow") or "portal"
        garmin_client.client._mfa_method = state.get("method") or "email"
        garmin_client.client._mfa_login_params = state.get("login_params") or {}
        garmin_client.client._mfa_post_headers = state.get("post_headers") or {}
        garmin_client.client._mfa_service_url = state.get("service_url")
        garmin_client.client._portal_service_url = state.get("portal_service_url") or getattr(
            garmin_client.client, "_portal_service_url", None
        )
        garmin_client.client._sso = state.get("sso") or getattr(garmin_client.client, "_sso", None)

        if state.get("widget_last_resp_text"):
            garmin_client.client._widget_last_resp = _StoredResponse(
                text=state["widget_last_resp_text"],
                url=state.get("widget_last_resp_url") or "",
            )

    def _create_mfa_session(self, state: Dict[str, Any]) -> Any:
        """Create an HTTP session compatible with the MFA flow that created the challenge."""
        session_module = state.get("session_module") or ""
        if session_module.startswith("curl_cffi"):
            try:
                from curl_cffi import requests as cffi_requests

                return cffi_requests.Session(impersonate="chrome", timeout=30)
            except Exception as e:
                logger.warning(f"Failed to restore curl_cffi MFA session, using requests: {e}")

        return requests.Session()

    def save_credentials(self, user: User, email: str, password: str) -> GarminAuth:
        """
        Save encrypted Garmin credentials for a user.

        Args:
            user: User object
            email: Garmin Connect email
            password: Garmin Connect password

        Returns:
            Created or updated GarminAuth object
        """
        encrypted_email = encrypt(email)
        encrypted_password = encrypt(password)

        garmin_auth = self.db.query(GarminAuth).filter(GarminAuth.user_id == user.id).first()

        if garmin_auth:
            garmin_auth.encrypted_email = encrypted_email
            garmin_auth.encrypted_password = encrypted_password
            garmin_auth.encrypted_mfa_token = None
            garmin_auth.session_data = None
        else:
            garmin_auth = GarminAuth(
                user_id=user.id,
                encrypted_email=encrypted_email,
                encrypted_password=encrypted_password,
            )
            self.db.add(garmin_auth)

        self.db.commit()
        self.db.refresh(garmin_auth)
        return garmin_auth

    def connect(self, user: User) -> bool:
        """
        Connect to Garmin Connect for a user.

        Args:
            user: User object

        Returns:
            True if connection successful, False otherwise
        """
        garmin_auth = user.garmin_auth
        if not garmin_auth:
            logger.error(f"No Garmin credentials found for user {user.id}")
            return False

        email = decrypt(garmin_auth.encrypted_email)
        password = decrypt(garmin_auth.encrypted_password)

        try:
            if garmin_auth.session_data and not garmin_auth.session_data.startswith(self.PENDING_MFA_PREFIX):
                try:
                    logger.info(
                        f"Attempting to restore Garmin session from database for user {user.id}"
                    )
                    self.client = Garmin()
                    self.client.login(tokenstore=garmin_auth.session_data)
                    logger.info(f"Successfully restored Garmin session for user {user.id}")
                    return True
                except Exception as e:
                    logger.warning(f"Failed to restore session, will re-login: {e}")

            logger.info(f"Performing fresh Garmin login for user {user.id}")
            self.client = Garmin(email=email, password=password, return_on_mfa=True)
            login_result = self.client.login()

            if login_result and login_result[0] == "needs_mfa":
                garmin_auth.encrypted_mfa_token = encrypt(self._encode_pending_mfa_state(self.client))
                garmin_auth.session_data = None
                self.db.commit()
                logger.info(f"Garmin MFA challenge started for user {user.id}")
                return False

            garmin_auth.session_data = self.client.client.dumps()
            garmin_auth.encrypted_mfa_token = None
            self.db.commit()

            logger.info(f"Successfully logged in to Garmin for user {user.id}")
            return True

        except GarminConnectAuthenticationError as e:
            logger.error(f"Garmin authentication failed for user {user.id}: {e}")
            return False
        except GarminConnectConnectionError as e:
            logger.error(f"Garmin connection error for user {user.id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Error connecting to Garmin for user {user.id}: {e}", exc_info=True)
            return False

    def complete_mfa(self, user: User, mfa_code: str) -> tuple[bool, Optional[str]]:
        """Complete a pending Garmin MFA login and persist session data."""
        garmin_auth = user.garmin_auth
        if not garmin_auth or not garmin_auth.encrypted_mfa_token:
            return False, "No pending Garmin MFA challenge found"

        try:
            pending_state = decrypt(garmin_auth.encrypted_mfa_token)
            email = decrypt(garmin_auth.encrypted_email)
            password = decrypt(garmin_auth.encrypted_password)

            self.client = Garmin(email=email, password=password, return_on_mfa=True)
            self._restore_pending_mfa_state(self.client, pending_state)
            self.client.resume_login({}, mfa_code)

            garmin_auth.session_data = self.client.client.dumps()
            garmin_auth.encrypted_mfa_token = None
            self.db.commit()
            return True, None
        except GarminConnectAuthenticationError as e:
            logger.error(f"Garmin MFA verification failed for user {user.id}: {e}")
            return False, f"MFA verification failed: {e}"
        except Exception as e:
            logger.error(f"Error completing Garmin MFA for user {user.id}: {e}", exc_info=True)
            return False, str(e)

    def verify_credentials(self, email: str, password: str) -> tuple[bool, Optional[str], Optional[str]]:
        """
        Verify Garmin credentials are valid without storing them.

        Args:
            email: Garmin Connect email
            password: Garmin Connect password

        Returns:
            Tuple of (success: bool, error_message: Optional[str], status: Optional[str])
        """
        try:
            logger.info(f"Verifying Garmin credentials for email: {email[:3]}***")
            client = Garmin(email=email, password=password, return_on_mfa=True)
            login_result = client.login()

            if login_result and login_result[0] == "needs_mfa":
                logger.info("Garmin credentials accepted, MFA required")
                return False, None, "needs_mfa"

            logger.info("Garmin credentials verified successfully")
            return True, None, None

        except GarminConnectAuthenticationError as e:
            error_msg = str(e)
            logger.warning(f"Garmin authentication error during verification: {error_msg}")
            return False, error_msg, None
        except GarminConnectConnectionError as e:
            error_msg = f"Connection error: {str(e)}"
            logger.warning(f"Garmin connection error during verification: {error_msg}")
            return False, error_msg, None
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            logger.warning(f"Garmin verification error: {error_msg}", exc_info=True)
            return False, error_msg, None

    def upload_activity(
        self, file_path: str, activity_format: str = ".gpx"
    ) -> Optional[Dict[str, Any]]:
        """
        Upload activity file to Garmin Connect.

        Args:
            file_path: Path to activity file (GPX or FIT)
            activity_format: File format (.gpx or .fit) - kept for backward compatibility but not used

        Returns:
            Upload response dict or None if error
        """
        if not self.client:
            logger.error("Garmin client not connected")
            return None

        try:
            import os

            if not os.path.exists(file_path):
                logger.error(f"Activity file does not exist: {file_path}")
                return None

            logger.info(f"Uploading activity from {file_path}")
            upload_response = self.client.upload_activity(file_path)

            logger.info(f"Upload response type: {type(upload_response)}")
            logger.info(f"Upload response: {upload_response}")

            if isinstance(upload_response, dict):
                return upload_response
            elif hasattr(upload_response, "__dict__"):
                return vars(upload_response)
            else:
                return {"raw_response": upload_response}

        except GarminConnectConnectionError as e:
            logger.error(f"Connection error uploading activity: {e}", exc_info=True)
            return None
        except Exception as e:
            logger.error(f"Error uploading activity: {e}", exc_info=True)
            return None

    def get_activities(self, start_date: str, limit: int = 10) -> Optional[list]:
        """
        Get recent activities from Garmin Connect.

        Args:
            start_date: Start date in format YYYY-MM-DD (activities from this date forward)
            limit: Maximum number of activities to fetch (note: garminconnect may not respect this limit)

        Returns:
            List of activities or None if error
        """
        if not self.client:
            logger.error("Garmin client not connected")
            return None

        try:
            logger.info(f"Fetching Garmin activities from {start_date} onwards")
            activities = self.client.get_activities_by_date(
                startdate=start_date, enddate=None
            )

            if activities:
                logger.info(f"Fetched {len(activities)} activities from {start_date}")
                return activities
            else:
                logger.info(f"No activities found from {start_date}")
                return []

        except Exception as e:
            logger.error(f"Error fetching Garmin activities from {start_date}: {e}", exc_info=True)
            return None

    def get_activity_by_id(self, activity_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific activity by ID from Garmin Connect.

        Args:
            activity_id: Garmin activity ID

        Returns:
            Activity details dict or None if error
        """
        if not self.client:
            logger.error("Garmin client not connected")
            return None

        try:
            try:
                logger.info(f"Fetching activity {activity_id} using get_activity()")
                activity = self.client.get_activity(activity_id)
                if activity:
                    logger.info(
                        f"Successfully fetched activity {activity_id}: {activity.get('activityName', 'Unknown')}"
                    )
                    return activity
            except Exception as e:
                logger.warning(f"get_activity() failed for {activity_id}: {e}")

            try:
                logger.info(f"Fetching activity {activity_id} using get_activity_details()")
                activity = self.client.get_activity_details(activity_id)
                if activity:
                    logger.info(
                        f"Successfully fetched activity details {activity_id}: {activity.get('activityName', 'Unknown')}"
                    )
                    return activity
            except Exception as e:
                logger.warning(f"get_activity_details() failed for {activity_id}: {e}")

            logger.error(f"Failed to fetch activity {activity_id} with all available methods")
            return None

        except Exception as e:
            logger.error(f"Error fetching Garmin activity {activity_id}: {e}", exc_info=True)
            return None

    def get_body_composition(self, date: str = None) -> Optional[Dict[str, Any]]:
        """
        Get body composition data from Garmin Connect.

        Args:
            date: Date in format YYYY-MM-DD (defaults to today)

        Returns:
            Dict with weight and body composition data or None if error
        """
        if not self.client:
            logger.error("Garmin client not connected")
            return None

        try:
            if date is None:
                date = datetime.now().strftime("%Y-%m-%d")

            logger.info(f"Fetching body composition for date: {date}")
            body_comp = self.client.get_body_composition(date)

            if body_comp:
                logger.info(f"Successfully fetched body composition for {date}")
                return body_comp
            else:
                logger.info(f"No body composition data found for {date}")
                return None

        except Exception as e:
            logger.error(f"Error fetching body composition for {date}: {e}", exc_info=True)
            return None
