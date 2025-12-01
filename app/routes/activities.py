"""
Activity listing routes for Garmin and Strava.
"""

import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models import SyncLog, User
from app.services.garmin_service import GarminService
from app.services.strava_service import StravaService

logger = logging.getLogger(__name__)
router = APIRouter()


class ActivityResponse(BaseModel):
    """Response model for activity listing."""

    id: str
    name: str
    type: str
    start_date: datetime
    distance: Optional[float]  # in meters
    moving_time: Optional[int]  # in seconds
    elapsed_time: Optional[int]  # in seconds
    total_elevation_gain: Optional[float]  # in meters
    source: str  # 'strava' or 'garmin'
    synced: bool  # whether this activity has been synced
    sync_direction: Optional[str]  # direction if synced: 'strava_to_garmin' or 'garmin_to_strava'

    model_config = ConfigDict(from_attributes=True)


@router.get("/garmin", response_model=List[ActivityResponse])
async def get_garmin_activities(
    current_user: User = Depends(get_current_user),
    limit: int = Query(10, description="Maximum number of activities to return", ge=1, le=50),
    db: Session = Depends(get_db),
):
    """
    Get recent activities from Garmin Connect.

    Requires: Bearer token authentication
    """
    user = current_user

    # Check if user has Garmin configured
    if not user.garmin_auth:
        raise HTTPException(status_code=400, detail="Garmin not connected")

    try:
        # Initialize Garmin service and connect
        garmin_service = GarminService(db)
        if not garmin_service.connect(user):
            raise HTTPException(status_code=500, detail="Failed to connect to Garmin")

        # Get activities from the last 30 days
        from datetime import datetime, timedelta

        start_date = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d")

        activities = garmin_service.get_activities(start_date=start_date, limit=limit)

        if activities is None:
            raise HTTPException(status_code=500, detail="Failed to fetch Garmin activities")

        # Get sync logs for this user to check which activities have been synced
        synced_activities = {}
        sync_logs = (
            db.query(SyncLog)
            .filter(
                SyncLog.user_id == user.id,
                SyncLog.sync_direction == "garmin_to_strava",
                SyncLog.status == "success",
            )
            .all()
        )

        for log in sync_logs:
            synced_activities[log.source_activity_id] = log.sync_direction

        # Transform to response format
        result = []
        for activity in activities[:limit]:  # Ensure we only return requested limit
            # Parse date - handle both formats from Garmin API
            start_date_str = activity.get("startTimeLocal") or activity.get("beginTimestamp")

            # Safely handle None, numeric, or malformed date values
            if start_date_str is None:
                logger.warning(
                    f"Activity {activity.get('activityId')} missing date fields, using current time"
                )
                start_date = datetime.utcnow()
            elif isinstance(start_date_str, (int, float)):
                # Handle timestamp in milliseconds (Garmin sometimes uses this)
                try:
                    start_date = datetime.fromtimestamp(start_date_str / 1000)
                except Exception as e:
                    logger.warning(f"Failed to parse numeric timestamp {start_date_str}: {e}")
                    start_date = datetime.utcnow()
            elif isinstance(start_date_str, str):
                try:
                    # Try ISO format first
                    if "T" in start_date_str:
                        start_date = datetime.fromisoformat(start_date_str.replace("Z", "+00:00"))
                    else:
                        # Try simple format
                        start_date = datetime.strptime(start_date_str, "%Y-%m-%d %H:%M:%S")
                except Exception as e:
                    logger.warning(f"Failed to parse date string {start_date_str}: {e}")
                    start_date = datetime.utcnow()
            else:
                logger.warning(
                    f"Unexpected date type {type(start_date_str)} for activity {activity.get('activityId')}"
                )
                start_date = datetime.utcnow()

            # Extract activity type
            activity_type_raw = activity.get("activityType", "unknown")
            if isinstance(activity_type_raw, dict):
                activity_type = activity_type_raw.get("typeKey", "unknown")
            else:
                activity_type = str(activity_type_raw)

            # Convert time values to integers (Garmin returns floats)
            moving_time = None
            if activity.get("movingDuration") is not None:
                moving_time = int(activity.get("movingDuration"))

            elapsed_time = None
            if activity.get("duration") is not None:
                elapsed_time = int(activity.get("duration"))

            # Check if activity has been synced
            activity_id = str(activity.get("activityId"))
            synced = activity_id in synced_activities
            sync_direction = synced_activities.get(activity_id) if synced else None

            result.append(
                ActivityResponse(
                    id=activity_id,
                    name=activity.get("activityName", "Unnamed Activity"),
                    type=activity_type,
                    start_date=start_date,
                    distance=activity.get("distance"),  # Already in meters
                    moving_time=moving_time,
                    elapsed_time=elapsed_time,
                    total_elevation_gain=activity.get("elevationGain"),  # Already in meters
                    source="garmin",
                    synced=synced,
                    sync_direction=sync_direction,
                )
            )

        logger.info(f"Returning {len(result)} Garmin activities for user {user.id}")
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching Garmin activities: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/strava", response_model=List[ActivityResponse])
async def get_strava_activities(
    current_user: User = Depends(get_current_user),
    limit: int = Query(10, description="Maximum number of activities to return", ge=1, le=50),
    db: Session = Depends(get_db),
):
    """
    Get recent activities from Strava.

    Requires: Bearer token authentication
    """
    user = current_user

    # Check if user has Strava configured
    if not user.strava_auth:
        raise HTTPException(status_code=400, detail="Strava not connected")

    try:
        # Initialize Strava service
        strava_service = StravaService(db)

        # Get recent activities
        # Note: We don't use 'after' parameter because stravalib/Strava API with 'limit'
        # and 'after' returns the OLDEST activities after that date.
        # By omitting 'after', we get the most recent activities.
        activities = strava_service.list_recent_activities(user, limit=limit)

        if activities is None:
            raise HTTPException(status_code=500, detail="Failed to fetch Strava activities")

        # Get sync logs for this user to check which activities have been synced
        synced_activities = {}
        sync_logs = (
            db.query(SyncLog)
            .filter(
                SyncLog.user_id == user.id,
                SyncLog.sync_direction == "strava_to_garmin",
                SyncLog.status == "success",
            )
            .all()
        )

        for log in sync_logs:
            synced_activities[log.source_activity_id] = log.sync_direction

        # Transform to response format
        result = []
        for activity in activities:
            # Convert activity type to string - handle both string and object types
            if activity.type:
                # If it's an object with a root attribute, use that
                if hasattr(activity.type, "root"):
                    activity_type = str(activity.type.root)
                else:
                    activity_type = str(activity.type)
            else:
                activity_type = "unknown"

            # Convert distance to float
            distance = None
            if activity.distance:
                distance = (
                    activity.distance.num
                    if hasattr(activity.distance, "num")
                    else float(activity.distance)
                )

            # Convert moving time to seconds
            moving_time = None
            if activity.moving_time:
                moving_time = (
                    int(activity.moving_time.total_seconds())
                    if hasattr(activity.moving_time, "total_seconds")
                    else int(activity.moving_time)
                )

            # Convert elapsed time to seconds
            elapsed_time = None
            if activity.elapsed_time:
                elapsed_time = (
                    int(activity.elapsed_time.total_seconds())
                    if hasattr(activity.elapsed_time, "total_seconds")
                    else int(activity.elapsed_time)
                )

            # Convert elevation gain to float
            elevation_gain = None
            if activity.total_elevation_gain:
                elevation_gain = (
                    activity.total_elevation_gain.num
                    if hasattr(activity.total_elevation_gain, "num")
                    else float(activity.total_elevation_gain)
                )

            # Check if activity has been synced
            activity_id = str(activity.id)
            synced = activity_id in synced_activities
            sync_direction = synced_activities.get(activity_id) if synced else None

            result.append(
                ActivityResponse(
                    id=activity_id,
                    name=activity.name,
                    type=activity_type,
                    start_date=activity.start_date,
                    distance=distance,
                    moving_time=moving_time,
                    elapsed_time=elapsed_time,
                    total_elevation_gain=elevation_gain,
                    source="strava",
                    synced=synced,
                    sync_direction=sync_direction,
                )
            )

        logger.info(f"Returning {len(result)} Strava activities for user {user.id}")
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching Strava activities: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
