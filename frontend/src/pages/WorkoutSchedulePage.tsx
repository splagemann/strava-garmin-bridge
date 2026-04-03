import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { workoutsApi } from '../api';
import type { GarminWorkout, WorkoutSchedule, SyncSchedulesResult } from '../types';
import { useAuth } from '../hooks/useAuth';

const SYNC_DAYS = 30;

const DAY_LABELS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

function resolveWorkoutName(w: GarminWorkout): string {
  return w.workoutName ?? w.name ?? `Workout ${w.workoutId}`;
}

function DayPicker({
  selected,
  onChange,
}: {
  selected: number[];
  onChange: (days: number[]) => void;
}) {
  const toggle = (day: number) => {
    onChange(
      selected.includes(day) ? selected.filter((d) => d !== day) : [...selected, day].sort(),
    );
  };
  return (
    <div className="flex gap-1 flex-wrap">
      {DAY_LABELS.map((label, idx) => (
        <button
          key={idx}
          type="button"
          onClick={() => toggle(idx)}
          className={`w-10 h-10 rounded-full text-xs font-semibold border transition-colors cursor-pointer ${
            selected.includes(idx)
              ? 'bg-primary text-white border-primary'
              : 'bg-white text-gray-600 border-gray-300 hover:border-primary hover:text-primary'
          }`}
        >
          {label}
        </button>
      ))}
    </div>
  );
}

function ScheduleRow({
  schedule,
  onDelete,
  onToggle,
}: {
  schedule: WorkoutSchedule;
  onDelete: (id: number) => void;
  onToggle: (id: number, active: boolean) => void;
}) {
  return (
    <div
      className={`flex items-center justify-between p-4 rounded-lg border ${
        schedule.is_active ? 'bg-white border-gray-200' : 'bg-gray-50 border-gray-200 opacity-60'
      }`}
    >
      <div className="flex-1 min-w-0">
        <p className="font-medium text-gray-900 truncate">{schedule.workout_name}</p>
        <div className="flex gap-1 mt-1 flex-wrap">
          {DAY_LABELS.map((label, idx) => (
            <span
              key={idx}
              className={`px-2 py-0.5 rounded text-xs font-medium ${
                schedule.days_of_week.includes(idx)
                  ? 'bg-primary/10 text-primary'
                  : 'bg-gray-100 text-gray-400'
              }`}
            >
              {label}
            </span>
          ))}
        </div>
      </div>
      <div className="flex items-center gap-2 ml-4 shrink-0">
        <button
          type="button"
          onClick={() => onToggle(schedule.id, !schedule.is_active)}
          className={`text-xs px-3 py-1 rounded border cursor-pointer transition-colors ${
            schedule.is_active
              ? 'border-gray-300 text-gray-600 hover:bg-gray-50'
              : 'border-green-400 text-green-700 hover:bg-green-50'
          }`}
        >
          {schedule.is_active ? 'Pause' : 'Resume'}
        </button>
        <button
          type="button"
          onClick={() => onDelete(schedule.id)}
          className="text-xs px-3 py-1 rounded border border-red-300 text-red-600 hover:bg-red-50 cursor-pointer transition-colors"
        >
          Delete
        </button>
      </div>
    </div>
  );
}

