import { useState } from 'react';
import { useSync } from '../hooks/useSync';
import { toast } from 'sonner';
import { formatDate } from '../lib/utils';
import { SYNC_STATUS_COLORS, SYNC_STATUS_LABELS } from '../lib/constants';

export default function SyncHistoryPage() {
  const { syncHistory, retrySync, deleteSyncLog, bulkDeleteSyncLogs, isRetrying, isDeleting } = useSync();
  const [showBulkDelete, setShowBulkDelete] = useState(false);
  const [bulkDeleteStatus, setBulkDeleteStatus] = useState<string>('');

  const handleRetry = async (id: number) => {
    try {
      await retrySync(id);
      toast.success('Retry initiated!');
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Failed to retry sync');
    }
  };

  const handleDelete = async (id: number) => {
    if (confirm('Are you sure you want to delete this sync log?')) {
      try {
        await deleteSyncLog(id);
        toast.success('Sync log deleted');
      } catch (error: any) {
        toast.error(error.response?.data?.detail || 'Failed to delete sync log');
      }
    }
  };

  const handleBulkDelete = async () => {
    const filters: any = {};
    if (bulkDeleteStatus) {
      filters.status = bulkDeleteStatus;
    }

    const message = bulkDeleteStatus
      ? `Delete all ${bulkDeleteStatus} sync logs?`
      : 'Delete ALL sync logs? This cannot be undone!';

    if (confirm(message)) {
      try {
        const result = await bulkDeleteSyncLogs(filters);
        toast.success(result.message);
        setShowBulkDelete(false);
        setBulkDeleteStatus('');
      } catch (error: any) {
        toast.error(error.response?.data?.detail || 'Failed to delete sync logs');
      }
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold">Sync History</h1>
        <button
          onClick={() => setShowBulkDelete(!showBulkDelete)}
          className="bg-red-600 hover:bg-red-700 text-white px-4 py-2 rounded-md font-medium"
        >
          {showBulkDelete ? 'Cancel' : 'Bulk Delete'}
        </button>
      </div>

      {showBulkDelete && (
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold mb-4">Bulk Delete Sync Logs</h2>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Filter by Status (optional)
              </label>
              <select
                value={bulkDeleteStatus}
                onChange={(e) => setBulkDeleteStatus(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md"
              >
                <option value="">All Logs</option>
                <option value="success">Success</option>
                <option value="failed">Failed</option>
                <option value="skipped">Skipped</option>
                <option value="pending">Pending</option>
              </select>
            </div>
            <button
              onClick={handleBulkDelete}
              disabled={isDeleting}
              className="w-full bg-red-600 hover:bg-red-700 text-white py-2 rounded-md font-medium disabled:opacity-50"
            >
              Delete Logs
            </button>
          </div>
        </div>
      )}

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
                <div className="flex gap-2">
                  {log.status === 'failed' && (
                    <button
                      onClick={() => handleRetry(log.id)}
                      disabled={isRetrying}
                      className="text-sm text-primary hover:text-primary/80 font-medium disabled:opacity-50"
                    >
                      Retry
                    </button>
                  )}
                  <button
                    onClick={() => handleDelete(log.id)}
                    disabled={isDeleting}
                    className="text-sm text-red-600 hover:text-red-800 font-medium disabled:opacity-50"
                  >
                    Delete
                  </button>
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
