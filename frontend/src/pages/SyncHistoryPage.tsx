import { useSync } from '../hooks/useSync';
import { toast } from 'sonner';
import { formatDate } from '../lib/utils';
import { SYNC_STATUS_COLORS, SYNC_STATUS_LABELS } from '../lib/constants';

export default function SyncHistoryPage() {
  const { syncHistory, retrySync, isRetrying } = useSync();

  const handleRetry = async (id: number) => {
    try {
      await retrySync(id);
      toast.success('Retry initiated!');
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Failed to retry sync');
    }
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Sync History</h1>

      <div className="bg-white rounded-lg shadow">
        <div className="px-6 py-4 border-b">
          <div className="grid grid-cols-6 gap-4 text-sm font-medium text-gray-500">
            <div className="col-span-2">Activity</div>
            <div>Type</div>
            <div>Status</div>
            <div>Date</div>
            <div>Actions</div>
          </div>
        </div>
        <div className="divide-y">
          {syncHistory.map((log) => (
            <div key={log.id} className="px-6 py-4 hover:bg-gray-50">
              <div className="grid grid-cols-6 gap-4 items-center">
                <div className="col-span-2">
                  <div className="font-medium">{log.activity_name || 'Unnamed Activity'}</div>
                  <div className="text-sm text-gray-500">ID: {log.strava_activity_id}</div>
                  {log.error_message && (
                    <div className="text-xs text-red-600 mt-1">{log.error_message}</div>
                  )}
                </div>
                <div className="text-sm text-gray-600">{log.activity_type || '-'}</div>
                <div>
                  <span
                    className={`px-3 py-1 rounded-full text-xs font-medium border ${
                      SYNC_STATUS_COLORS[log.status]
                    }`}
                  >
                    {SYNC_STATUS_LABELS[log.status]}
                  </span>
                </div>
                <div className="text-sm text-gray-600">{formatDate(log.created_at)}</div>
                <div>
                  {log.status === 'failed' && (
                    <button
                      onClick={() => handleRetry(log.id)}
                      disabled={isRetrying}
                      className="text-sm text-primary hover:text-primary/80 font-medium disabled:opacity-50"
                    >
                      Retry
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}
          {syncHistory.length === 0 && (
            <div className="px-6 py-12 text-center text-gray-500">
              No sync history yet. Try syncing an activity!
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
