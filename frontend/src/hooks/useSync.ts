import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { syncApi } from '../api';
import { QUERY_KEYS } from '../lib/constants';
import type { ManualSyncRequest } from '../types';

export function useSync() {
  const queryClient = useQueryClient();

  const { data: syncHistory, isLoading: isLoadingHistory, refetch: refetchHistory } = useQuery({
    queryKey: QUERY_KEYS.syncHistory(),
    queryFn: () => syncApi.getSyncHistory(),
    refetchInterval: 30000, // Auto-refresh every 30 seconds
  });

  const { data: syncStats, isLoading: isLoadingStats, refetch: refetchStats } = useQuery({
    queryKey: QUERY_KEYS.syncStats,
    queryFn: syncApi.getSyncStats,
    refetchInterval: 30000,
  });

  const manualSyncMutation = useMutation({
    mutationFn: syncApi.manualSync,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.syncHistory() });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.syncStats });
    },
  });

  const retrySyncMutation = useMutation({
    mutationFn: syncApi.retrySync,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.syncHistory() });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.syncStats });
    },
  });

  const deleteSyncMutation = useMutation({
    mutationFn: syncApi.deleteSyncLog,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.syncHistory() });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.syncStats });
    },
  });

  const bulkDeleteSyncMutation = useMutation({
    mutationFn: syncApi.bulkDeleteSyncLogs,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.syncHistory() });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.syncStats });
    },
  });

  const refetch = async () => {
    await Promise.all([refetchHistory(), refetchStats()]);
  };

  return {
    syncHistory: syncHistory || [],
    syncStats,
    isLoadingHistory,
    isLoadingStats,
    manualSync: (data: ManualSyncRequest) => manualSyncMutation.mutateAsync(data),
    retrySync: (id: number) => retrySyncMutation.mutateAsync(id),
    deleteSyncLog: (id: number) => deleteSyncMutation.mutateAsync(id),
    bulkDeleteSyncLogs: (params?: Parameters<typeof syncApi.bulkDeleteSyncLogs>[0]) =>
      bulkDeleteSyncMutation.mutateAsync(params),
    isSyncing: manualSyncMutation.isPending,
    isRetrying: retrySyncMutation.isPending,
    isDeleting: deleteSyncMutation.isPending,
    isBulkDeleting: bulkDeleteSyncMutation.isPending,
    refetch,
  };
}
