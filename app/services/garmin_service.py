"""
Garmin Connect service for authentication and activity upload.
"""
from garminconnect import Garmin, GarminConnectAuthenticationError, GarminConnectConnectionError
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
from app.models import User, GarminAuth
from app.utils.crypto import encrypt, decrypt
import logging
import json

logger = logging.getLogger(__name__)


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
        garmin_auth = self.db.query(GarminAuth).filter(
            GarminAuth.user_id == user.id
        ).first()

        if garmin_auth:
            # Update existing auth
            garmin_auth.encrypted_email = encrypted_email
            garmin_auth.encrypted_password = encrypted_password
        else:
            # Create new auth
            garmin_auth = GarminAuth(
                user_id=user.id,
                encrypted_email=encrypted_email,
                encrypted_password=encrypted_password
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

        # Decrypt credentials
        email = decrypt(garmin_auth.encrypted_email)
        password = decrypt(garmin_auth.encrypted_password)

        try:
            # Try to restore session from database
            if garmin_auth.session_data:
                try:
                    logger.info(f"Attempting to restore Garmin session from database for user {user.id}")
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

            # Login returns tuple: (status, mfa_data) where status can be "needs_mfa" or None
            login_result = self.client.login()

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

    def upload_activity(self, file_path: str, activity_format: str = ".gpx") -> Optional[Dict[str, Any]]:
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

            logger.info(f"Upload response type: {type(upload_response)}")
            logger.info(f"Upload response: {upload_response}")

            # Parse response to extract activity ID
            # Response format varies, could be dict or object with activity_id
            if isinstance(upload_response, dict):
                return upload_response
            elif hasattr(upload_response, '__dict__'):
                # Convert object to dict
                return vars(upload_response)
            else:
                # Return as-is wrapped in dict
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
            start_date: Start date in format YYYY-MM-DD
            limit: Maximum number of activities to fetch

        Returns:
            List of activities or None if error
        """
        if not self.client:
            logger.error("Garmin client not connected")
            return None

        try:
            activities = self.client.get_activities(0, limit)
            return activities
        except Exception as e:
            logger.error(f"Error fetching Garmin activities: {e}")
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
            import zipfile
            import io
            import os

            logger.info(f"Downloading original activity file for activity {activity_id}")

            # Download activity in ORIGINAL format (returns zip file bytes)
            zip_data = self.client.download_activity(activity_id, dl_fmt=self.client.ActivityDownloadFormat.ORIGINAL)

            if not zip_data:
                logger.error(f"No data returned for activity {activity_id}")
                return None

            # Extract FIT file from zip
            with zipfile.ZipFile(io.BytesIO(zip_data)) as zip_file:
                # Find FIT file in zip (usually there's only one)
                fit_files = [f for f in zip_file.namelist() if f.lower().endswith('.fit')]

                if not fit_files:
                    logger.error(f"No FIT file found in downloaded zip for activity {activity_id}")
                    return None

                # Extract the first FIT file
                fit_filename = fit_files[0]
                logger.info(f"Extracting {fit_filename} from zip")

                fit_data = zip_file.read(fit_filename)

                # Save to output path
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                with open(output_path, 'wb') as f:
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
        try:
            logger.info(f"Attempting to verify Garmin credentials for {email}")

            # Use garminconnect with the correct login pattern
            client = Garmin(email=email, password=password)

            # Login returns tuple: (status, mfa_data)
            login_result = client.login()

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
        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e) if str(e) else 'No details available'}"
            logger.error(f"Error verifying credentials: {error_msg}", exc_info=True)
            return False, error_msg
