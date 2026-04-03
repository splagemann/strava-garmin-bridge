"""
Garmin Connect service for authentication and activity upload.
"""

import logging
import os
import threading
import time
import uuid
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from garminconnect import (
    Garmin,
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
    GarminConnectTooManyRequestsError,
)
from sqlalchemy.orm import Session

from app.models import GarminAuth, User
from app.utils.crypto import decrypt, encrypt

logger = logging.getLogger(__name__)

# Root directory for per-user DI OAuth token files.
# Mount this path as a persistent Docker volume so tokens survive container restarts.
_TOKEN_ROOT = os.environ.get("GARMIN_TOKEN_DIR", "/backend/data/garmin_tokens")

# Per-user rate-limit backoff: after a 429/auth failure on a fresh login, suppress
# further fresh-login attempts for this many seconds to avoid Cloudflare blocks.
_FRESH_LOGIN_COOLDOWN_SECONDS = 600  # 10 minutes
_fresh_login_failed_at: Dict[int, float] = {}  # user_id → epoch timestamp of last failure
_fresh_login_lock = threading.Lock()

# In-memory store for MFA pending state (Garmin client + client_state not serializable).
# Key: mfa_token (str), Value: dict with garmin, client_state, email, password, user_id, created_at
_MFA_PENDING: Dict[str, Dict[str, Any]] = {}
_MFA_LOCK = threading.Lock()
_MFA_TTL_SECONDS = 300  # 5 minutes


