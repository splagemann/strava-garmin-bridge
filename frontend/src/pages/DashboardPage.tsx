import { useState } from 'react';
import { useSync } from '../hooks/useSync';
import { toast } from 'sonner';
import { formatRelativeTime } from '../lib/utils';
import { SYNC_STATUS_COLORS, SYNC_STATUS_LABELS } from '../lib/constants';

export default function DashboardPage() {
  const { syncStats, syncHistory, manualSync, isSyncing } = useSync();
  const [activityId, setActivityId] = useState('');

  const handleManualSync = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await manualSync({ strava_activity_id: parseInt(activityId) });
      toast.success('Activity synced successfully!');
      setActivityId('');
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Failed to sync activity');
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

      {/* Manual Sync Form */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-semibold mb-4">Manual Sync</h2>
        <form onSubmit={handleManualSync} className="flex gap-4">
          <input
            type="number"
            placeholder="Strava Activity ID"
            value={activityId}
            onChange={(e) => setActivityId(e.target.value)}
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

      {/* Recent Syncs */}
      <div className="bg-white rounded-lg shadow">
        <div className="px-6 py-4 border-b">
          <h2 className="text-lg font-semibold">Recent Syncs</h2>
        </div>
        <div className="divide-y">
          {syncHistory.slice(0, 10).map((log) => (
            <div key={log.id} className="px-6 py-4 flex items-center justify-between hover:bg-gray-50">
              <div className="flex-1">
                <div className="font-medium">{log.activity_name || 'Unnamed Activity'}</div>
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
