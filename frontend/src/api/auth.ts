import { apiClient } from './client';
import type { AuthStatus, GarminCredentials, StravaAuthResponse, StravaAuthUrlResponse } from '../types';

export const authApi = {
  /**
   * Get Strava OAuth authorization URL with signed state token
   */
  getStravaAuthUrl: async (): Promise<StravaAuthUrlResponse> => {
    console.log('Fetching Strava auth URL...');
    const response = await apiClient.get<StravaAuthUrlResponse>('/api/v1/auth/strava/auth-url');
    console.log('Auth URL response:', response.data);
    return response.data;
  },

  /**
   * Exchange Strava authorization code for JWT token
   */
  exchangeStravaCode: async (
    code: string,
    state: string,
    signedState: string,
    scope?: string
  ): Promise<StravaAuthResponse> => {
    const response = await apiClient.post<StravaAuthResponse>('/api/v1/auth/strava/exchange', {
      code,
      state,
      signed_state: signedState,
      scope,
    });
    return response.data;
  },

  /**
   * Redirect to Strava OAuth login
   * Stores signed state for later validation
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

    // Store signed state for CSRF protection
    sessionStorage.setItem('oauth_signed_state', data.state);

    console.log('Redirecting to:', data.auth_url);
    window.location.href = data.auth_url;
  },

  /**
   * Handle OAuth callback and exchange code for JWT token
   */
  handleOAuthCallback: async (code: string, state: string): Promise<StravaAuthResponse> => {
    // Retrieve signed state from storage
    const signedState = sessionStorage.getItem('oauth_signed_state');

    if (!signedState) {
      throw new Error('No signed state found. Please restart the authentication process.');
    }

    // Clear signed state after use
    sessionStorage.removeItem('oauth_signed_state');

    // Exchange code for JWT token with CSRF protection
    const authResponse = await authApi.exchangeStravaCode(code, state, signedState);

    // Store JWT token and user info
    localStorage.setItem('auth_token', authResponse.access_token);
    localStorage.setItem('user_email', authResponse.email);
    localStorage.setItem('athlete_id', authResponse.athlete_id);

    return authResponse;
  },

  /**
   * Save Garmin credentials (requires authentication)
   */
  saveGarminCredentials: async (credentials: GarminCredentials) => {
    const response = await apiClient.post('/api/v1/auth/garmin/credentials', credentials);
    return response.data;
  },

  /**
   * Get auth status for authenticated user
   */
  getAuthStatus: async (): Promise<AuthStatus> => {
    const response = await apiClient.get<AuthStatus>('/api/v1/auth/status');
    return response.data;
  },

  /**
   * Logout user - clear tokens and redirect to auth
   */
  logout: () => {
    localStorage.removeItem('auth_token');
    localStorage.removeItem('user_email');
    localStorage.removeItem('athlete_id');
    sessionStorage.removeItem('oauth_signed_state');
    window.location.href = '/auth';
  },
};