class GarminService:
    """Service for interacting with Garmin Connect."""

    def __init__(self, db: Session):
        self.db = db
        self.client: Optional[Garmin] = None

    # ------------------------------------------------------------------
    # Token persistence helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _token_dir(user_id: int) -> str:
        """Return (and create) the per-user token directory on disk."""
        path = os.path.join(_TOKEN_ROOT, f"user_{user_id}")
        os.makedirs(path, exist_ok=True)
        return path

    def _persist_tokens(self, garmin_client: Garmin, garmin_auth: GarminAuth) -> None:
        """Write DI OAuth tokens to disk AND keep the DB column in sync.
        Also clears any active rate-limit cooldown — valid tokens mean we're unblocked.
        """
        with _fresh_login_lock:
            _fresh_login_failed_at.pop(garmin_auth.user_id, None)

        token_dir = self._token_dir(garmin_auth.user_id)
        try:
            garmin_client.client.dump(token_dir)
        except Exception as exc:
            logger.warning(f"Could not write token file for user {garmin_auth.user_id}: {exc}")

        try:
            session_json = garmin_client.client.dumps()
            garmin_auth.session_data = session_json
            self.db.commit()
        except Exception as exc:
            logger.warning(f"Could not save session to DB for user {garmin_auth.user_id}: {exc}")

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
        except GarminConnectTooManyRequestsError as e:
            logger.error(f"Garmin login (MFA flow) rate-limited: {e}")
            raise
        except GarminConnectAuthenticationError as e:
            logger.error(f"Garmin login (MFA flow) auth failed: {e}")
            raise
        except GarminConnectConnectionError as e:
            logger.error(f"Garmin login (MFA flow) connection error: {e}")
            raise

        if login_result and login_result[0] == "needs_mfa":
            mfa_token = str(uuid.uuid4())
            with _MFA_LOCK:
                _MFA_PENDING[mfa_token] = {
                    "garmin": client,
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
        email = pending["email"]
        password = pending["password"]

        try:
            # client_state is now unused internally (MFA state lives on the client object)
            garmin_client.resume_login(None, mfa_code)
        except GarminConnectAuthenticationError as e:
            logger.warning(f"MFA completion failed for user {user.id}: {e}")
            return False, "Invalid MFA code. Please try again."
        except GarminConnectConnectionError as e:
            logger.warning(f"MFA completion connection error for user {user.id}: {e}")
            msg = str(e).strip()
            if msg and len(msg) < 120 and "traceback" not in msg.lower():
                return False, f"MFA verification failed: {msg}"
            return (
                False,
                "MFA verification failed. Please re-enter your Garmin credentials and try the code again.",
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
            garmin_auth = self.save_credentials(user, email, password)
            self._persist_tokens(garmin_client, garmin_auth)
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

        token_dir = self._token_dir(user.id)
        token_file = os.path.join(token_dir, "garmin_tokens.json")

        # Strip corrupt/empty session_data so it is never used to seed a bad token file.
        if garmin_auth.session_data is not None and not garmin_auth.session_data.strip():
            logger.warning(
                f"Clearing empty/corrupt session_data for user {user.id}"
            )
            garmin_auth.session_data = None
            try:
                self.db.commit()
            except Exception:
                pass

        try:
            # Seed disk from DB on first run / fresh volume mount.
            if garmin_auth.session_data and not os.path.exists(token_file):
                try:
                    with open(token_file, "w") as f:
                        f.write(garmin_auth.session_data)
                    logger.info(f"Seeded token file from DB for user {user.id}")
                except Exception as seed_err:
                    logger.warning(f"Could not seed token file: {seed_err}")

            # Restore from disk — login() handles load + expiry check + proactive refresh.
            if os.path.exists(token_file):
                try:
                    self.client = Garmin()
                    self.client.login(token_dir)
                    self._persist_tokens(self.client, garmin_auth)
                    logger.info(f"Restored Garmin session for user {user.id}")
                    return True
                except (GarminConnectTooManyRequestsError, GarminConnectConnectionError) as e:
                    # Rate-limit or network error — keep the token file (tokens may still be
                    # valid once the throttle lifts) and bail out until next cycle.
                    logger.warning(
                        f"Garmin rate-limit/connection error while restoring session for "
                        f"user {user.id}: {e}. Will retry next cycle."
                    )
                    return False
                except GarminConnectAuthenticationError as e:
                    # Token file contains an incompatible format (e.g. old garth tokens).
                    # This is a local data problem, not Garmin blocking us — delete the
                    # bad file, wipe the DB copy, clear any rate-limit cooldown, and fall
                    # through to attempt a fresh login immediately.
                    logger.warning(
                        f"Token file for user {user.id} has an incompatible format "
                        f"({e}). Clearing stale data and attempting fresh login."
                    )
                    try:
                        os.unlink(token_file)
                    except OSError:
                        pass
                    try:
                        garmin_auth.session_data = None
                        self.db.commit()
                    except Exception:
                        pass
                    with _fresh_login_lock:
                        _fresh_login_failed_at.pop(user.id, None)
                except Exception as e:
                    logger.warning(
                        f"Stale token file for user {user.id}: {e}. Removing and will "
                        "attempt fresh login after cooldown."
                    )
                    try:
                        os.unlink(token_file)
                    except OSError:
                        pass

            # Guard: suppress fresh logins while in the rate-limit cooldown window.
            with _fresh_login_lock:
                last_fail = _fresh_login_failed_at.get(user.id)
            if last_fail and (time.time() - last_fail) < _FRESH_LOGIN_COOLDOWN_SECONDS:
                remaining = int(_FRESH_LOGIN_COOLDOWN_SECONDS - (time.time() - last_fail))
                logger.warning(
                    f"Skipping fresh Garmin login for user {user.id} — still in "
                    f"rate-limit cooldown ({remaining}s remaining). "
                    "Re-authenticate via the app to reset."
                )
                return False

            # Fresh login — only reached when no valid token file exists.
            # return_on_mfa=True prevents a hard exception when MFA is required;
            # instead we get ("needs_mfa",) back and can bail gracefully.
            logger.info(f"Performing fresh Garmin login for user {user.id}")
            self.client = Garmin(email=email, password=password, return_on_mfa=True)
            login_result = self.client.login(token_dir)

            if login_result and login_result[0] == "needs_mfa":
                logger.error(
                    f"MFA required for user {user.id} during background connect. "
                    "Re-authenticate via the app."
                )
                return False

            with _fresh_login_lock:
                _fresh_login_failed_at.pop(user.id, None)
            self._persist_tokens(self.client, garmin_auth)
            logger.info(f"Fresh Garmin login succeeded for user {user.id}")
            return True

        except (GarminConnectTooManyRequestsError, GarminConnectConnectionError) as e:
            logger.error(
                f"Garmin rate-limited / connection error for user {user.id}: {e}. "
                f"Entering {_FRESH_LOGIN_COOLDOWN_SECONDS // 60}-minute cooldown."
            )
            with _fresh_login_lock:
                _fresh_login_failed_at[user.id] = time.time()
            return False
        except GarminConnectAuthenticationError as e:
            logger.error(f"Garmin authentication failed for user {user.id}: {e}")
            with _fresh_login_lock:
                _fresh_login_failed_at[user.id] = time.time()
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

    def import_activity(self, file_path: str) -> Optional[Dict[str, Any]]:
        """
        Import activity file to Garmin Connect using the import endpoint.

        Unlike upload_activity(), this uses the import-style endpoint with
        Garmin Connect Mobile headers so the activity is treated as an import
        and will NOT be re-exported to Strava (preventing ping-pong duplicates).

        Args:
            file_path: Path to activity file (.fit, .tcx, or .gpx)

        Returns:
            DetailedImportResult dict (with successes/failures/internalId) or None if error
        """
        if not self.client:
            logger.error("Garmin client not connected")
            return None

        try:
            import os

            if not os.path.exists(file_path):
                logger.error(f"Activity file does not exist: {file_path}")
                return None

            logger.info(f"Importing activity from {file_path} (will not be re-exported to Strava)")
            result = self.client.import_activity(file_path)

            if isinstance(result, dict):
                return result
            return vars(result) if hasattr(result, "__dict__") else {"raw_response": result}

        except Exception as e:
            # 409 Conflict means Garmin already has this activity — treat as duplicate not an error
            if "409" in str(e) or "duplicate" in str(e).lower():
                logger.warning(f"Activity already exists in Garmin (duplicate): {e}")
                return {"duplicate": True, "message": str(e)}
            logger.error(f"Error importing activity: {e}", exc_info=True)
            return None

    def get_workouts(self, limit: int = 200) -> Optional[list]:
        """
        Fetch all saved workouts from Garmin Connect.

        Returns:
            List of workout dicts (workoutId, name, sport, etc.) or None on error.
        """
        if not self.client:
            logger.error("Garmin client not connected")
            return None

        try:
            logger.info("Fetching Garmin workouts")
            workouts = self.client.get_workouts(0, limit)
            return workouts if isinstance(workouts, list) else []
        except Exception as e:
            logger.error(f"Error fetching Garmin workouts: {e}", exc_info=True)
            return None

    def get_scheduled_dates_for_workout(self, workout_id: str) -> set:
        """
        Fetch all dates on which a specific workout is already scheduled in Garmin.

        Calls GET /workout-service/schedule/{workout_id} — returns a list of objects
        like {"date": "YYYY-MM-DD", ...}.  Returns a set of ISO date strings so callers
        can do O(1) membership tests.

        Returns an empty set on any error (fail-open: we'd rather over-schedule than skip).
        """
        if not self.client:
            return set()

        try:
            # garminconnect exposes low-level API access via connectapi()
            data = self.client.connectapi(
                f"/workout-service/schedule/{workout_id}"
            )
            if isinstance(data, list):
                dates = {entry.get("date") for entry in data if entry.get("date")}
                logger.debug(
                    f"Workout {workout_id} already scheduled on {len(dates)} date(s): {sorted(dates)}"
                )
                return dates
        except Exception as e:
            logger.warning(
                f"Could not fetch scheduled dates for workout {workout_id}: {e}. "
                "Proceeding without Garmin-side duplicate check."
            )
        return set()

    def schedule_workout(self, workout_id: str, date: str) -> Optional[dict]:
        """
        Schedule a Garmin workout on a specific date.

        Args:
            workout_id: Garmin workout ID string.
            date: ISO date string (YYYY-MM-DD).

        Returns:
            Response dict on success, or None on error.
        """
        if not self.client:
            logger.error("Garmin client not connected")
            return None

        try:
            logger.info(f"Scheduling workout {workout_id} for {date}")
            result = self.client.schedule_workout(workout_id, date)
            if isinstance(result, dict):
                return result
            return {"scheduled": True}
        except Exception as e:
            logger.error(f"Error scheduling workout {workout_id} for {date}: {e}", exc_info=True)
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
        try:
            logger.info(f"Attempting to verify Garmin credentials for {email}")

            client = Garmin(email=email, password=password)
            login_result = client.login()

            if login_result and login_result[0] == "needs_mfa":
                error_msg = "MFA/2FA is required for this account. Please disable 2FA or use an app-specific password."
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
        except GarminConnectTooManyRequestsError as e:
            error_msg = f"Rate limit exceeded: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
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
