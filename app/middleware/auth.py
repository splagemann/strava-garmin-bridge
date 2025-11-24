"""
Authentication middleware and dependencies.
"""

import logging
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.utils.jwt import verify_token

logger = logging.getLogger(__name__)

# HTTP Bearer token scheme
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)
) -> User:
    """
    Dependency to get current authenticated user from JWT token.

    Args:
        credentials: HTTP Authorization header with Bearer token
        db: Database session

    Returns:
        Current authenticated User object

    Raises:
        HTTPException: If token is invalid or user not found
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Extract token
    token = credentials.credentials

    # Verify and decode token
    payload = verify_token(token)
    if payload is None:
        logger.warning("Invalid or expired token")
        raise credentials_exception

    # Extract user_id from payload
    user_id_str: Optional[str] = payload.get("sub")
    if user_id_str is None:
        logger.warning("Token missing 'sub' claim")
        raise credentials_exception

    try:
        user_id = int(user_id_str)
    except (ValueError, TypeError):
        logger.warning(f"Invalid 'sub' claim format: {user_id_str}")
        raise credentials_exception

    # Get user from database
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        logger.warning(f"User {user_id} not found in database")
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="User account is inactive"
        )

    return user


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """
    Dependency to get current user if authenticated, None otherwise.
    Useful for optional authentication on public endpoints.

    Args:
        credentials: Optional HTTP Authorization header
        db: Database session

    Returns:
        User object if authenticated, None otherwise
    """
    if credentials is None:
        return None

    try:
        token = credentials.credentials
        payload = verify_token(token)

        if payload is None:
            return None

        user_id_str: Optional[str] = payload.get("sub")
        if user_id_str is None:
            return None

        try:
            user_id = int(user_id_str)
        except (ValueError, TypeError):
            return None

        user = db.query(User).filter(User.id == user_id).first()
        if user and user.is_active:
            return user

    except Exception as e:
        logger.debug(f"Optional auth failed: {e}")

    return None
