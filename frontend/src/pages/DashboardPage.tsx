import { useState } from 'react';
import { useAuth } from '../hooks/useAuth';
import { useSync } from '../hooks/useSync';
import { toast } from 'sonner';
import { formatRelativeTime } from '../lib/utils';
import { SYNC_STATUS_COLORS, SYNC_STATUS_LABELS } from '../lib/constants';
import { syncApi } from '../api/sync';
import { ActivitiesList } from '../components/ActivitiesList';

type SyncDirection = 'strava_to_garmin' | 'garmin_to_strava';

export default function DashboardPage() {
  const { authStatus, connectWithings } = useAuth();
  const { syncStats, syncHistory, manualSync, isSyncing, refetch } = useSync();
  const [activeTab, setActiveTab] = useState<SyncDirection>('strava_to_garmin');
  const [stravaActivityId, setStravaActivityId] = useState('');
  const [garminActivityId, setGarminActivityId] = useState('');
  const [isSyncingGarmin, setIsSyncingGarmin] = useState(false);

  const handleWithingsConnect = async () => {
    try {
      await connectWithings();
    } catch (error: any) {
      toast.error('Failed to initiate Withings connection');
    }
  };

  const handleManualSync = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      // Keep ID as string to safely handle 64-bit Strava IDs
      await manualSync({ strava_activity_id: stravaActivityId });
      toast.success('Activity synced successfully!');
      setStravaActivityId('');
      refetch();
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Failed to sync activity');
    }
  };

  const handleManualSyncGarminToStrava = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSyncingGarmin(true);
    try {
      const result = await syncApi.manualSyncGarminToStrava({ garmin_activity_id: garminActivityId });
      if (result.status === 'success') {
        toast.success('Activity synced successfully from Garmin to Strava!');
      } else if (result.status === 'skipped') {
        toast.info(result.message);
      } else {
        toast.error(result.message || 'Failed to sync activity');
      }
      setGarminActivityId('');
      refetch();
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Failed to sync activity');
    } finally {
      setIsSyncingGarmin(false);
    }
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Dashboard</h1>

      {/* Connections Status */}
      <div className="bg-white rounded-lg shadow p-4 sm:p-6">
        <h2 className="text-lg font-semibold mb-4">Connections</h2>
        <div className="flex flex-wrap gap-4">
          <div className="flex items-center gap-2 px-3 py-2 bg-green-50 text-green-700 rounded-md border border-green-200">
            <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
              <path
                fillRule="evenodd"
                d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                clipRule="evenodd"
              />
            </svg>
            <span className="font-medium">Strava</span>
          </div>
          <div className="flex items-center gap-2 px-3 py-2 bg-green-50 text-green-700 rounded-md border border-green-200">
            <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
              <path
                fillRule="evenodd"
                d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                clipRule="evenodd"
              />
            </svg>
            <span className="font-medium">Garmin</span>
          </div>

          {authStatus?.withings_connected ? (
            <div className="flex items-center gap-2 px-3 py-2 bg-green-50 text-green-700 rounded-md border border-green-200">
              <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                <path
                  fillRule="evenodd"
                  d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                  clipRule="evenodd"
                />
              </svg>
              <span className="font-medium">Withings</span>
            </div>
          ) : (
            <button
              type="button"
              onClick={handleWithingsConnect}
              className="flex items-center gap-2 px-3 py-2 bg-blue-50 text-blue-700 hover:bg-blue-100 rounded-md border border-blue-200 transition-colors cursor-pointer"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4" />
              </svg>
              <span className="font-medium">Connect Withings</span>
            </button>
          )}
        </div>
      </div>

      {/* Stats Grid */}
      {syncStats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 sm:gap-4">
          <div className="bg-white rounded-lg shadow p-4 sm:p-6">
            <div className="text-xs sm:text-sm font-medium text-gray-500">Total Syncs</div>
            <div className="mt-1 sm:mt-2 text-2xl sm:text-3xl font-bold">{syncStats.total}</div>
          </div>
          <div className="bg-white rounded-lg shadow p-4 sm:p-6">
            <div className="text-xs sm:text-sm font-medium text-gray-500">Success</div>
            <div className="mt-1 sm:mt-2 text-2xl sm:text-3xl font-bold text-green-600">{syncStats.success}</div>
          </div>
          <div className="bg-white rounded-lg shadow p-4 sm:p-6">
            <div className="text-xs sm:text-sm font-medium text-gray-500">Failed</div>
            <div className="mt-1 sm:mt-2 text-2xl sm:text-3xl font-bold text-red-600">{syncStats.failed}</div>
          </div>
          <div className="bg-white rounded-lg shadow p-4 sm:p-6">
            <div className="text-xs sm:text-sm font-medium text-gray-500">Success Rate</div>
            <div className="mt-1 sm:mt-2 text-2xl sm:text-3xl font-bold">{syncStats.success_rate.toFixed(1)}%</div>
          </div>
        </div>
      )}

      {/* Manual Sync Form with Tabs (Garmin→Strava tab only when enabled) */}
      <div className="bg-white rounded-lg shadow">
        {authStatus?.garmin_to_strava_sync_disabled !== true ? (
          <div className="border-b">
            <div className="flex">
              <button
                onClick={() => setActiveTab('strava_to_garmin')}
                className={`flex-1 px-4 sm:px-6 py-3 sm:py-4 text-xs sm:text-sm font-medium transition-colors ${
                  activeTab === 'strava_to_garmin'
                    ? 'border-b-2 border-primary text-primary'
                    : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                <span className="hidden sm:inline">Strava → Garmin</span>
                <span className="sm:hidden">S → G</span>
              </button>
              <button
                onClick={() => setActiveTab('garmin_to_strava')}
                className={`flex-1 px-4 sm:px-6 py-3 sm:py-4 text-xs sm:text-sm font-medium transition-colors ${
                  activeTab === 'garmin_to_strava'
                    ? 'border-b-2 border-primary text-primary'
                    : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                <span className="hidden sm:inline">Garmin → Strava</span>
                <span className="sm:hidden">G → S</span>
              </button>
            </div>
          </div>
        ) : null}

        <div className="p-4 sm:p-6">
          {activeTab === 'strava_to_garmin' || authStatus?.garmin_to_strava_sync_disabled === true ? (
            <div>
              <h2 className="text-base sm:text-lg font-semibold mb-3 sm:mb-4">Sync from Strava to Garmin</h2>
              <form onSubmit={handleManualSync} className="flex flex-col sm:flex-row gap-3 sm:gap-4">
                <input
                  type="text"
                  placeholder="Strava Activity ID"
                  value={stravaActivityId}
                  onChange={(e) => setStravaActivityId(e.target.value)}
                  required
                  pattern="[0-9]+"
                  title="Please enter a valid numeric activity ID"
                  className="flex-1 px-3 sm:px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary text-sm sm:text-base"
                />
                <button
                  type="submit"
                  disabled={isSyncing}
                  className="bg-primary hover:bg-primary/90 text-white px-4 sm:px-6 py-2 rounded-md font-medium disabled:opacity-50 text-sm sm:text-base whitespace-nowrap cursor-pointer"
                >
                  {isSyncing ? 'Syncing...' : 'Sync Activity'}
                </button>
              </form>
            </div>
          ) : (
            <div>
              <h2 className="text-base sm:text-lg font-semibold mb-3 sm:mb-4">Sync from Garmin to Strava</h2>
              <form onSubmit={handleManualSyncGarminToStrava} className="flex flex-col sm:flex-row gap-3 sm:gap-4">
                <input
                  type="text"
                  placeholder="Garmin Activity ID"
                  value={garminActivityId}
                  onChange={(e) => setGarminActivityId(e.target.value)}
                  required
                  className="flex-1 px-3 sm:px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary text-sm sm:text-base"
                />
                <button
                  type="submit"
                  disabled={isSyncingGarmin}
                  className="bg-primary hover:bg-primary/90 text-white px-4 sm:px-6 py-2 rounded-md font-medium disabled:opacity-50 text-sm sm:text-base whitespace-nowrap cursor-pointer"
                >
                  {isSyncingGarmin ? 'Syncing...' : 'Sync Activity'}
                </button>
              </form>
            </div>
          )}
        </div>
      </div>

      {/* Recent Activities */}
      <ActivitiesList limit={10} />

      {/* Recent Syncs */}
      <div className="bg-white rounded-lg shadow">
        <div className="px-4 sm:px-6 py-4 border-b">
          <h2 className="text-lg font-semibold">Recent Syncs</h2>
        </div>
        <div className="divide-y">
          {syncHistory.slice(0, 10).map((log) => (
            <div key={log.id} className="px-4 sm:px-6 py-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 hover:bg-gray-50">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <div className="font-medium truncate">{log.activity_name || 'Unnamed Activity'}</div>
                  <span className="text-xs px-2 py-0.5 rounded bg-gray-100 text-gray-600 whitespace-nowrap">
                    {log.sync_direction === 'strava_to_garmin' ? 'S→G' : 'G→S'}
                  </span>
                </div>
                <div className="text-sm text-gray-500">
                  {log.activity_type} • {formatRelativeTime(log.created_at)}
                </div>
              </div>
              <span
                className={`px-3 py-1 rounded-full text-xs font-medium border self-start sm:self-auto whitespace-nowrap ${
                  SYNC_STATUS_COLORS[log.status]
                }`}
              >
                {SYNC_STATUS_LABELS[log.status]}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
