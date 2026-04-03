"""
Sync management routes.
"""

import logging
import os
import tempfile
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.database import get_db
from app.utils.file_storage import get_file_path
from app.utils.user_settings import get_garmin_to_strava_sync_enabled
from app.middleware.auth import get_current_user
from app.models import SyncLog, User
from app.services.garmin_service import GarminService
from app.services.garmin_to_strava_sync_service import GarminToStravaSyncService
from app.services.sync_service import SyncService

logger = logging.getLogger(__name__)
router = APIRouter()


class SyncRequest(BaseModel):
    """Request model for manual sync (Strava to Garmin)."""

    strava_activity_id: str  # String to handle 64-bit IDs safely in JS


class GarminSyncRequest(BaseModel):
    """Request model for manual sync (Garmin to Strava)."""

    garmin_activity_id: str


class SyncLogResponse(BaseModel):
    """Response model for sync log."""

    id: int
    sync_direction: str
    source_activity_id: str
    target_activity_id: Optional[str]
    strava_activity_id: str  # Legacy field for backward compatibility
    garmin_activity_id: Optional[str]  # Legacy field for backward compatibility
    status: str
    error_message: Optional[str]
    activity_name: Optional[str]
    activity_type: Optional[str]
    created_at: datetime
    completed_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class SyncLogDetailResponse(BaseModel):
    """Response model for sync log with limited debug data.

    Note: Sensitive fields like session_data and raw GPX data are excluded
    for security reasons as they may contain credentials or precise location data.
    """

    id: int
    sync_direction: str
    source_activity_id: str
    target_activity_id: Optional[str]
    strava_activity_id: str  # Legacy field for backward compatibility
    garmin_activity_id: Optional[str]  # Legacy field for backward compatibility
    status: str
    error_message: Optional[str]
    activity_name: Optional[str]
    activity_type: Optional[str]
    uploaded_file_extension: Optional[str]  # File type sent: "fit", "gpx", "tcx", etc.
    uploaded_file_path: Optional[str]  # Path to stored file
    file_available: bool  # Whether the file exists on disk and can be downloaded
    strava_data: Optional[Dict]  # Raw Strava activity data
    garmin_data: Optional[str]  # File summary or Garmin response data
    created_at: datetime
    completed_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


