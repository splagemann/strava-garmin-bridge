import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import type { Activity } from '../api/activities';
import { activitiesApi } from '../api/activities';
import { syncApi } from '../api/sync';
import { useAuth } from '../hooks/useAuth';
import { formatDateOnly, formatTime } from '../lib/utils';
import { toast } from 'sonner';

interface ActivitiesListProps {
  limit?: number;
}

export function ActivitiesList({ limit = 10 }: ActivitiesListProps) {
  const { authStatus } = useAuth();
  const navigate = useNavigate();
  const garminToStravaEnabled = authStatus?.garmin_to_strava_sync_disabled !== true;
  const displayTimezone = authStatus?.display_timezone ?? 'UTC';
  const hour12 = authStatus?.display_time_format !== '24h';

  const [activities, setActivities] = useState<Activity[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeSource, setActiveSource] = useState<'all' | 'strava' | 'garmin'>('all');
  const [syncingActivityId, setSyncingActivityId] = useState<string | null>(null);
  const [sourceErrors, setSourceErrors] = useState<{ strava?: string; garmin?: string }>({});

  useEffect(() => {
    loadActivities();
  }, [limit]);

  const loadActivities = async () => {
    setLoading(true);
    setSourceErrors({});
    try {
      const errors: { strava?: string; garmin?: string } = {};

      const [stravaActivities, garminActivities] = await Promise.all([
        activitiesApi.getStravaActivities(limit).catch((err: any) => {
          const detail = err?.response?.data?.detail || 'Failed to load Strava activities';
          errors.strava = detail;
          return [] as Activity[];
        }),
        activitiesApi.getGarminActivities(limit).catch((err: any) => {
          const detail = err?.response?.data?.detail || 'Failed to load Garmin activities';
          errors.garmin = detail;
          return [] as Activity[];
        }),
      ]);

      if (Object.keys(errors).length > 0) {
        setSourceErrors(errors);
      }

      // Combine and sort by date (most recent first)
      const combined = [...stravaActivities, ...garminActivities].sort(
        (a, b) => new Date(b.start_date).getTime() - new Date(a.start_date).getTime()
      );

      setActivities(combined);
    } catch (error: any) {
      console.error('Error loading activities:', error);
      toast.error('Failed to load activities');
    } finally {
      setLoading(false);
    }
  };

  const formatDistance = (meters?: number) => {
    if (!meters) return 'N/A';
    const km = meters / 1000;
    return `${km.toFixed(2)} km`;
  };

  const formatDuration = (seconds?: number) => {
    if (!seconds) return 'N/A';
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    if (hours > 0) {
      return `${hours}h ${minutes}m`;
    }
    return `${minutes}m`;
  };

  const handleSync = async (activity: Activity) => {
    setSyncingActivityId(activity.id);
    try {
      if (activity.source === 'strava') {
        // Sync Strava to Garmin - keep ID as string to safely handle 64-bit IDs
        const result = await syncApi.manualSync({ strava_activity_id: activity.id });
        if (result.status === 'success') {
          toast.success('Activity synced to Garmin!');
        } else {
          toast.error(result.message || 'Failed to sync activity');
        }
      } else {
        // Sync Garmin to Strava
        const result = await syncApi.manualSyncGarminToStrava({ garmin_activity_id: activity.id });
        if (result.status === 'success') {
          toast.success('Activity synced to Strava!');
        } else if (result.status === 'skipped') {
          toast.info(result.message);
        } else {
          toast.error(result.message || 'Failed to sync activity');
        }
      }
      // Reload activities to update sync status
      await loadActivities();
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Failed to sync activity');
    } finally {
      setSyncingActivityId(null);
    }
  };

  const filteredActivities = activities.filter((activity) => {
    if (activeSource === 'all') return true;
    return activity.source === activeSource;
  }).slice(0, limit);

  if (loading) {
    return (
      <div className="bg-white rounded-lg shadow">
        <div className="px-4 sm:px-6 py-4 border-b">
          <h2 className="text-lg font-semibold">Recent Activities</h2>
        </div>
        <div className="p-8 text-center text-gray-500">
          Loading activities...
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow">
      <div className="px-4 sm:px-6 py-4 border-b">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <h2 className="text-lg font-semibold">Recent Activities</h2>
          <div className="flex gap-2 overflow-x-auto pb-2 sm:pb-0">
            <button
              type="button"
              onClick={() => setActiveSource('all')}
              className={`px-3 py-1.5 text-sm font-medium rounded-md whitespace-nowrap transition-colors cursor-pointer ${
                activeSource === 'all'
                  ? 'bg-primary text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              All
            </button>
            <button
              type="button"
              onClick={() => setActiveSource('strava')}
              className={`px-3 py-1.5 text-sm font-medium rounded-md whitespace-nowrap transition-colors cursor-pointer ${
                activeSource === 'strava'
                  ? 'bg-primary text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              Strava
            </button>
            <button
              type="button"
              onClick={() => setActiveSource('garmin')}
              className={`px-3 py-1.5 text-sm font-medium rounded-md whitespace-nowrap transition-colors cursor-pointer ${
                activeSource === 'garmin'
                  ? 'bg-primary text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              Garmin
            </button>
          </div>
        </div>
      </div>

      {(sourceErrors.strava || sourceErrors.garmin) && (
        <div className="px-4 sm:px-6 py-3 bg-amber-50 border-b border-amber-100 space-y-2">
          {sourceErrors.strava && (
            <p className="text-sm text-amber-700">
              <span className="font-medium">Strava:</span> {sourceErrors.strava}
            </p>
          )}
          {sourceErrors.garmin && (
            <div className="flex flex-wrap items-center gap-3">
              <p className="text-sm text-amber-700">
                <span className="font-medium">Garmin:</span> {sourceErrors.garmin}
              </p>
              <button
                type="button"
                onClick={() => navigate('/settings')}
                className="text-xs font-medium text-white bg-amber-600 hover:bg-amber-700 px-2.5 py-1 rounded cursor-pointer whitespace-nowrap"
              >
                Re-authenticate →
              </button>
            </div>
          )}
        </div>
      )}

      {filteredActivities.length === 0 ? (
        <div className="p-8 text-center text-gray-500">
          {sourceErrors.strava && sourceErrors.garmin
            ? 'Could not load activities from either source.'
            : 'No activities found'}
        </div>
      ) : (
        <div className="divide-y">
          {filteredActivities.map((activity) => (
            <div
              key={`${activity.source}-${activity.id}`}
              className="px-4 sm:px-6 py-4 hover:bg-gray-50 transition-colors"
            >
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1 flex-wrap">
                    <h3 className="font-medium text-gray-900 truncate">{activity.name}</h3>
                    <span
                      className={`px-2 py-0.5 text-xs font-medium rounded whitespace-nowrap ${
                        activity.source === 'strava'
                          ? 'bg-orange-100 text-orange-700'
                          : 'bg-blue-100 text-blue-700'
                      }`}
                    >
                      {activity.source}
                    </span>
                  </div>
                  <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-gray-500">
                    <span className="flex items-center gap-1">
                      <span className="font-medium">{activity.type}</span>
                    </span>
                    <span className="flex items-center gap-1">
                      <svg
                        className="w-4 h-4"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"
                        />
                      </svg>
                      {formatDateOnly(activity.start_date, displayTimezone)}
                    </span>
                    <span className="flex items-center gap-1">
                      <svg
                        className="w-4 h-4"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
                        />
                      </svg>
                      {formatTime(activity.start_date, displayTimezone, hour12)}
                    </span>
                  </div>
                </div>
                <div className="flex items-center gap-4 sm:gap-6">
                  <div className="flex gap-4 sm:gap-6 text-sm">
                    <div className="text-center">
                      <div className="text-gray-500 text-xs mb-1">Distance</div>
                      <div className="font-semibold text-gray-900">{formatDistance(activity.distance)}</div>
                    </div>
                    <div className="text-center">
                      <div className="text-gray-500 text-xs mb-1">Duration</div>
                      <div className="font-semibold text-gray-900">{formatDuration(activity.moving_time)}</div>
                    </div>
                    {activity.total_elevation_gain !== null && activity.total_elevation_gain !== undefined && (
                      <div className="text-center">
                        <div className="text-gray-500 text-xs mb-1">Elevation</div>
                        <div className="font-semibold text-gray-900">{Math.round(activity.total_elevation_gain)}m</div>
                      </div>
                    )}
                  </div>
                  {!activity.synced && (activity.source === 'strava' || garminToStravaEnabled) && (
                    <button
                      onClick={() => handleSync(activity)}
                      disabled={syncingActivityId === activity.id}
                      className="px-3 py-1.5 text-sm font-medium text-white bg-primary hover:bg-primary/90 rounded-md disabled:opacity-50 whitespace-nowrap transition-colors cursor-pointer"
                      title={activity.source === 'strava' ? 'Sync to Garmin' : 'Sync to Strava'}
                    >
                      {syncingActivityId === activity.id ? (
                        <span className="flex items-center gap-1">
                          <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                          </svg>
                          <span className="hidden sm:inline">Syncing...</span>
                        </span>
                      ) : (
                        <span className="flex items-center gap-1">
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                          </svg>
                          <span className="hidden sm:inline">Sync</span>
                        </span>
                      )}
                    </button>
                  )}
                  {activity.synced && (
                    <div className="flex items-center gap-1 text-green-600 text-sm whitespace-nowrap">
                      <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                      </svg>
                      <span className="hidden sm:inline">Synced</span>
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
