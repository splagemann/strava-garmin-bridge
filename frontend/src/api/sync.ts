import { apiClient } from './client';
import type { SyncLog, SyncStats, ManualSyncRequest, ManualSyncResponse } from '../types';

export const syncApi = {
  /**
   * Trigger manual sync for a specific activity
   */
  manualSync: async (data: ManualSyncRequest): Promise<ManualSyncResponse> => {
    const response = await apiClient.post('/api/v1/sync/manual', data);
    return response.data;
  },

  /**
   * Get sync history with pagination
   */
  getSyncHistory: async (params?: {
    limit?: number;
    offset?: number;
    status?: string;
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
};
