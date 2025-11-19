"""
Sync management routes.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from datetime import datetime
from app.database import get_db
from app.models import User, SyncLog
from app.services.sync_service import SyncService
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


class SyncRequest(BaseModel):
    """Request model for manual sync."""
    strava_activity_id: int


class SyncLogResponse(BaseModel):
    """Response model for sync log."""
    id: int
    strava_activity_id: str
    garmin_activity_id: Optional[str]
    status: str
    error_message: Optional[str]
    activity_name: Optional[str]
    activity_type: Optional[str]
    created_at: datetime
    completed_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


@router.post("/manual")
async def manual_sync(
    sync_request: SyncRequest,
    user_id: int = Query(..., description="User ID"),
    db: Session = Depends(get_db)
):
    """
    Manually trigger sync for a specific Strava activity.
    """
    # Get user
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Check if user has both Strava and Garmin configured
    if not user.strava_auth:
        raise HTTPException(status_code=400, detail="Strava not connected")

    if not user.garmin_auth:
        raise HTTPException(status_code=400, detail="Garmin not connected")

    # Perform sync
    try:
        sync_service = SyncService(db, user)
        result = sync_service.sync_activity(sync_request.strava_activity_id)

        return result

    except Exception as e:
        logger.error(f"Error during manual sync: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history", response_model=List[SyncLogResponse])
async def sync_history(
    user_id: int = Query(..., description="User ID"),
    limit: int = Query(50, description="Maximum number of logs to return"),
    offset: int = Query(0, description="Number of logs to skip"),
    status: Optional[str] = Query(None, description="Filter by status"),
    db: Session = Depends(get_db)
):
    """
    Get sync history for a user.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Build query
    query = db.query(SyncLog).filter(SyncLog.user_id == user_id)

    # Filter by status if provided
    if status:
        query = query.filter(SyncLog.status == status)

    # Order by created_at descending (most recent first)
    query = query.order_by(SyncLog.created_at.desc())

    # Apply pagination
    logs = query.offset(offset).limit(limit).all()

    return logs


@router.get("/history/{sync_log_id}", response_model=SyncLogResponse)
async def get_sync_log(
    sync_log_id: int,
    user_id: int = Query(..., description="User ID"),
    db: Session = Depends(get_db)
):
    """
    Get details of a specific sync log.
    """
    sync_log = db.query(SyncLog).filter(
        SyncLog.id == sync_log_id,
        SyncLog.user_id == user_id
    ).first()

    if not sync_log:
        raise HTTPException(status_code=404, detail="Sync log not found")

    return sync_log


@router.post("/history/{sync_log_id}/retry")
async def retry_sync(
    sync_log_id: int,
    user_id: int = Query(..., description="User ID"),
    db: Session = Depends(get_db)
):
    """
    Retry a failed sync.
    """
    # Get sync log
    sync_log = db.query(SyncLog).filter(
        SyncLog.id == sync_log_id,
        SyncLog.user_id == user_id
    ).first()

    if not sync_log:
        raise HTTPException(status_code=404, detail="Sync log not found")

    if sync_log.status == "success":
        raise HTTPException(status_code=400, detail="Cannot retry successful sync")

    # Get user
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Retry sync
    try:
        sync_service = SyncService(db, user)
        result = sync_service.sync_activity(int(sync_log.strava_activity_id))

        return result

    except Exception as e:
        logger.error(f"Error during retry: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def sync_stats(
    user_id: int = Query(..., description="User ID"),
    db: Session = Depends(get_db)
):
    """
    Get sync statistics for a user.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Count logs by status
    total = db.query(SyncLog).filter(SyncLog.user_id == user_id).count()
    success = db.query(SyncLog).filter(
        SyncLog.user_id == user_id,
        SyncLog.status == "success"
    ).count()
    failed = db.query(SyncLog).filter(
        SyncLog.user_id == user_id,
        SyncLog.status == "failed"
    ).count()
    skipped = db.query(SyncLog).filter(
        SyncLog.user_id == user_id,
        SyncLog.status == "skipped"
    ).count()

    return {
        "total": total,
        "success": success,
        "failed": failed,
        "skipped": skipped,
        "success_rate": (success / total * 100) if total > 0 else 0
    }
