import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { filtersApi } from '../api';
import { QUERY_KEYS } from '../lib/constants';
import type { FilterCreate, FilterUpdate } from '../types';

export function useFilters() {
  const queryClient = useQueryClient();

  const { data: filters, isLoading, error } = useQuery({
    queryKey: QUERY_KEYS.filters,
    queryFn: filtersApi.getFilters,
  });

  const createMutation = useMutation({
    mutationFn: filtersApi.createFilter,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.filters });
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: FilterUpdate }) =>
      filtersApi.updateFilter(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.filters });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: filtersApi.deleteFilter,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.filters });
    },
  });

  return {
    filters: filters || [],
    isLoading,
    error,
    createFilter: (data: FilterCreate) => createMutation.mutateAsync(data),
    updateFilter: (id: number, data: FilterUpdate) => updateMutation.mutateAsync({ id, data }),
    deleteFilter: (id: number) => deleteMutation.mutateAsync(id),
    isCreating: createMutation.isPending,
    isUpdating: updateMutation.isPending,
    isDeleting: deleteMutation.isPending,
  };
}
