export interface GarminWorkout {
  workoutId: string | number;
  /** Garmin may expose the name as `workoutName` or `name` depending on API version */
  workoutName?: string;
  name?: string;
  sportType?: { sportTypeKey?: string; sportTypeId?: number };
  /** Resolved display name */
  displayName?: string;
}

export interface WorkoutSchedule {
  id: number;
  workout_id: string;
  workout_name: string;
  /** 0=Mon … 6=Sun */
  days_of_week: number[];
  is_active: boolean;
  created_at: string;
}

export interface CreateScheduleRequest {
  workout_id: string;
  workout_name: string;
  days_of_week: number[];
}

export interface SyncSchedulesRequest {
  date?: string; // YYYY-MM-DD; omit for today
}

export interface SyncMonthRequest {
  days?: number; // number of days from today, default 30
}

export interface SyncSchedulesResult {
  date: string;       // YYYY-MM-DD — which day this was scheduled on
  schedule_id: number;
  workout_name: string;
  success: boolean;
  skipped?: boolean;  // true when already scheduled — not an error
  reason?: string;
  result?: Record<string, unknown>;
  error?: string;
}

export interface SyncSchedulesResponse {
  date: string;
  applied: number;
  succeeded: number;
  failed: number;
  results: SyncSchedulesResult[];
}

export interface SyncMonthResponse {
  start: string;   // today (YYYY-MM-DD)
  end: string;     // today + days - 1
  days: number;
  applied: number;
  skipped: number;
  succeeded: number;
  failed: number;
  results: SyncSchedulesResult[];
}
