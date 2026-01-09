import { useState } from 'react';
import { useSync } from '../hooks/useSync';
import { syncApi } from '../api';
import { toast } from 'sonner';
import { formatDate } from '../lib/utils';
import { SYNC_STATUS_COLORS, SYNC_STATUS_LABELS } from '../lib/constants';

export default function SyncHistoryPage() {
  const { syncHistory, retrySync, deleteSyncLog, bulkDeleteSyncLogs, isRetrying, isDeleting } = useSync();
  const [showBulkDelete, setShowBulkDelete] = useState(false);
  const [bulkDeleteStatus, setBulkDeleteStatus] = useState<string>('');
  const [directionFilter, setDirectionFilter] = useState<string>('all');
  const [selectedLogDetails, setSelectedLogDetails] = useState<any>(null);
  const [loadingDetails, setLoadingDetails] = useState(false);

  // Filter sync history by direction
  const filteredHistory = syncHistory.filter(log => {
    if (directionFilter === 'all') return true;
    return log.sync_direction === directionFilter;
  });

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

  const handleViewDetails = async (id: number) => {
    setLoadingDetails(true);
    try {
      const details = await syncApi.getSyncLogDetails(id);
      setSelectedLogDetails(details);
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Failed to load details');
    } finally {
      setLoadingDetails(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold">Sync History</h1>
        <div className="flex gap-4 items-center">
          <div>
            <label className="text-sm font-medium text-gray-700 mr-2">Direction:</label>
            <select
              value={directionFilter}
              onChange={(e) => setDirectionFilter(e.target.value)}
              className="px-3 py-2 border border-gray-300 rounded-md text-sm"
            >
              <option value="all">All</option>
              <option value="strava_to_garmin">Strava → Garmin</option>
              <option value="garmin_to_strava">Garmin → Strava</option>
              <option value="withings_to_garmin">Withings → Garmin</option>
            </select>
          </div>
          <button
            onClick={() => setShowBulkDelete(!showBulkDelete)}
            className="bg-red-600 hover:bg-red-700 text-white px-4 py-2 rounded-md font-medium"
          >
            {showBulkDelete ? 'Cancel' : 'Bulk Delete'}
          </button>
        </div>
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
          <div className="grid grid-cols-7 gap-4 text-sm font-medium text-gray-500">
            <div className="col-span-2">Activity</div>
            <div>Direction</div>
            <div>Type</div>
            <div>Status</div>
            <div>Date</div>
            <div>Actions</div>
          </div>
        </div>
        <div className="divide-y">
          {filteredHistory.map((log) => (
            <div key={log.id} className="px-6 py-4 hover:bg-gray-50">
              <div className="grid grid-cols-7 gap-4 items-center">
                <div className="col-span-2">
                  <div className="font-medium">{log.activity_name || 'Unnamed Activity'}</div>
                  <div className="text-sm text-gray-500">
                    Source ID: {log.source_activity_id}
                    {log.target_activity_id && ` → ${log.target_activity_id}`}
                  </div>
                  {log.error_message && (
                    <div className="text-xs text-red-600 mt-1">{log.error_message}</div>
                  )}
                </div>
                <div>
                  <span className="text-xs px-2 py-1 rounded bg-gray-100 text-gray-700 font-medium">
                    {log.sync_direction === 'strava_to_garmin' 
                      ? 'S → G' 
                      : log.sync_direction === 'garmin_to_strava'
                        ? 'G → S'
                        : 'W → G'}
                  </span>
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
                <div className="flex gap-2 flex-col">
                  <button
                    onClick={() => handleViewDetails(log.id)}
                    disabled={loadingDetails}
                    className="text-sm text-blue-600 hover:text-blue-800 font-medium disabled:opacity-50"
                  >
                    Details
                  </button>
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
          {filteredHistory.length === 0 && syncHistory.length > 0 && (
            <div className="px-6 py-12 text-center text-gray-500">
              No syncs match the selected filter.
            </div>
          )}
          {syncHistory.length === 0 && (
            <div className="px-6 py-12 text-center text-gray-500">
              No sync history yet. Try syncing an activity!
            </div>
          )}
        </div>
      </div>

      {/* Details Modal */}
      {selectedLogDetails && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] overflow-hidden flex flex-col">
            <div className="px-6 py-4 border-b flex justify-between items-center">
              <h2 className="text-xl font-bold">Sync Details</h2>
              <button
                onClick={() => setSelectedLogDetails(null)}
                className="text-gray-500 hover:text-gray-700"
              >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="px-6 py-4 overflow-y-auto flex-1">
              <div className="space-y-6">
                {/* Basic Info */}
                <div>
                  <h3 className="text-lg font-semibold mb-2">Basic Information</h3>
                  <div className="bg-gray-50 p-4 rounded space-y-2">
                    <div><strong>Activity Name:</strong> {selectedLogDetails.activity_name || 'N/A'}</div>
                    <div><strong>Activity Type:</strong> {selectedLogDetails.activity_type || 'N/A'}</div>
                    <div><strong>Sync Direction:</strong> {
                      selectedLogDetails.sync_direction === 'strava_to_garmin' 
                        ? 'Strava → Garmin' 
                        : selectedLogDetails.sync_direction === 'garmin_to_strava'
                          ? 'Garmin → Strava'
                          : 'Withings → Garmin'
                    }</div>
                    <div><strong>Source Activity ID:</strong> {selectedLogDetails.source_activity_id}</div>
                    <div><strong>Target Activity ID:</strong> {selectedLogDetails.target_activity_id || 'N/A'}</div>
                    <div><strong>Status:</strong> {selectedLogDetails.status}</div>
                  </div>
                </div>

                {/* Strava Data */}
                {selectedLogDetails.strava_data && (
                  <div>
                    <h3 className="text-lg font-semibold mb-2">Strava Activity Data</h3>
                    <div className="bg-gray-50 p-4 rounded">
                      <pre className="text-xs overflow-x-auto whitespace-pre-wrap">
                        {JSON.stringify(selectedLogDetails.strava_data, null, 2)}
                      </pre>
                    </div>
                  </div>
                )}

                {/* FIT Data Summary */}
                {selectedLogDetails.gpx_data && (
                  <div>
                    <h3 className="text-lg font-semibold mb-2">FIT File Sent to Garmin</h3>
                    <div className="bg-gray-50 p-4 rounded">
                      {(() => {
                        try {
                          // Try to parse as Python dict string (e.g., "{'format': 'FIT', ...}")
                          const cleaned = selectedLogDetails.gpx_data
                            .replace(/'/g, '"')  // Replace single quotes with double quotes
                            .replace(/None/g, 'null')  // Replace None with null
                            .replace(/True/g, 'true')  // Replace True with true
                            .replace(/False/g, 'false');  // Replace False with false
                          const fitData = JSON.parse(cleaned);

                          return (
                            <div className="space-y-2">
                              <div><strong>Format:</strong> {fitData.format}</div>
                              <div><strong>File Size:</strong> {(fitData.size_bytes / 1024).toFixed(2)} KB</div>
                              <div><strong>GPS Points:</strong> {fitData.num_gps_points?.toLocaleString()}</div>
                              <div><strong>Activity Type:</strong> {fitData.activity_type}</div>
                              <div><strong>Sport:</strong> {fitData.sport}</div>
                              {fitData.duration_seconds && (
                                <div><strong>Duration:</strong> {Math.floor(fitData.duration_seconds / 60)} minutes {Math.floor(fitData.duration_seconds % 60)} seconds</div>
                              )}
                              {fitData.distance_meters && (
                                <div><strong>Distance:</strong> {(fitData.distance_meters / 1000).toFixed(2)} km</div>
                              )}
                            </div>
                          );
                        } catch (e) {
                          // If parsing fails, show as plain text (legacy data or hex)
                          const isHex = /^[0-9a-f]+$/i.test(selectedLogDetails.gpx_data);
                          if (isHex && selectedLogDetails.gpx_data.length > 1000) {
                            return (
                              <div className="text-sm text-gray-600">
                                FIT file (binary data): {(selectedLogDetails.gpx_data.length / 2 / 1024).toFixed(2)} KB
                              </div>
                            );
                          }
                          return (
                            <pre className="text-xs overflow-x-auto whitespace-pre-wrap max-h-96">
                              {selectedLogDetails.gpx_data}
                            </pre>
                          );
                        }
                      })()}
                    </div>
                  </div>
                )}

                {/* Error Message */}
                {selectedLogDetails.error_message && (
                  <div>
                    <h3 className="text-lg font-semibold mb-2 text-red-600">Error Message</h3>
                    <div className="bg-red-50 p-4 rounded text-red-800">
                      {selectedLogDetails.error_message}
                    </div>
                  </div>
                )}
              </div>
            </div>
            <div className="px-6 py-4 border-t flex justify-end">
              <button
                onClick={() => setSelectedLogDetails(null)}
                className="bg-gray-200 hover:bg-gray-300 text-gray-800 px-4 py-2 rounded-md font-medium"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
