"""
Routes for Garmin workout scheduling.
"""

import logging
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models import User
from app.services.workout_schedule_service import WorkoutScheduleService

logger = logging.getLogger(__name__)
router = APIRouter()

# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------


class CreateScheduleRequest(BaseModel):
    workout_id: str
    workout_name: str
    days_of_week: List[int]  # 0=Mon … 6=Sun

    @field_validator("days_of_week")
    @classmethod
    def validate_days(cls, v: List[int]) -> List[int]:
        if not v:
            raise ValueError("At least one day must be selected")
        if any(d not in range(7) for d in v):
            raise ValueError("Days must be integers 0–6 (Mon–Sun)")
        return sorted(set(v))


class ToggleScheduleRequest(BaseModel):
    is_active: bool


class SyncRequest(BaseModel):
    date: Optional[str] = None  # ISO date YYYY-MM-DD; defaults to today


class SyncNextDaysRequest(BaseModel):
    days: int = 30  # number of days from today (inclusive)


class WorkoutScheduleResponse(BaseModel):
    id: int
    workout_id: str
    workout_name: str
    days_of_week: List[int]
    is_active: bool
    created_at: str

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/library")
async def list_garmin_workouts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """
    Fetch the current user's saved Garmin workout library.
    Requires Garmin credentials to be connected.
    """
    if not current_user.garmin_auth:
        raise HTTPException(status_code=400, detail="Garmin account not connected")

    svc = WorkoutScheduleService(db, current_user)
    workouts = svc.fetch_garmin_workouts()
    if workouts is None:
        raise HTTPException(
            status_code=502,
            detail="Could not connect to Garmin Connect. Please re-authenticate.",
        )
    return workouts


@router.get("/schedules")
async def list_schedules(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Return all workout schedules for the current user."""
    svc = WorkoutScheduleService(db, current_user)
    schedules = svc.list_schedules()
    return [
        {
            "id": s.id,
            "workout_id": s.workout_id,
            "workout_name": s.workout_name,
            "days_of_week": s.days_of_week,
            "is_active": s.is_active,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        }
        for s in schedules
    ]


@router.post("/schedules", status_code=201)
async def create_schedule(
    body: CreateScheduleRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create a new recurring workout schedule."""
    if not current_user.garmin_auth:
        raise HTTPException(status_code=400, detail="Garmin account not connected")

    svc = WorkoutScheduleService(db, current_user)
    try:
        schedule = svc.create_schedule(
            workout_id=body.workout_id,
            workout_name=body.workout_name,
            days_of_week=body.days_of_week,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    return {
        "id": schedule.id,
        "workout_id": schedule.workout_id,
        "workout_name": schedule.workout_name,
        "days_of_week": schedule.days_of_week,
        "is_active": schedule.is_active,
        "created_at": schedule.created_at.isoformat() if schedule.created_at else None,
    }


@router.patch("/schedules/{schedule_id}")
async def toggle_schedule(
    schedule_id: int,
    body: ToggleScheduleRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Enable or disable a schedule."""
    svc = WorkoutScheduleService(db, current_user)
    schedule = svc.toggle_schedule(schedule_id, body.is_active)
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return {
        "id": schedule.id,
        "workout_id": schedule.workout_id,
        "workout_name": schedule.workout_name,
        "days_of_week": schedule.days_of_week,
        "is_active": schedule.is_active,
        "created_at": schedule.created_at.isoformat() if schedule.created_at else None,
    }


@router.delete("/schedules/{schedule_id}")
async def delete_schedule(
    schedule_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, str]:
    """Delete a workout schedule."""
    svc = WorkoutScheduleService(db, current_user)
    deleted = svc.delete_schedule(schedule_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return {"message": "Schedule deleted"}


@router.post("/schedules/sync")
async def sync_schedules(
    body: SyncRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Manually push all active schedules matching the given date (default: today)
    to Garmin Connect.
    """
    if not current_user.garmin_auth:
        raise HTTPException(status_code=400, detail="Garmin account not connected")

    target: Optional[date] = None
    if body.date:
        try:
            target = date.fromisoformat(body.date)
        except ValueError:
            raise HTTPException(status_code=422, detail="date must be YYYY-MM-DD")

    svc = WorkoutScheduleService(db, current_user)
    try:
        results = svc.apply_for_date(target)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    skipped_count = sum(1 for r in results if r.get("skipped"))
    success_count = sum(1 for r in results if r.get("success") and not r.get("skipped"))
    failed_count = sum(1 for r in results if not r.get("success"))
    return {
        "date": (target or date.today()).isoformat(),
        "applied": len(results) - skipped_count,
        "skipped": skipped_count,
        "succeeded": success_count,
        "failed": failed_count,
        "results": results,
    }


@router.post("/schedules/sync-month")
async def sync_schedules_next_days(
    body: SyncNextDaysRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Push all active schedules for the next N days (default 30) starting today.
    """
    if not current_user.garmin_auth:
        raise HTTPException(status_code=400, detail="Garmin account not connected")

    if body.days < 1 or body.days > 365:
        raise HTTPException(status_code=422, detail="days must be between 1 and 365")

    today = date.today()
    end = today + timedelta(days=body.days - 1)

    svc = WorkoutScheduleService(db, current_user)
    try:
        results = svc.apply_for_next_days(body.days)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    skipped_count = sum(1 for r in results if r.get("skipped"))
    success_count = sum(1 for r in results if r.get("success") and not r.get("skipped"))
    failed_count = sum(1 for r in results if not r.get("success"))
    return {
        "start": today.isoformat(),
        "end": end.isoformat(),
        "days": body.days,
        "applied": len(results) - skipped_count,
        "skipped": skipped_count,
        "succeeded": success_count,
        "failed": failed_count,
        "results": results,
    }