@router.post("/manual")
async def manual_sync(
    sync_request: SyncRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Manually trigger sync for a specific Strava activity (Strava → Garmin).
    Always syncs even if activity was already synced before.

    Requires: Bearer token authentication
    """
    user = current_user

    # Check if user has both Strava and Garmin configured
    if not user.strava_auth:
        raise HTTPException(status_code=400, detail="Strava not connected")

    if not user.garmin_auth:
        raise HTTPException(status_code=400, detail="Garmin not connected")

    # Perform sync
    try:
        sync_service = SyncService(db, user)
        # Convert string ID to int for service layer
        activity_id = int(sync_request.strava_activity_id)
        result = sync_service.sync_activity(
            activity_id, force_sync=True  # Always sync for manual requests
        )

        return result

    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid activity ID format")
    except Exception as e:
        db.rollback()
        logger.error(f"Error during manual sync: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/manual/garmin-to-strava")
async def manual_sync_garmin_to_strava(
    sync_request: GarminSyncRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Manually trigger sync for a specific Garmin activity (Garmin → Strava).
    Always syncs even if activity was already synced before.
    Supports activities from the last 90 days.

    Requires: Bearer token authentication
    """
    if not get_garmin_to_strava_sync_enabled(current_user, db):
        raise HTTPException(
            status_code=403,
            detail="Garmin → Strava sync is disabled. Enable it in Settings to sync from Garmin to Strava.",
        )

    user = current_user

    # Check if user has both Strava and Garmin configured
    if not user.strava_auth:
        raise HTTPException(status_code=400, detail="Strava not connected")

    if not user.garmin_auth:
        raise HTTPException(status_code=400, detail="Garmin not connected")

    # Perform sync
    try:
        sync_service = GarminToStravaSyncService(db, user)
        result = sync_service.sync_activity(
            sync_request.garmin_activity_id,
            force_sync=True,  # Always sync for manual requests
            skip_date_filter=True,  # Support old activities up to 90 days
        )

        return result

    except Exception as e:
        db.rollback()
        logger.error(f"Error during manual Garmin to Strava sync: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history", response_model=List[SyncLogResponse])
async def sync_history(
    current_user: User = Depends(get_current_user),
    limit: int = Query(50, description="Maximum number of logs to return"),
    offset: int = Query(0, description="Number of logs to skip"),
    status: Optional[str] = Query(None, description="Filter by status"),
    direction: Optional[str] = Query(
        None, description="Filter by sync direction (strava_to_garmin or garmin_to_strava)"
    ),
    db: Session = Depends(get_db),
):
    """
    Get sync history for the authenticated user.

    Requires: Bearer token authentication
    """
    # Build query
    query = db.query(SyncLog).filter(SyncLog.user_id == current_user.id)

    # Filter by status if provided
    if status:
        query = query.filter(SyncLog.status == status)

    # Filter by direction if provided
    if direction:
        if direction not in ["strava_to_garmin", "garmin_to_strava"]:
            raise HTTPException(
                status_code=400,
                detail="Invalid direction. Must be: strava_to_garmin or garmin_to_strava",
            )
        query = query.filter(SyncLog.sync_direction == direction)

    # Order by created_at descending (most recent first)
    query = query.order_by(SyncLog.created_at.desc())

    # Apply pagination
    logs = query.offset(offset).limit(limit).all()

    return logs


@router.get("/history/{sync_log_id}", response_model=SyncLogResponse)
async def get_sync_log(
    sync_log_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """
    Get details of a specific sync log for the authenticated user.

    Requires: Bearer token authentication
    """
    sync_log = (
        db.query(SyncLog)
        .filter(SyncLog.id == sync_log_id, SyncLog.user_id == current_user.id)
        .first()
    )

    if not sync_log:
        raise HTTPException(status_code=404, detail="Sync log not found")

    return sync_log


@router.get("/history/{sync_log_id}/details", response_model=SyncLogDetailResponse)
async def get_sync_log_details(
    sync_log_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """
    Get detailed sync log for debugging (sensitive data excluded for security).

    Requires: Bearer token authentication
    """
    sync_log = (
        db.query(SyncLog)
        .filter(SyncLog.id == sync_log_id, SyncLog.user_id == current_user.id)
        .first()
    )

    if not sync_log:
        raise HTTPException(status_code=404, detail="Sync log not found")

    # Check if file exists on disk
    file_available = False
    if sync_log.uploaded_file_path and sync_log.uploaded_file_extension:
        from app.utils.file_storage import get_file_path
        try:
            file_path = get_file_path(sync_log.uploaded_file_path)
            file_available = file_path.exists()
        except Exception as e:
            logger.warning(f"Error checking file existence for sync_log {sync_log_id}: {e}")
            file_available = False

    # Create response using model_validate with additional field
    response_data = {
        "id": sync_log.id,
        "sync_direction": sync_log.sync_direction,
        "source_activity_id": sync_log.source_activity_id,
        "target_activity_id": sync_log.target_activity_id,
        "strava_activity_id": sync_log.strava_activity_id,
        "garmin_activity_id": sync_log.garmin_activity_id,
        "status": sync_log.status,
        "error_message": sync_log.error_message,
        "activity_name": sync_log.activity_name,
        "activity_type": sync_log.activity_type,
        "uploaded_file_extension": sync_log.uploaded_file_extension,
        "uploaded_file_path": sync_log.uploaded_file_path,
        "file_available": file_available,
        "strava_data": sync_log.strava_data,
        "garmin_data": sync_log.garmin_data,
        "created_at": sync_log.created_at,
        "completed_at": sync_log.completed_at,
    }

    return SyncLogDetailResponse(**response_data)


@router.get("/history/{sync_log_id}/download-fit")
async def download_sync_log_fit(
    sync_log_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """
    Download the file that was sent during sync. Returns the stored file when available,
    otherwise regenerates (Strava→Garmin) or re-downloads (Garmin→Strava).
    """
    sync_log = (
        db.query(SyncLog)
        .filter(SyncLog.id == sync_log_id, SyncLog.user_id == current_user.id)
        .first()
    )
    if not sync_log:
        raise HTTPException(status_code=404, detail="Sync log not found")
    if sync_log.status != "success":
        raise HTTPException(status_code=400, detail="Only successful syncs can be downloaded")

    activity_id = sync_log.source_activity_id

    # Serve stored file when available
    if sync_log.uploaded_file_path and sync_log.uploaded_file_extension:
        path = get_file_path(sync_log.uploaded_file_path)
        if path.exists():
            ext = sync_log.uploaded_file_extension.strip().lower()
            media_type = {
                "fit": "application/octet-stream",
                "gpx": "application/gpx+xml",
                "tcx": "application/vnd.garmin.tcx+xml",
            }.get(ext, "application/octet-stream")
            with open(path, "rb") as f:
                file_bytes = f.read()
            return Response(
                content=file_bytes,
                media_type=media_type,
                headers={"Content-Disposition": f'attachment; filename="activity-{activity_id}.{ext}"'},
            )
        logger.warning(f"Stored file missing: {sync_log.uploaded_file_path}")

    # Fallback for old sync logs without stored file
    filename = f"activity-{activity_id}.fit"

    if sync_log.sync_direction == "strava_to_garmin":
        sync_service = SyncService(db, current_user)
        fit_bytes = sync_service.get_fit_bytes_for_strava_activity(int(activity_id))
        if not fit_bytes:
            raise HTTPException(
                status_code=502,
                detail="Could not generate FIT file (activity or streams unavailable)",
            )
        return Response(
            content=fit_bytes,
            media_type="application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    if sync_log.sync_direction == "garmin_to_strava":
        garmin_service = GarminService(db)
        if not garmin_service.connect(current_user):
            raise HTTPException(status_code=502, detail="Garmin not connected")
        fd, temp_path = tempfile.mkstemp(suffix=".fit")
        try:
            os.close(fd)
            path = garmin_service.download_activity_original(activity_id, temp_path)
            if not path or not os.path.exists(path):
                raise HTTPException(status_code=502, detail="Could not download FIT from Garmin")
            with open(path, "rb") as f:
                fit_bytes = f.read()
            return Response(
                content=fit_bytes,
                media_type="application/octet-stream",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )
        finally:
            if os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass

    raise HTTPException(status_code=400, detail="Download not supported for this sync direction")


@router.post("/history/{sync_log_id}/retry")
async def retry_sync(
    sync_log_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """
    Retry a failed sync for the authenticated user (supports both directions).

    Requires: Bearer token authentication
    """
    # Get sync log
    sync_log = (
        db.query(SyncLog)
        .filter(SyncLog.id == sync_log_id, SyncLog.user_id == current_user.id)
        .first()
    )

    if not sync_log:
        raise HTTPException(status_code=404, detail="Sync log not found")

    if sync_log.status == "success":
        raise HTTPException(status_code=400, detail="Cannot retry successful sync")

    # Retry sync based on direction
    try:
        if sync_log.sync_direction == "garmin_to_strava":
            # Garmin → Strava retry
            sync_service = GarminToStravaSyncService(db, current_user)
            result = sync_service.sync_activity(
                sync_log.source_activity_id,
                force_sync=True,
                skip_date_filter=True,  # Allow retry of old activities
            )
        else:
            # Strava → Garmin retry (default/legacy)
            sync_service = SyncService(db, current_user)
            result = sync_service.sync_activity(int(sync_log.strava_activity_id), force_sync=True)

        return result

    except Exception as e:
        db.rollback()
        logger.error(f"Error during retry: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def sync_stats(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Get sync statistics for the authenticated user.

    Requires: Bearer token authentication
    """
    # Count logs by status
    total = db.query(SyncLog).filter(SyncLog.user_id == current_user.id).count()
    success = (
        db.query(SyncLog)
        .filter(SyncLog.user_id == current_user.id, SyncLog.status == "success")
        .count()
    )
    failed = (
        db.query(SyncLog)
        .filter(SyncLog.user_id == current_user.id, SyncLog.status == "failed")
        .count()
    )
    skipped = (
        db.query(SyncLog)
        .filter(SyncLog.user_id == current_user.id, SyncLog.status == "skipped")
        .count()
    )

    return {
        "total": total,
        "success": success,
        "failed": failed,
        "skipped": skipped,
        "success_rate": (success / total * 100) if total > 0 else 0,
    }


@router.delete("/history/{sync_log_id}")
async def delete_sync_log(
    sync_log_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """
    Delete a specific sync log entry for the authenticated user.

    Requires: Bearer token authentication
    """
    try:
        # Get sync log with user authorization
        sync_log = (
            db.query(SyncLog)
            .filter(SyncLog.id == sync_log_id, SyncLog.user_id == current_user.id)
            .first()
        )

        if not sync_log:
            raise HTTPException(status_code=404, detail="Sync log not found")

        # Delete associated file if it exists
        if sync_log.uploaded_file_path:
            from app.utils.file_storage import delete_uploaded_file
            try:
                delete_uploaded_file(sync_log.uploaded_file_path)
                logger.info(f"Deleted file for sync_log {sync_log_id}: {sync_log.uploaded_file_path}")
            except Exception as e:
                logger.warning(f"Failed to delete file for sync_log {sync_log_id}: {e}")

        # Delete the sync log
        db.delete(sync_log)
        db.commit()

        logger.info(f"Deleted sync log {sync_log_id} for user {current_user.id}")

        return {"message": "Sync log deleted successfully", "deleted_id": sync_log_id}

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting sync log {sync_log_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to delete sync log: {str(e)}")


@router.delete("/history")
async def bulk_delete_sync_logs(
    current_user: User = Depends(get_current_user),
    status: Optional[str] = Query(
        None, description="Delete only logs with this status (success/failed/skipped/pending)"
    ),
    before_date: Optional[datetime] = Query(
        None, description="Delete logs created before this date (ISO format)"
    ),
    strava_activity_id: Optional[str] = Query(
        None, description="Delete logs for specific Strava activity ID"
    ),
    db: Session = Depends(get_db),
):
    """
    Bulk delete sync logs for the authenticated user with optional filters.

    Requires: Bearer token authentication

    Examples:
    - DELETE /history?status=failed  (delete all failed logs)
    - DELETE /history?before_date=2024-01-01T00:00:00  (delete logs before date)
    - DELETE /history  (delete all logs for authenticated user)
    """
    try:
        # Build query
        query = db.query(SyncLog).filter(SyncLog.user_id == current_user.id)

        # Apply filters
        if status:
            if status not in ["success", "failed", "skipped", "pending"]:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid status. Must be: success, failed, skipped, or pending",
                )
            query = query.filter(SyncLog.status == status)

        if before_date:
            query = query.filter(SyncLog.created_at < before_date)

        if strava_activity_id:
            query = query.filter(SyncLog.strava_activity_id == strava_activity_id)

        # Count before deletion
        count = query.count()

        if count == 0:
            return {"message": "No sync logs found matching the criteria", "deleted_count": 0}

        # Get sync logs to delete their associated files
        sync_logs_to_delete = query.all()
        from app.utils.file_storage import delete_uploaded_file
        
        # Delete associated files
        files_deleted = 0
        for sync_log in sync_logs_to_delete:
            if sync_log.uploaded_file_path:
                try:
                    delete_uploaded_file(sync_log.uploaded_file_path)
                    files_deleted += 1
                except Exception as e:
                    logger.warning(f"Failed to delete file for sync_log {sync_log.id}: {e}")

        # Delete matching logs
        query.delete(synchronize_session=False)
        db.commit()
        
        if files_deleted > 0:
            logger.info(f"Deleted {files_deleted} associated file(s) during bulk delete")

        logger.info(
            f"Bulk deleted {count} sync logs for user {current_user.id} (status={status}, before_date={before_date}, strava_activity_id={strava_activity_id})"
        )

        return {"message": f"Successfully deleted {count} sync log(s)", "deleted_count": count}

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error during bulk delete: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to bulk delete sync logs: {str(e)}")
