"""
Service for managing and applying recurring Garmin workout schedules.
"""

import calendar
import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models import ScheduledWorkoutInstance, User, WorkoutSchedule
from app.services.garmin_service import GarminService

logger = logging.getLogger(__name__)

# Day-name labels matching Python's date.weekday() (0=Mon … 6=Sun)
DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _ensure_instance_recorded(db, user_id: int, workout_id: str, date_str: str) -> None:
    """Insert a ScheduledWorkoutInstance row if one doesn't already exist."""
    from sqlalchemy.exc import IntegrityError

    existing = (
        db.query(ScheduledWorkoutInstance)
        .filter(
            ScheduledWorkoutInstance.user_id == user_id,
            ScheduledWorkoutInstance.workout_id == workout_id,
            ScheduledWorkoutInstance.scheduled_date == date_str,
        )
        .first()
    )
    if existing:
        return
    try:
        db.add(ScheduledWorkoutInstance(
            user_id=user_id,
            workout_id=workout_id,
            scheduled_date=date_str,
        ))
        db.commit()
    except IntegrityError:
        db.rollback()  # race condition — another request already inserted it


class WorkoutScheduleService:
    """CRUD and application logic for recurring workout schedules."""

    def __init__(self, db: Session, user: User) -> None:
        self.db = db
        self.user = user
        self.garmin_service = GarminService(db)

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def list_schedules(self) -> List[WorkoutSchedule]:
        return (
            self.db.query(WorkoutSchedule)
            .filter(WorkoutSchedule.user_id == self.user.id)
            .order_by(WorkoutSchedule.created_at.desc())
            .all()
        )

    def create_schedule(
        self, workout_id: str, workout_name: str, days_of_week: List[int]
    ) -> WorkoutSchedule:
        """
        Create a new recurring workout schedule.

        Args:
            workout_id: Garmin workout ID.
            workout_name: Human-readable workout name (cached locally).
            days_of_week: List of ints (0=Mon … 6=Sun).
        """
        if not days_of_week:
            raise ValueError("At least one day must be selected")
        invalid = [d for d in days_of_week if d not in range(7)]
        if invalid:
            raise ValueError(f"Invalid day values: {invalid}")

        schedule = WorkoutSchedule(
            user_id=self.user.id,
            workout_id=str(workout_id),
            workout_name=workout_name,
            days_of_week=sorted(set(days_of_week)),
        )
        self.db.add(schedule)
        self.db.commit()
        self.db.refresh(schedule)
        logger.info(
            f"Created workout schedule {schedule.id} for user {self.user.id}: "
            f"'{workout_name}' on days {schedule.days_of_week}"
        )
        return schedule

    def delete_schedule(self, schedule_id: int) -> bool:
        schedule = (
            self.db.query(WorkoutSchedule)
            .filter(
                WorkoutSchedule.id == schedule_id,
                WorkoutSchedule.user_id == self.user.id,
            )
            .first()
        )
        if not schedule:
            return False
        self.db.delete(schedule)
        self.db.commit()
        logger.info(f"Deleted workout schedule {schedule_id} for user {self.user.id}")
        return True

    def toggle_schedule(self, schedule_id: int, is_active: bool) -> Optional[WorkoutSchedule]:
        schedule = (
            self.db.query(WorkoutSchedule)
            .filter(
                WorkoutSchedule.id == schedule_id,
                WorkoutSchedule.user_id == self.user.id,
            )
            .first()
        )
        if not schedule:
            return None
        schedule.is_active = is_active
        schedule.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(schedule)
        return schedule

    # ------------------------------------------------------------------
    # Garmin API helpers
    # ------------------------------------------------------------------

    def fetch_garmin_workouts(self) -> Optional[List[Dict[str, Any]]]:
        """Connect to Garmin and return the full workout library."""
        if not self.garmin_service.connect(self.user):
            logger.error(f"Could not connect to Garmin for user {self.user.id}")
            return None
        return self.garmin_service.get_workouts()

    # ------------------------------------------------------------------
    # Schedule application
    # ------------------------------------------------------------------

    def apply_for_date(self, target_date: Optional[date] = None) -> List[Dict[str, Any]]:
        """
        Push all active schedules whose day_of_week matches target_date to Garmin.

        Returns a list of per-schedule result dicts:
            {"date", "schedule_id", "workout_name", "success", "result"|"error"}
        """
        if target_date is None:
            target_date = date.today()

        if not self.garmin_service.connect(self.user):
            raise RuntimeError("Could not connect to Garmin Connect")

        # Fetch Garmin-side scheduled dates for duplicate detection
        active_schedules = (
            self.db.query(WorkoutSchedule)
            .filter(
                WorkoutSchedule.user_id == self.user.id,
                WorkoutSchedule.is_active.is_(True),
            )
            .all()
        )
        garmin_scheduled: Dict[str, set] = {
            s.workout_id: self.garmin_service.get_scheduled_dates_for_workout(s.workout_id)
            for s in active_schedules
        }
        return self._apply_date_connected(target_date, garmin_scheduled)

    def _apply_date_connected(
        self,
        target_date: date,
        garmin_scheduled: Optional[Dict[str, set]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Apply schedules for a single date, assuming Garmin is already connected.

        garmin_scheduled: pre-fetched map of {workout_id: set_of_iso_date_strings}
            from Garmin's schedule endpoint. When provided, used to skip workouts
            that are already on the Garmin calendar (including manually-scheduled ones).
        """
        if garmin_scheduled is None:
            garmin_scheduled = {}

        day_of_week = target_date.weekday()  # 0=Mon … 6=Sun
        date_str = target_date.isoformat()

        active_schedules = (
            self.db.query(WorkoutSchedule)
            .filter(
                WorkoutSchedule.user_id == self.user.id,
                WorkoutSchedule.is_active.is_(True),
            )
            .all()
        )

        matching = [s for s in active_schedules if day_of_week in (s.days_of_week or [])]

        if not matching:
            logger.debug(
                f"No active schedules for user {self.user.id} on "
                f"{DAY_NAMES[day_of_week]} ({date_str})"
            )
            return []

        results: List[Dict[str, Any]] = []
        for schedule in matching:
            # 1. Check Garmin's own calendar (catches manually-scheduled workouts too)
            if date_str in garmin_scheduled.get(schedule.workout_id, set()):
                logger.debug(
                    f"Skipping '{schedule.workout_name}' on {date_str} — already on Garmin calendar"
                )
                # Sync our local DB so future runs skip the API call
                _ensure_instance_recorded(self.db, self.user.id, schedule.workout_id, date_str)
                results.append(
                    {
                        "date": date_str,
                        "schedule_id": schedule.id,
                        "workout_name": schedule.workout_name,
                        "success": True,
                        "skipped": True,
                        "reason": "already on Garmin calendar",
                    }
                )
                continue

            # 2. Check our local DB (fast path for workouts we previously pushed)
            already_local = (
                self.db.query(ScheduledWorkoutInstance)
                .filter(
                    ScheduledWorkoutInstance.user_id == self.user.id,
                    ScheduledWorkoutInstance.workout_id == schedule.workout_id,
                    ScheduledWorkoutInstance.scheduled_date == date_str,
                )
                .first()
            )
            if already_local:
                logger.debug(
                    f"Skipping '{schedule.workout_name}' on {date_str} — in local record"
                )
                results.append(
                    {
                        "date": date_str,
                        "schedule_id": schedule.id,
                        "workout_name": schedule.workout_name,
                        "success": True,
                        "skipped": True,
                        "reason": "already scheduled",
                    }
                )
                continue

            try:
                result = self.garmin_service.schedule_workout(schedule.workout_id, date_str)
                if result is not None:
                    _ensure_instance_recorded(self.db, self.user.id, schedule.workout_id, date_str)

                results.append(
                    {
                        "date": date_str,
                        "schedule_id": schedule.id,
                        "workout_name": schedule.workout_name,
                        "success": result is not None,
                        "result": result,
                    }
                )
                logger.info(
                    f"Scheduled '{schedule.workout_name}' for {date_str} (user {self.user.id})"
                )
            except Exception as exc:
                logger.error(
                    f"Failed to schedule '{schedule.workout_name}' for {date_str}: {exc}",
                    exc_info=True,
                )
                results.append(
                    {
                        "date": date_str,
                        "schedule_id": schedule.id,
                        "workout_name": schedule.workout_name,
                        "success": False,
                        "error": str(exc),
                    }
                )

        return results

    def apply_for_next_days(self, days: int = 30) -> List[Dict[str, Any]]:
        """
        Push active schedules for every day from today through the next N days (inclusive).

        Garmin is connected once, then we pre-fetch each workout's already-scheduled
        dates from Garmin so the loop can skip duplicates without extra API calls.

        Returns a flat list of per-schedule/per-date result dicts:
            {"date", "schedule_id", "workout_name", "success", "result"|"error"}
        """
        today = date.today()
        end = today + timedelta(days=days - 1)

        if not self.garmin_service.connect(self.user):
            raise RuntimeError("Could not connect to Garmin Connect")

        # Pre-fetch Garmin-side scheduled dates for every active workout, once.
        # This catches manually-scheduled workouts that our local DB doesn't know about.
        active_schedules = (
            self.db.query(WorkoutSchedule)
            .filter(
                WorkoutSchedule.user_id == self.user.id,
                WorkoutSchedule.is_active.is_(True),
            )
            .all()
        )
        unique_workout_ids = {s.workout_id for s in active_schedules}
        garmin_scheduled: Dict[str, set] = {
            wid: self.garmin_service.get_scheduled_dates_for_workout(wid)
            for wid in unique_workout_ids
        }
        logger.info(
            f"Pre-fetched Garmin schedule for {len(unique_workout_ids)} workout(s) "
            f"(user {self.user.id})"
        )

        all_results: List[Dict[str, Any]] = []
        current = today
        while current <= end:
            day_results = self._apply_date_connected(current, garmin_scheduled)
            all_results.extend(day_results)
            current += timedelta(days=1)

        logger.info(
            f"Next-{days}-days sync for user {self.user.id}: "
            f"{len(all_results)} entries from {today} to {end}"
        )
        return all_results
