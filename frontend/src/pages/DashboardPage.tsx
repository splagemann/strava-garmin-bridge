import { useState } from 'react';
import { useSync } from '../hooks/useSync';
import { toast } from 'sonner';
import { formatRelativeTime } from '../lib/utils';
import { SYNC_STATUS_COLORS, SYNC_STATUS_LABELS } from '../lib/constants';
import { syncApi } from '../api/sync';

type SyncDirection = 'strava_to_garmin' | 'garmin_to_strava';

export default function DashboardPage() {
  const { syncStats, syncHistory, manualSync, isSyncing, refetch } = useSync();
  const [activeTab, setActiveTab] = useState<SyncDirection>('strava_to_garmin');
  const [stravaActivityId, setStravaActivityId] = useState('');
  const [garminActivityId, setGarminActivityId] = useState('');
  const [isSyncingGarmin, setIsSyncingGarmin] = useState(false);

  const handleManualSync = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await manualSync({ strava_activity_id: parseInt(stravaActivityId) });
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

      {/* Stats Grid */}
      {syncStats && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="bg-white rounded-lg shadow p-6">
            <div className="text-sm font-medium text-gray-500">Total Syncs</div>
            <div className="mt-2 text-3xl font-bold">{syncStats.total}</div>
          </div>
          <div className="bg-white rounded-lg shadow p-6">
            <div className="text-sm font-medium text-gray-500">Success</div>
            <div className="mt-2 text-3xl font-bold text-green-600">{syncStats.success}</div>
          </div>
          <div className="bg-white rounded-lg shadow p-6">
            <div className="text-sm font-medium text-gray-500">Failed</div>
            <div className="mt-2 text-3xl font-bold text-red-600">{syncStats.failed}</div>
          </div>
          <div className="bg-white rounded-lg shadow p-6">
            <div className="text-sm font-medium text-gray-500">Success Rate</div>
            <div className="mt-2 text-3xl font-bold">{syncStats.success_rate.toFixed(1)}%</div>
          </div>
        </div>
      )}

      {/* Manual Sync Form with Tabs */}
      <div className="bg-white rounded-lg shadow">
        <div className="border-b">
          <div className="flex">
            <button
              onClick={() => setActiveTab('strava_to_garmin')}
              className={`flex-1 px-6 py-4 text-sm font-medium transition-colors ${
                activeTab === 'strava_to_garmin'
                  ? 'border-b-2 border-primary text-primary'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              Strava → Garmin
            </button>
            <button
              onClick={() => setActiveTab('garmin_to_strava')}
              className={`flex-1 px-6 py-4 text-sm font-medium transition-colors ${
                activeTab === 'garmin_to_strava'
                  ? 'border-b-2 border-primary text-primary'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              Garmin → Strava
            </button>
          </div>
        </div>

        <div className="p-6">
          {activeTab === 'strava_to_garmin' ? (
            <div>
              <h2 className="text-lg font-semibold mb-4">Sync from Strava to Garmin</h2>
              <form onSubmit={handleManualSync} className="flex gap-4">
                <input
                  type="number"
                  placeholder="Strava Activity ID"
                  value={stravaActivityId}
                  onChange={(e) => setStravaActivityId(e.target.value)}
                  required
                  className="flex-1 px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
                />
                <button
                  type="submit"
                  disabled={isSyncing}
                  className="bg-primary hover:bg-primary/90 text-white px-6 py-2 rounded-md font-medium disabled:opacity-50"
                >
                  {isSyncing ? 'Syncing...' : 'Sync Activity'}
                </button>
              </form>
            </div>
          ) : (
            <div>
              <h2 className="text-lg font-semibold mb-4">Sync from Garmin to Strava</h2>
              <form onSubmit={handleManualSyncGarminToStrava} className="flex gap-4">
                <input
                  type="text"
                  placeholder="Garmin Activity ID"
                  value={garminActivityId}
                  onChange={(e) => setGarminActivityId(e.target.value)}
                  required
                  className="flex-1 px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
                />
                <button
                  type="submit"
                  disabled={isSyncingGarmin}
                  className="bg-primary hover:bg-primary/90 text-white px-6 py-2 rounded-md font-medium disabled:opacity-50"
                >
                  {isSyncingGarmin ? 'Syncing...' : 'Sync Activity'}
                </button>
              </form>
            </div>
          )}
        </div>
      </div>

      {/* Recent Syncs */}
      <div className="bg-white rounded-lg shadow">
        <div className="px-6 py-4 border-b">
          <h2 className="text-lg font-semibold">Recent Syncs</h2>
        </div>
        <div className="divide-y">
          {syncHistory.slice(0, 10).map((log) => (
            <div key={log.id} className="px-6 py-4 flex items-center justify-between hover:bg-gray-50">
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <div className="font-medium">{log.activity_name || 'Unnamed Activity'}</div>
                  <span className="text-xs px-2 py-0.5 rounded bg-gray-100 text-gray-600">
                    {log.sync_direction === 'strava_to_garmin' ? 'S→G' : 'G→S'}
                  </span>
                </div>
                <div className="text-sm text-gray-500">
                  {log.activity_type} • {formatRelativeTime(log.created_at)}
                </div>
              </div>
              <span
                className={`px-3 py-1 rounded-full text-xs font-medium border ${
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
