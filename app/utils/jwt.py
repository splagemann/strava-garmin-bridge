"""
JWT token utilities for authentication.
"""
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from app.config import settings
import secrets
import logging

logger = logging.getLogger(__name__)

# JWT Configuration
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token.

    Args:
        data: Dictionary of claims to encode in the token
        expires_delta: Optional expiration time delta

    Returns:
        Encoded JWT token string
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "access"
    })

    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Verify and decode a JWT token.

    Args:
        token: JWT token string

    Returns:
        Decoded token payload or None if invalid
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])

        # Verify token type
        if payload.get("type") != "access":
            logger.warning("Invalid token type")
            return None

        return payload

    except JWTError as e:
        logger.warning(f"JWT validation error: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error verifying token: {e}")
        return None


def generate_state_token() -> str:
    """
    Generate a cryptographically secure state token for OAuth CSRF protection.

    Returns:
        Random state token string
    """
    return secrets.token_urlsafe(32)


def create_state_token(state: str, expires_in_minutes: int = 10) -> str:
    """
    Create a signed state token for OAuth flow CSRF protection.

    Args:
        state: Random state value
        expires_in_minutes: Token expiration time in minutes

    Returns:
        Signed JWT state token
    """
    expire = datetime.utcnow() + timedelta(minutes=expires_in_minutes)

    to_encode = {
        "state": state,
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "state"
    }

    encoded = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)
    return encoded


def verify_state_token(token: str, expected_state: str) -> bool:
    """
    Verify OAuth state token.

    Args:
        token: Signed state token
        expected_state: Expected state value

    Returns:
        True if valid, False otherwise
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])

        # Verify token type and state
        if payload.get("type") != "state":
            logger.warning("Invalid state token type")
            return False

        if payload.get("state") != expected_state:
            logger.warning("State mismatch")
            return False

        return True

    except JWTError as e:
        logger.warning(f"State token validation error: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error verifying state token: {e}")
        return False
