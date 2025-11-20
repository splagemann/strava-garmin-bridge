import { apiClient } from './client';
import type { AuthStatus, GarminCredentials } from '../types';

export const authApi = {
  /**
   * Redirect to Strava OAuth login
   */
  connectStrava: () => {
    const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
    window.location.href = `${baseUrl}/api/v1/auth/strava/login`;
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
