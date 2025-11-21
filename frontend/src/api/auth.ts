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
    console.log('Signed state token:', data.state);

    if (!data.auth_url) {
      console.error('No auth_url in response:', data);
      throw new Error('No authorization URL received from server');
    }

    // Store signed state for CSRF protection in both storages
    // sessionStorage for security, localStorage as fallback
    sessionStorage.setItem('oauth_signed_state', data.state);
    localStorage.setItem('oauth_signed_state', data.state);
    console.log('Stored signed state in both sessionStorage and localStorage');

    console.log('Redirecting to:', data.auth_url);
    window.location.href = data.auth_url;
  },

  /**
   * Handle OAuth callback and exchange code for JWT token
   */
  handleOAuthCallback: async (code: string, state: string): Promise<StravaAuthResponse> => {
    // Retrieve signed state from storage
    let signedState = sessionStorage.getItem('oauth_signed_state');

    console.log('OAuth callback - signed state from sessionStorage:', signedState);
    console.log('OAuth callback - state from URL:', state);

    // Fallback: Try localStorage as well (in case sessionStorage was cleared)
    if (!signedState) {
      signedState = localStorage.getItem('oauth_signed_state');
      console.log('Trying localStorage for signed state:', signedState);
    }

    // If no signed state found, use the state from URL as fallback
    // This happens when storage is cleared or blocked by browser
    if (!signedState) {
      console.warn('No signed state found in storage, using state from URL as fallback');
      signedState = state;
    }

    // Clear signed state after use
    sessionStorage.removeItem('oauth_signed_state');
    localStorage.removeItem('oauth_signed_state');

    try {
      // Exchange code for JWT token with CSRF protection
      const authResponse = await authApi.exchangeStravaCode(code, state, signedState);

      // Store JWT token and user info
      localStorage.setItem('auth_token', authResponse.access_token);
      localStorage.setItem('user_email', authResponse.email);
      localStorage.setItem('athlete_id', authResponse.athlete_id);

      return authResponse;
    } catch (error: any) {
      console.error('Error in exchangeStravaCode:', error);
      console.error('Request details - code:', code, 'state:', state, 'signedState:', signedState);
      throw error;
    }
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
