"""
Garmin Connect service for authentication and activity upload.
"""

import json
import logging
import threading
import time
import uuid
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from garminconnect import Garmin, GarminConnectAuthenticationError, GarminConnectConnectionError
from garth.exc import GarthException
from sqlalchemy.orm import Session

from app.models import GarminAuth, User
from app.utils.crypto import decrypt, encrypt

logger = logging.getLogger(__name__)

# In-memory store for MFA pending state (Garmin client + client_state not serializable).
# Key: mfa_token (str), Value: dict with garmin, client_state, email, password, user_id, created_at
_MFA_PENDING: Dict[str, Dict[str, Any]] = {}
_MFA_LOCK = threading.Lock()
_MFA_TTL_SECONDS = 300  # 5 minutes


class GarminService:
    """Service for interacting with Garmin Connect."""

    def __init__(self, db: Session):
        """
        Initialize Garmin service.

        Args:
            db: Database session
        """
        self.db = db
        self.client: Optional[Garmin] = None

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
        # Encrypt credentials
        encrypted_email = encrypt(email)
        encrypted_password = encrypt(password)

        # Check if auth already exists
        garmin_auth = self.db.query(GarminAuth).filter(GarminAuth.user_id == user.id).first()

        if garmin_auth:
            # Update existing auth
            garmin_auth.encrypted_email = encrypted_email
            garmin_auth.encrypted_password = encrypted_password
        else:
            # Create new auth
            garmin_auth = GarminAuth(
                user_id=user.id,
                encrypted_email=encrypted_email,
                encrypted_password=encrypted_password,
            )
            self.db.add(garmin_auth)

        self.db.commit()
        self.db.refresh(garmin_auth)
        return garmin_auth

    def _mfa_cleanup_expired(self) -> None:
        """Remove expired MFA pending entries."""
        now = time.time()
        with _MFA_LOCK:
            expired = [
                k for k, v in _MFA_PENDING.items() if (now - v["created_at"]) > _MFA_TTL_SECONDS
            ]
            for k in expired:
                del _MFA_PENDING[k]

    def start_login_with_mfa(self, user_id: int, email: str, password: str) -> Tuple[str, Any]:
        """
        Start Garmin login; supports MFA by returning early when MFA is required.

        Args:
            user_id: Current user id (for completing MFA later).
            email: Garmin Connect email.
            password: Garmin Connect password.

        Returns:
            ("mfa_required", mfa_token) when MFA code is needed; caller should
            call complete_mfa(mfa_token, mfa_code, user_id) with the code.
            ("success", garmin_client) when login completed without MFA; caller
            should save credentials and session from the client.
        """
        self._mfa_cleanup_expired()
        try:
            client = Garmin(email=email, password=password, return_on_mfa=True)
            login_result = client.login()
        except GarminConnectAuthenticationError as e:
            logger.error(f"Garmin login (MFA flow) auth failed: {e}")
            raise
        except GarminConnectConnectionError as e:
            logger.error(f"Garmin login (MFA flow) connection error: {e}")
            raise

        if login_result and login_result[0] == "needs_mfa":
            client_state = login_result[1]
            mfa_token = str(uuid.uuid4())
            with _MFA_LOCK:
                _MFA_PENDING[mfa_token] = {
                    "garmin": client,
                    "client_state": client_state,
                    "email": email,
                    "password": password,
                    "user_id": user_id,
                    "created_at": time.time(),
                }
            logger.info(f"MFA required for Garmin login, token issued for user {user_id}")
            return "mfa_required", mfa_token

        # Login succeeded without MFA
        logger.info("Garmin login succeeded without MFA")
        return "success", client

    def complete_mfa(self, mfa_token: str, mfa_code: str, user: User) -> Tuple[bool, Optional[str]]:
        """
        Complete Garmin login with MFA code and save credentials + session.

        Args:
            mfa_token: Token returned from start_login_with_mfa when MFA was required.
            mfa_code: MFA code from the user (e.g. from authenticator app).
            user: User to attach Garmin credentials to.

        Returns:
            (True, None) on success; (False, error_message) on failure.
        """
        self._mfa_cleanup_expired()
        with _MFA_LOCK:
            pending = _MFA_PENDING.pop(mfa_token, None)
        if not pending:
            return (
                False,
                "MFA session expired or invalid. Please submit your Garmin credentials again.",
            )

        now = time.time()
        if (now - pending["created_at"]) > _MFA_TTL_SECONDS:
            return False, "MFA session expired. Please submit your Garmin credentials again."

        garmin_client = pending["garmin"]
        client_state = pending["client_state"]
        email = pending["email"]
        password = pending["password"]

        try:
            garmin_client.resume_login(client_state, mfa_code)
        except GarminConnectAuthenticationError as e:
            logger.warning(f"MFA completion failed for user {user.id}: {e}")
            return False, "Invalid MFA code. Please try again."
        except GarminConnectConnectionError as e:
            logger.warning(f"MFA completion connection error for user {user.id}: {e}")
            return False, str(e)
        except GarthException as e:
            msg = str(e).strip() if str(e) else ""
            logger.warning(f"MFA completion (Garth) for user {user.id}: {e}")
            if "csrf" in msg.lower() or "session" in msg.lower() or "expired" in msg.lower():
                return (
                    False,
                    "Session expired. Please re-enter your Garmin credentials and try the code again.",
                )
            if "mfa" in msg.lower() or "code" in msg.lower() or "invalid" in msg.lower():
                return False, "Invalid MFA code. Please try again."
            if msg and len(msg) < 120 and "traceback" not in msg.lower():
                return False, f"MFA verification failed: {msg}"
            return (
                False,
                "MFA verification failed. Please re-enter your Garmin credentials and try the code again.",
            )
        except AssertionError as e:
            logger.warning(f"MFA completion assertion for user {user.id}: {e}")
            return (
                False,
                "Session expired or invalid. Please re-enter your Garmin credentials and try again.",
            )
        except Exception as e:
            logger.exception(f"MFA completion error for user {user.id}: {type(e).__name__}: {e}")
            err_msg = str(e).strip() if str(e) else ""
            if (
                err_msg
                and len(err_msg) < 100
                and "\n" not in err_msg
                and "traceback" not in err_msg.lower()
            ):
                return False, f"Verification failed: {err_msg}"
            return False, (
                "Verification failed. Try re-entering your Garmin credentials, then enter the new code from your app quickly."
            )

        try:
            session_json = garmin_client.garth.dumps()
            garmin_auth = self.save_credentials(user, email, password)
            garmin_auth.session_data = session_json
            self.db.commit()
            logger.info(f"Garmin credentials and session saved for user {user.id} after MFA")
            return True, None
        except Exception as e:
            logger.exception(f"Failed to save Garmin credentials after MFA: {e}")
            return False, "Failed to save credentials. Please try again."

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

        # Decrypt credentials
        email = decrypt(garmin_auth.encrypted_email)
        password = decrypt(garmin_auth.encrypted_password)

        try:
            # Try to restore session from database
            if garmin_auth.session_data:
                try:
                    logger.info(
                        f"Attempting to restore Garmin session from database for user {user.id}"
                    )
                    # Initialize Garmin client
                    self.client = Garmin()

                    # Load saved tokens into garth
                    self.client.garth.loads(garmin_auth.session_data)

                    logger.info(f"Successfully restored Garmin session for user {user.id}")
                    return True
                except Exception as e:
                    logger.warning(f"Failed to restore session, will re-login: {e}")

            # Fresh login required
            logger.info(f"Performing fresh Garmin login for user {user.id}")
            self.client = Garmin(email=email, password=password)

            # Login returns tuple: (status, mfa_data) or (OAuth1Token, OAuth2Token).
            # When MFA is required, garth returns ("needs_mfa", state); garminconnect
            # may then access profile before checking, raising AssertionError.
            try:
                login_result = self.client.login()
            except AssertionError as e:
                if "OAuth1 token is required for OAuth2 refresh" in str(e):
                    logger.error(
                        "Garmin login failed for user %s (MFA/OAuth1): %s",
                        user.id,
                        e,
                    )
                    return False
                raise

            # Check if MFA is required
            if login_result and login_result[0] == "needs_mfa":
                error_msg = "MFA/2FA is required for this Garmin account. Please disable 2FA or use app-specific password."
                logger.error(f"{error_msg} for user {user.id}")
                return False

            # Save tokens to database as JSON
            session_json = self.client.garth.dumps()
            garmin_auth.session_data = session_json
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
            # Verify file exists
            import os

            if not os.path.exists(file_path):
                logger.error(f"Activity file does not exist: {file_path}")
                return None

            # New garminconnect API expects file path directly
            # Supported formats: .fit .gpx .tcx
            logger.info(f"Uploading activity from {file_path}")
            upload_response = self.client.upload_activity(file_path)

            # Return the JSON: Response object -> .json(), else dict as-is
            if hasattr(upload_response, "json") and callable(getattr(upload_response, "json")):
                return upload_response.json() if getattr(upload_response, "content", None) else {}
            if isinstance(upload_response, dict):
                return upload_response
            return (
                vars(upload_response)
                if hasattr(upload_response, "__dict__")
                else {"raw_response": upload_response}
            )

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
            # Use get_activities_by_date to fetch activities from start_date to today
            logger.info(f"Fetching Garmin activities from {start_date} onwards")
            activities = self.client.get_activities_by_date(
                startdate=start_date, enddate=None  # None means up to today
            )

            if activities:
                logger.info(f"Fetched {len(activities)} activities from {start_date}")
                # Garmin returns in descending order by default, which is what we want (newest first)
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
            # Try get_activity first (basic activity data)
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

            # Fallback: Try get_activity_details (more comprehensive data)
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

            # If both methods fail, log error
            logger.error(f"Could not fetch activity {activity_id} using any method")
            return None

        except Exception as e:
            logger.error(f"Error fetching Garmin activity {activity_id}: {e}", exc_info=True)
            return None

    def download_activity_original(self, activity_id: str, output_path: str) -> Optional[str]:
        """
        Download original activity file (FIT) from Garmin Connect.

        Args:
            activity_id: Garmin activity ID
            output_path: Path to save the FIT file

        Returns:
            Path to saved FIT file or None if error
        """
        if not self.client:
            logger.error("Garmin client not connected")
            return None

        try:
            import io
            import os
            import zipfile

            logger.info(f"Downloading original activity file for activity {activity_id}")

            # Download activity in ORIGINAL format (returns zip file bytes)
            zip_data = self.client.download_activity(
                activity_id, dl_fmt=self.client.ActivityDownloadFormat.ORIGINAL
            )

            if not zip_data:
                logger.error(f"No data returned for activity {activity_id}")
                return None

            # Extract FIT file from zip
            with zipfile.ZipFile(io.BytesIO(zip_data)) as zip_file:
                # Find FIT file in zip (usually there's only one)
                fit_files = [f for f in zip_file.namelist() if f.lower().endswith(".fit")]

                if not fit_files:
                    logger.error(f"No FIT file found in downloaded zip for activity {activity_id}")
                    return None

                # Extract the first FIT file
                fit_filename = fit_files[0]
                logger.info(f"Extracting {fit_filename} from zip")

                fit_data = zip_file.read(fit_filename)

                # Save to output path
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                with open(output_path, "wb") as f:
                    f.write(fit_data)

                logger.info(f"Saved FIT file to {output_path} ({len(fit_data)} bytes)")
                return output_path

        except Exception as e:
            logger.error(f"Error downloading activity {activity_id}: {e}", exc_info=True)
            return None

    def verify_credentials(self, email: str, password: str) -> tuple[bool, Optional[str]]:
        """
        Verify Garmin credentials by attempting login.

        Args:
            email: Garmin Connect email
            password: Garmin Connect password

        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        _OAUTH1_REFRESH_MSG = "OAuth1 token is required for OAuth2 refresh"

        try:
            logger.info(f"Attempting to verify Garmin credentials for {email}")

            # Use garminconnect with the correct login pattern
            client = Garmin(email=email, password=password)

            # Login returns tuple: (status, mfa_data) or (OAuth1Token, OAuth2Token)
            # When MFA is required, garth returns ("needs_mfa", state) and then
            # garminconnect may access profile before checking, triggering AssertionError
            try:
                login_result = client.login()
            except AssertionError as e:
                if _OAUTH1_REFRESH_MSG in str(e):
                    error_msg = (
                        "MFA/2FA is required for this account. "
                        "Please disable 2FA or use an app-specific password."
                    )
                    logger.warning(f"Garmin login failed (OAuth1/MFA): {e}")
                    return False, error_msg
                raise

            # Check if MFA is required
            if login_result and login_result[0] == "needs_mfa":
                error_msg = "MFA/2FA is required for this account. Please disable 2FA or use app-specific password."
                logger.warning(error_msg)
                return False, error_msg

            logger.info("Garmin credentials verified successfully")
            return True, None

        except GarminConnectAuthenticationError as e:
            error_msg = f"Authentication failed: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
        except GarminConnectConnectionError as e:
            error_msg = f"Connection error: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
        except AssertionError as e:
            if _OAUTH1_REFRESH_MSG in str(e):
                error_msg = (
                    "MFA/2FA is required for this account. "
                    "Please disable 2FA or use an app-specific password."
                )
                logger.warning(f"Garmin verify credentials failed (OAuth1/MFA): {e}")
                return False, error_msg
            raise
        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e) if str(e) else 'No details available'}"
            logger.error(f"Error verifying credentials: {error_msg}", exc_info=True)
            return False, error_msg

    def upload_weight(self, weight_kg: float, timestamp: Optional[datetime] = None) -> bool:
        """
        Upload weight measurement to Garmin Connect.

        Args:
            weight_kg: Weight in kilograms
            timestamp: Measurement timestamp (optional, defaults to now)

        Returns:
            True if success, False otherwise
        """
        if not self.client:
            logger.error("Garmin client not connected")
            return False

        try:
            logger.info(f"Uploading weight {weight_kg}kg to Garmin")

            # Timestamp format expected by garminconnect is not strictly documented in the method signature
            # we saw earlier (it said str | None), but usually it handles it.
            # If None, it uses current time.

            # garminconnect.add_body_composition(timestamp, weight, ...)
            # timestamp can be ISO string or None

            ts_str = timestamp.isoformat() if timestamp else None

            self.client.add_body_composition(timestamp=ts_str, weight=weight_kg)

            logger.info("Successfully uploaded weight to Garmin")
            return True

        except Exception as e:
            logger.error(f"Error uploading weight to Garmin: {e}", exc_info=True)
            return False
