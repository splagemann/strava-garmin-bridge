import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { authApi } from '../api';
import { isAuthenticated as checkIsAuthenticated } from '../api/client';
import { QUERY_KEYS } from '../lib/constants';
import type { GarminCredentials } from '../types';

export function useAuth() {
  const queryClient = useQueryClient();
  const hasAuthToken = checkIsAuthenticated();

  const { data: authStatus, isLoading, error } = useQuery({
    queryKey: QUERY_KEYS.authStatus,
    queryFn: authApi.getAuthStatus,
    enabled: hasAuthToken,
    retry: 1,
  });

  const saveGarminMutation = useMutation({
    mutationFn: authApi.saveGarminCredentials,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.authStatus });
    },
  });

  const verifyGarminMfaMutation = useMutation({
    mutationFn: authApi.verifyGarminMfa,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.authStatus });
    },
  });

  const connectStrava = async () => {
    try {
      await authApi.connectStrava();
    } catch (error) {
      console.error('Error connecting to Strava:', error);
      throw error;
    }
  };

  const connectWithings = async () => {
    try {
      await authApi.connectWithings();
    } catch (error) {
      console.error('Error connecting to Withings:', error);
      throw error;
    }
  };

  const saveGarminCredentials = async (credentials: GarminCredentials) => {
    return saveGarminMutation.mutateAsync(credentials);
  };

  const verifyGarminMfa = async (code: string) => {
    return verifyGarminMfaMutation.mutateAsync({ code });
  };

  const logout = () => {
    authApi.logout();
  };

  return {
    authStatus,
    isLoading,
    error,
    isAuthenticated: !!authStatus?.strava_connected,
    hasAuthToken,
    connectStrava,
    connectWithings,
    saveGarminCredentials,
    verifyGarminMfa,
    logout,
    isSavingGarmin: saveGarminMutation.isPending,
    isVerifyingGarminMfa: verifyGarminMfaMutation.isPending,
    garminError: saveGarminMutation.error ?? verifyGarminMfaMutation.error,
  };
}