export default function WorkoutSchedulePage() {
  const { authStatus } = useAuth();
  const navigate = useNavigate();
  const garminConnected = authStatus?.garmin_connected ?? false;

  // ── workout library ──────────────────────────────────────────────────
  const [library, setLibrary] = useState<GarminWorkout[]>([]);
  const [loadingLibrary, setLoadingLibrary] = useState(false);
  const [libraryError, setLibraryError] = useState<string | null>(null);

  // ── schedules ────────────────────────────────────────────────────────
  const [schedules, setSchedules] = useState<WorkoutSchedule[]>([]);
  const [loadingSchedules, setLoadingSchedules] = useState(false);

  // ── create form ──────────────────────────────────────────────────────
  const [selectedWorkoutId, setSelectedWorkoutId] = useState('');
  const [selectedDays, setSelectedDays] = useState<number[]>([]);
  const [creating, setCreating] = useState(false);

  // ── sync ─────────────────────────────────────────────────────────────
  const [syncing, setSyncing] = useState(false);
  const [syncingToday, setSyncingToday] = useState(false);
  const [syncResults, setSyncResults] = useState<SyncSchedulesResult[] | null>(null);
  const [syncLabel, setSyncLabel] = useState<string>('');

  // ── load data ────────────────────────────────────────────────────────
  useEffect(() => {
    if (!garminConnected) return;
    loadLibrary();
    loadSchedules();
  }, [garminConnected]);

  const loadLibrary = async () => {
    setLoadingLibrary(true);
    setLibraryError(null);
    try {
      const data = await workoutsApi.listLibrary();
      setLibrary(data);
    } catch (err: any) {
      const msg = err.response?.data?.detail ?? 'Failed to load Garmin workouts';
      setLibraryError(msg);
    } finally {
      setLoadingLibrary(false);
    }
  };

  const loadSchedules = async () => {
    setLoadingSchedules(true);
    try {
      const data = await workoutsApi.listSchedules();
      setSchedules(data);
    } catch {
      // non-critical
    } finally {
      setLoadingSchedules(false);
    }
  };

  // ── handlers ─────────────────────────────────────────────────────────
  const handleCreate = async () => {
    if (!selectedWorkoutId) return toast.error('Please select a workout');
    if (selectedDays.length === 0) return toast.error('Please select at least one day');

    const workout = library.find((w) => String(w.workoutId) === selectedWorkoutId);
    if (!workout) return;

    setCreating(true);
    try {
      const schedule = await workoutsApi.createSchedule({
        workout_id: selectedWorkoutId,
        workout_name: resolveWorkoutName(workout),
        days_of_week: selectedDays,
      });
      setSchedules((prev) => [schedule, ...prev]);
      setSelectedWorkoutId('');
      setSelectedDays([]);
      toast.success(`Schedule created for "${resolveWorkoutName(workout)}"`);
    } catch (err: any) {
      toast.error(err.response?.data?.detail ?? 'Failed to create schedule');
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Delete this workout schedule?')) return;
    try {
      await workoutsApi.deleteSchedule(id);
      setSchedules((prev) => prev.filter((s) => s.id !== id));
      toast.success('Schedule deleted');
    } catch (err: any) {
      toast.error(err.response?.data?.detail ?? 'Failed to delete schedule');
    }
  };

  const handleToggle = async (id: number, is_active: boolean) => {
    try {
      const updated = await workoutsApi.toggleSchedule(id, is_active);
      setSchedules((prev) => prev.map((s) => (s.id === id ? updated : s)));
    } catch (err: any) {
      toast.error(err.response?.data?.detail ?? 'Failed to update schedule');
    }
  };

  const handleSyncMonth = async () => {
    setSyncing(true);
    setSyncResults(null);
    setSyncLabel(`Next ${SYNC_DAYS} days`);
    try {
      const response = await workoutsApi.syncMonth({ days: SYNC_DAYS });
      setSyncResults(response.results);
      const { applied, succeeded, failed, skipped } = response;
      if (applied === 0 && skipped === 0) {
        toast.info(`No scheduled days in the next ${SYNC_DAYS} days — nothing to push`);
      } else if (applied === 0 && skipped > 0) {
        toast.info(`All ${skipped} workout${skipped !== 1 ? 's' : ''} already scheduled — nothing new to push`);
      } else if (failed === 0) {
        const skipNote = skipped > 0 ? `, ${skipped} already scheduled` : '';
        toast.success(`Pushed ${succeeded} workout${succeeded !== 1 ? 's' : ''} to Garmin${skipNote}`);
      } else {
        toast.warning(`${succeeded} pushed, ${failed} failed${skipped > 0 ? `, ${skipped} already scheduled` : ''}`);
      }
    } catch (err: any) {
      toast.error(err.response?.data?.detail ?? 'Sync failed');
    } finally {
      setSyncing(false);
    }
  };

  const handleSyncToday = async () => {
    setSyncingToday(true);
    setSyncResults(null);
    const now = new Date();
    setSyncLabel(`Today (${now.toLocaleDateString(undefined, { weekday: 'long', month: 'short', day: 'numeric' })})`);
    try {
      const response = await workoutsApi.syncSchedules();
      setSyncResults(response.results);
      if (response.applied === 0) {
        toast.info('No schedules matched today — nothing to push');
      } else if (response.failed === 0) {
        toast.success(
          `Pushed ${response.succeeded} workout${response.succeeded !== 1 ? 's' : ''} to Garmin`,
        );
      } else {
        toast.warning(`${response.succeeded} succeeded, ${response.failed} failed`);
      }
    } catch (err: any) {
      toast.error(err.response?.data?.detail ?? 'Sync failed');
    } finally {
      setSyncingToday(false);
    }
  };

  // ── render ───────────────────────────────────────────────────────────
  if (!garminConnected) {
    return (
      <div className="max-w-2xl mx-auto py-12 text-center">
        <div className="text-4xl mb-4">🏋️</div>
        <h2 className="text-xl font-semibold text-gray-700 mb-2">Garmin not connected</h2>
        <p className="text-gray-500">
          Connect your Garmin account in Settings to manage workout schedules.
        </p>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto space-y-8">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Workout Schedules</h1>
          <p className="text-sm text-gray-500 mt-1">
            Set up recurring weekly schedules and push them to your Garmin calendar.
          </p>
        </div>
        <div className="flex flex-col items-end gap-2 shrink-0">
          {/* Primary: Sync Month */}
          <button
            type="button"
            onClick={handleSyncMonth}
            disabled={syncing || syncingToday || schedules.filter((s) => s.is_active).length === 0}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-primary text-white text-sm font-medium
              hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors cursor-pointer"
          >
            {syncing ? (
              <>
                <span className="animate-spin inline-block w-4 h-4 border-2 border-white border-t-transparent rounded-full" />
                Syncing…
              </>
            ) : (
              <>
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
                Sync Next 30 Days
              </>
            )}
          </button>
          {/* Secondary: Sync Today */}
          <button
            type="button"
            onClick={handleSyncToday}
            disabled={syncing || syncingToday || schedules.filter((s) => s.is_active).length === 0}
            className="inline-flex items-center gap-1 text-xs text-gray-500 hover:text-primary
              disabled:opacity-40 disabled:cursor-not-allowed transition-colors cursor-pointer"
          >
            {syncingToday ? (
              <span className="animate-spin inline-block w-3 h-3 border border-gray-400 border-t-transparent rounded-full" />
            ) : (
              <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
            )}
            Sync Today only
          </button>
        </div>
      </div>

      {/* Sync results */}
      {syncResults !== null && (
        <div className="rounded-lg border border-gray-200 overflow-hidden">
          <div className="px-4 py-2 bg-gray-50 border-b flex items-center justify-between">
            <span className="text-sm font-medium text-gray-700">
              Results — {syncLabel}
            </span>
            <button
              type="button"
              onClick={() => setSyncResults(null)}
              className="text-xs text-gray-400 hover:text-gray-600 cursor-pointer"
            >
              Dismiss
            </button>
          </div>
          {syncResults.length === 0 ? (
            <p className="px-4 py-3 text-sm text-gray-500">No matching scheduled days in this period.</p>
          ) : (() => {
            // Group results by date
            const byDate = syncResults.reduce<Record<string, SyncSchedulesResult[]>>((acc, r) => {
              (acc[r.date] = acc[r.date] ?? []).push(r);
              return acc;
            }, {});
            return (
              <ul className="divide-y">
                {Object.entries(byDate).map(([d, rows]) => (
                  <li key={d}>
                    <div className="px-4 py-1.5 bg-gray-50/60 text-xs font-semibold text-gray-500 uppercase tracking-wide">
                      {new Date(d + 'T00:00:00').toLocaleDateString(undefined, {
                        weekday: 'short', month: 'short', day: 'numeric',
                      })}
                    </div>
                    <ul>
                      {rows.map((r, i) => (
                        <li key={i} className="flex items-center gap-3 px-4 py-2 text-sm border-t border-gray-100 first:border-0">
                          <span className={`w-2 h-2 rounded-full shrink-0 ${
                            r.skipped ? 'bg-gray-300' : r.success ? 'bg-green-500' : 'bg-red-500'
                          }`} />
                          <span className={`flex-1 ${r.skipped ? 'text-gray-400' : 'text-gray-700'}`}>
                            {r.workout_name}
                          </span>
                          {r.skipped && <span className="text-gray-400 text-xs">already scheduled</span>}
                          {r.error && <span className="text-red-500 text-xs">{r.error}</span>}
                        </li>
                      ))}
                    </ul>
                  </li>
                ))}
              </ul>
            );
          })()}
        </div>
      )}

      {/* ── Create schedule card ── */}
      <div className="bg-white rounded-xl border border-gray-200 p-6 space-y-5">
        <h2 className="text-lg font-semibold text-gray-800">Add Schedule</h2>

        {/* Workout picker */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Workout
          </label>
          {loadingLibrary ? (
            <div className="flex items-center gap-2 text-sm text-gray-500">
              <span className="animate-spin inline-block w-4 h-4 border-2 border-primary border-t-transparent rounded-full" />
              Loading your Garmin workouts…
            </div>
          ) : libraryError ? (
            <div className="rounded-md bg-red-50 border border-red-200 px-4 py-3 space-y-2">
              <p className="text-sm text-red-700">{libraryError}</p>
              <div className="flex gap-3">
                <button
                  type="button"
                  onClick={() => navigate('/settings')}
                  className="text-sm font-medium text-white bg-primary hover:bg-primary/90 px-3 py-1 rounded cursor-pointer"
                >
                  Re-authenticate Garmin
                </button>
                <button
                  type="button"
                  onClick={loadLibrary}
                  className="text-sm text-gray-600 hover:text-gray-900 underline cursor-pointer"
                >
                  Retry
                </button>
              </div>
            </div>
          ) : library.length === 0 ? (
            <p className="text-sm text-gray-500">
              No saved workouts found in your Garmin account.
            </p>
          ) : (
            <select
              value={selectedWorkoutId}
              onChange={(e) => setSelectedWorkoutId(e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm
                focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary"
            >
              <option value="">— Select a workout —</option>
              {library.map((w) => (
                <option key={String(w.workoutId)} value={String(w.workoutId)}>
                  {resolveWorkoutName(w)}
                  {w.sportType?.sportTypeKey ? ` · ${w.sportType.sportTypeKey}` : ''}
                </option>
              ))}
            </select>
          )}
        </div>

        {/* Day picker */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Repeat on
          </label>
          <DayPicker selected={selectedDays} onChange={setSelectedDays} />
          {selectedDays.length > 0 && (
            <p className="mt-1 text-xs text-gray-500">
              Every{' '}
              {selectedDays
                .map((d) => DAY_LABELS[d])
                .join(', ')}
            </p>
          )}
        </div>

        <button
          type="button"
          onClick={handleCreate}
          disabled={creating || !selectedWorkoutId || selectedDays.length === 0}
          className="w-full py-2 px-4 bg-primary text-white rounded-lg text-sm font-medium
            hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors cursor-pointer"
        >
          {creating ? 'Saving…' : 'Add Schedule'}
        </button>
      </div>

      {/* ── Existing schedules ── */}
      <div>
        <h2 className="text-lg font-semibold text-gray-800 mb-3">Your Schedules</h2>
        {loadingSchedules ? (
          <div className="flex items-center gap-2 text-sm text-gray-500 py-4">
            <span className="animate-spin inline-block w-4 h-4 border-2 border-primary border-t-transparent rounded-full" />
            Loading…
          </div>
        ) : schedules.length === 0 ? (
          <div className="text-center py-10 text-gray-400 border border-dashed border-gray-200 rounded-xl">
            <div className="text-3xl mb-2">📅</div>
            <p className="text-sm">No workout schedules yet.</p>
            <p className="text-xs mt-1">Add one above to get started.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {schedules.map((s) => (
              <ScheduleRow
                key={s.id}
                schedule={s}
                onDelete={handleDelete}
                onToggle={handleToggle}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
