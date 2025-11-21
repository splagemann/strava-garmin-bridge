import { apiClient } from './client';
import type { SyncLog, SyncStats, ManualSyncRequest, ManualSyncResponse } from '../types';

export const syncApi = {
  /**
   * Trigger manual sync for a specific activity (Strava → Garmin)
   */
  manualSync: async (data: ManualSyncRequest): Promise<ManualSyncResponse> => {
    const response = await apiClient.post('/api/v1/sync/manual', data);
    return response.data;
  },

  /**
   * Trigger manual sync for a specific Garmin activity (Garmin → Strava)
   */
  manualSyncGarminToStrava: async (data: { garmin_activity_id: string }): Promise<ManualSyncResponse> => {
    const response = await apiClient.post('/api/v1/sync/manual/garmin-to-strava', data);
    return response.data;
  },

  /**
   * Get sync history with pagination
   */
  getSyncHistory: async (params?: {
    limit?: number;
    offset?: number;
    status?: string;
    direction?: 'strava_to_garmin' | 'garmin_to_strava';
  }): Promise<SyncLog[]> => {
    const response = await apiClient.get('/api/v1/sync/history', { params });
    return response.data;
  },

  /**
   * Get specific sync log details
   */
  getSyncLog: async (syncLogId: number): Promise<SyncLog> => {
    const response = await apiClient.get(`/api/v1/sync/history/${syncLogId}`);
    return response.data;
  },

  /**
   * Retry a failed sync
   */
  retrySync: async (syncLogId: number): Promise<ManualSyncResponse> => {
    const response = await apiClient.post(`/api/v1/sync/history/${syncLogId}/retry`);
    return response.data;
  },

  /**
   * Get sync statistics
   */
  getSyncStats: async (): Promise<SyncStats> => {
    const response = await apiClient.get('/api/v1/sync/stats');
    return response.data;
  },

  /**
   * Delete a specific sync log
   */
  deleteSyncLog: async (syncLogId: number): Promise<{ message: string; deleted_id: number }> => {
    const response = await apiClient.delete(`/api/v1/sync/history/${syncLogId}`);
    return response.data;
  },

  /**
   * Bulk delete sync logs with optional filters
   */
  bulkDeleteSyncLogs: async (params?: {
    status?: 'success' | 'failed' | 'skipped' | 'pending';
    before_date?: string;
    strava_activity_id?: string;
  }): Promise<{ message: string; deleted_count: number }> => {
    const response = await apiClient.delete('/api/v1/sync/history', { params });
    return response.data;
  },

  /**
   * Get sync log details including debug data
   */
  getSyncLogDetails: async (syncLogId: number): Promise<{
    id: number;
    sync_direction: string;
    source_activity_id: string;
    target_activity_id: string | null;
    strava_activity_id: string;  // Legacy field
    garmin_activity_id: string | null;  // Legacy field
    status: string;
    error_message: string | null;
    activity_name: string | null;
    activity_type: string | null;
    strava_data: any | null;
    gpx_data: string | null;
    created_at: string;
    completed_at: string | null;
  }> => {
    const response = await apiClient.get(`/api/v1/sync/history/${syncLogId}/details`);
    return response.data;
  },
};
