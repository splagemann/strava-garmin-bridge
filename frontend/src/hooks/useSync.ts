import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { syncApi } from '../api';
import { QUERY_KEYS } from '../lib/constants';
import type { ManualSyncRequest } from '../types';

export function useSync() {
  const queryClient = useQueryClient();

  const { data: syncHistory, isLoading: isLoadingHistory } = useQuery({
    queryKey: QUERY_KEYS.syncHistory(),
    queryFn: () => syncApi.getSyncHistory(),
    refetchInterval: 30000, // Auto-refresh every 30 seconds
  });

  const { data: syncStats, isLoading: isLoadingStats } = useQuery({
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

  return {
    syncHistory: syncHistory || [],
    syncStats,
    isLoadingHistory,
    isLoadingStats,
    manualSync: (data: ManualSyncRequest) => manualSyncMutation.mutateAsync(data),
    retrySync: (id: number) => retrySyncMutation.mutateAsync(id),
    isSyncing: manualSyncMutation.isPending,
    isRetrying: retrySyncMutation.isPending,
  };
}
