import { apiClient } from './client';
import type { AuthStatus, GarminCredentials } from '../types';

export const authApi = {
  /**
   * Get Strava OAuth authorization URL
   */
  getStravaAuthUrl: async () => {
    console.log('Fetching Strava auth URL...');
    const response = await apiClient.get('/api/v1/auth/strava/auth-url');
    console.log('Auth URL response:', response.data);
    return response.data;
  },

  /**
   * Exchange Strava authorization code for user data
   */
  exchangeStravaCode: async (code: string, scope?: string) => {
    const response = await apiClient.post('/api/v1/auth/strava/exchange', {
      code,
      scope,
    });
    return response.data;
  },

  /**
   * Redirect to Strava OAuth login
   */
  connectStrava: async () => {
    console.log('Starting Strava connection...');
    const data = await authApi.getStravaAuthUrl();
    console.log('Received data:', data);
    console.log('Auth URL:', data.auth_url);

    if (!data.auth_url) {
      console.error('No auth_url in response:', data);
      throw new Error('No authorization URL received from server');
    }

    console.log('Redirecting to:', data.auth_url);
    window.location.href = data.auth_url;
  },

  /**
   * Save Garmin credentials
   */
  saveGarminCredentials: async (credentials: GarminCredentials) => {
    const response = await apiClient.post('/api/v1/auth/garmin/credentials', credentials);
    return response.data;
  },

  /**
   * Get auth status for current user
   */
  getAuthStatus: async (): Promise<AuthStatus> => {
    const response = await apiClient.get('/api/v1/auth/status');
    return response.data;
  },
};
