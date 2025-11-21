"""
Activity filter management routes.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from app.database import get_db
from app.models import User, ActivityFilter
from app.middleware.auth import get_current_user
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


class FilterCreate(BaseModel):
    """Request model for creating a filter."""
    filter_type: str  # "include" or "exclude"
    filter_field: str = "name"  # "name" or "type" - field to match against
    pattern: str
    is_regex: bool = False
    active: bool = True


class FilterUpdate(BaseModel):
    """Request model for updating a filter."""
    filter_type: Optional[str] = None
    filter_field: Optional[str] = None
    pattern: Optional[str] = None
    is_regex: Optional[bool] = None
    active: Optional[bool] = None


class FilterResponse(BaseModel):
    """Response model for filter."""
    id: int
    filter_type: str
    filter_field: str
    pattern: str
    is_regex: bool
    active: bool

    model_config = ConfigDict(from_attributes=True)


@router.get("/", response_model=List[FilterResponse])
async def list_filters(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List all activity filters for the authenticated user.

    Requires: Bearer token authentication
    """
    filters = db.query(ActivityFilter).filter(
        ActivityFilter.user_id == current_user.id
    ).all()

    return filters


@router.post("/", response_model=FilterResponse)
async def create_filter(
    filter_data: FilterCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new activity filter for the authenticated user.

    Requires: Bearer token authentication
    """
    try:
        # Validate filter type
        if filter_data.filter_type not in ["include", "exclude"]:
            raise HTTPException(
                status_code=400,
                detail="filter_type must be 'include' or 'exclude'"
            )

        # Validate filter field
        if filter_data.filter_field not in ["name", "type"]:
            raise HTTPException(
                status_code=400,
                detail="filter_field must be 'name' or 'type'"
            )

        # Create filter
        activity_filter = ActivityFilter(
            user_id=current_user.id,
            filter_type=filter_data.filter_type,
            filter_field=filter_data.filter_field,
            pattern=filter_data.pattern,
            is_regex=filter_data.is_regex,
            active=filter_data.active
        )

        db.add(activity_filter)
        db.commit()
        db.refresh(activity_filter)

        logger.info(f"Created filter {activity_filter.id} for user {current_user.id}")

        return activity_filter

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating filter: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create filter: {str(e)}")


@router.get("/{filter_id}", response_model=FilterResponse)
async def get_filter(
    filter_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get a specific filter by ID for the authenticated user.

    Requires: Bearer token authentication
    """
    activity_filter = db.query(ActivityFilter).filter(
        ActivityFilter.id == filter_id,
        ActivityFilter.user_id == current_user.id
    ).first()

    if not activity_filter:
        raise HTTPException(status_code=404, detail="Filter not found")

    return activity_filter


@router.put("/{filter_id}", response_model=FilterResponse)
async def update_filter(
    filter_id: int,
    filter_data: FilterUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update an existing filter for the authenticated user.

    Requires: Bearer token authentication
    """
    try:
        activity_filter = db.query(ActivityFilter).filter(
            ActivityFilter.id == filter_id,
            ActivityFilter.user_id == current_user.id
        ).first()

        if not activity_filter:
            raise HTTPException(status_code=404, detail="Filter not found")

        # Update fields
        if filter_data.filter_type is not None:
            if filter_data.filter_type not in ["include", "exclude"]:
                raise HTTPException(
                    status_code=400,
                    detail="filter_type must be 'include' or 'exclude'"
                )
            activity_filter.filter_type = filter_data.filter_type

        if filter_data.filter_field is not None:
            if filter_data.filter_field not in ["name", "type"]:
                raise HTTPException(
                    status_code=400,
                    detail="filter_field must be 'name' or 'type'"
                )
            activity_filter.filter_field = filter_data.filter_field

        if filter_data.pattern is not None:
            activity_filter.pattern = filter_data.pattern

        if filter_data.is_regex is not None:
            activity_filter.is_regex = filter_data.is_regex

        if filter_data.active is not None:
            activity_filter.active = filter_data.active

        db.commit()
        db.refresh(activity_filter)

        logger.info(f"Updated filter {filter_id} for user {current_user.id}")

        return activity_filter

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating filter {filter_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to update filter: {str(e)}")


@router.delete("/{filter_id}")
async def delete_filter(
    filter_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete a filter for the authenticated user.

    Requires: Bearer token authentication
    """
    try:
        activity_filter = db.query(ActivityFilter).filter(
            ActivityFilter.id == filter_id,
            ActivityFilter.user_id == current_user.id
        ).first()

        if not activity_filter:
            raise HTTPException(status_code=404, detail="Filter not found")

        db.delete(activity_filter)
        db.commit()

        logger.info(f"Deleted filter {filter_id} for user {current_user.id}")

        return {"message": "Filter deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting filter {filter_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to delete filter: {str(e)}")
