"""
Activity filter management routes.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from app.database import get_db
from app.models import User, ActivityFilter
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


class FilterCreate(BaseModel):
    """Request model for creating a filter."""
    filter_type: str  # "include" or "exclude"
    pattern: str
    is_regex: bool = False
    active: bool = True


class FilterUpdate(BaseModel):
    """Request model for updating a filter."""
    filter_type: Optional[str] = None
    pattern: Optional[str] = None
    is_regex: Optional[bool] = None
    active: Optional[bool] = None


class FilterResponse(BaseModel):
    """Response model for filter."""
    id: int
    filter_type: str
    pattern: str
    is_regex: bool
    active: bool

    model_config = ConfigDict(from_attributes=True)


@router.get("/", response_model=List[FilterResponse])
async def list_filters(
    user_id: int = Query(..., description="User ID"),
    db: Session = Depends(get_db)
):
    """
    List all activity filters for a user.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    filters = db.query(ActivityFilter).filter(
        ActivityFilter.user_id == user_id
    ).all()

    return filters


@router.post("/", response_model=FilterResponse)
async def create_filter(
    filter_data: FilterCreate,
    user_id: int = Query(..., description="User ID"),
    db: Session = Depends(get_db)
):
    """
    Create a new activity filter.
    """
    # Validate filter type
    if filter_data.filter_type not in ["include", "exclude"]:
        raise HTTPException(
            status_code=400,
            detail="filter_type must be 'include' or 'exclude'"
        )

    # Check user exists
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Create filter
    activity_filter = ActivityFilter(
        user_id=user_id,
        filter_type=filter_data.filter_type,
        pattern=filter_data.pattern,
        is_regex=filter_data.is_regex,
        active=filter_data.active
    )

    db.add(activity_filter)
    db.commit()
    db.refresh(activity_filter)

    logger.info(f"Created filter {activity_filter.id} for user {user_id}")

    return activity_filter


@router.get("/{filter_id}", response_model=FilterResponse)
async def get_filter(
    filter_id: int,
    user_id: int = Query(..., description="User ID"),
    db: Session = Depends(get_db)
):
    """
    Get a specific filter by ID.
    """
    activity_filter = db.query(ActivityFilter).filter(
        ActivityFilter.id == filter_id,
        ActivityFilter.user_id == user_id
    ).first()

    if not activity_filter:
        raise HTTPException(status_code=404, detail="Filter not found")

    return activity_filter


@router.put("/{filter_id}", response_model=FilterResponse)
async def update_filter(
    filter_id: int,
    filter_data: FilterUpdate,
    user_id: int = Query(..., description="User ID"),
    db: Session = Depends(get_db)
):
    """
    Update an existing filter.
    """
    activity_filter = db.query(ActivityFilter).filter(
        ActivityFilter.id == filter_id,
        ActivityFilter.user_id == user_id
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

    if filter_data.pattern is not None:
        activity_filter.pattern = filter_data.pattern

    if filter_data.is_regex is not None:
        activity_filter.is_regex = filter_data.is_regex

    if filter_data.active is not None:
        activity_filter.active = filter_data.active

    db.commit()
    db.refresh(activity_filter)

    logger.info(f"Updated filter {filter_id} for user {user_id}")

    return activity_filter


@router.delete("/{filter_id}")
async def delete_filter(
    filter_id: int,
    user_id: int = Query(..., description="User ID"),
    db: Session = Depends(get_db)
):
    """
    Delete a filter.
    """
    activity_filter = db.query(ActivityFilter).filter(
        ActivityFilter.id == filter_id,
        ActivityFilter.user_id == user_id
    ).first()

    if not activity_filter:
        raise HTTPException(status_code=404, detail="Filter not found")

    db.delete(activity_filter)
    db.commit()

    logger.info(f"Deleted filter {filter_id} for user {user_id}")

    return {"message": "Filter deleted successfully"}
