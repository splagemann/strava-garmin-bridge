import { apiClient } from './client';
import type {
  AuthStatus,
  GarminConnectResponse,
  GarminCredentials,
  GarminMfaRequest,
  StravaAuthResponse,
  StravaAuthUrlResponse,
  WithingsAuthUrlResponse,
} from '../types';

export const authApi = {
  connectStrava: async () => {
    const response = await apiClient.get<StravaAuthUrlResponse>('/api/v1/auth/strava/auth-url');
    const { auth_url, state } = response.data;
    sessionStorage.setItem('oauth_signed_state', state);
    window.location.href = auth_url;
  },

  connectWithings: async () => {
    const response = await apiClient.get<WithingsAuthUrlResponse>('/api/v1/auth/withings/auth-url');
    const { auth_url, state } = response.data;
    sessionStorage.setItem('oauth_signed_state', state);
    window.location.href = auth_url;
  },

  exchangeStravaCode: async (code: string, state: string, signedState: string): Promise<StravaAuthResponse> => {
    const response = await apiClient.post<StravaAuthResponse>('/api/v1/auth/strava/exchange', {
      code,
      state,
      signed_state: signedState,
    });

    const authResponse = response.data;
    localStorage.setItem('auth_token', authResponse.access_token);
    localStorage.setItem('user_email', authResponse.email);
    localStorage.setItem('athlete_id', authResponse.athlete_id);
    return authResponse;
  },

  handleOAuthCallback: async (code: string, state: string): Promise<StravaAuthResponse> => {
    const signedState = sessionStorage.getItem('oauth_signed_state');
    if (!signedState) {
      throw new Error('Missing OAuth state. Please restart the Strava connection flow.');
    }
    return authApi.exchangeStravaCode(code, state, signedState);
  },

  handleWithingsCallback: async (code: string, state: string) => {
    const signedState = sessionStorage.getItem('oauth_signed_state');
    if (!signedState) {
      throw new Error('Missing OAuth state. Please restart the Withings connection flow.');
    }

    const response = await apiClient.post('/api/v1/auth/withings/exchange', {
      code,
      state,
      signed_state: signedState,
    });
    return response.data;
  },

  saveGarminCredentials: async (credentials: GarminCredentials): Promise<GarminConnectResponse> => {
    const response = await apiClient.post<GarminConnectResponse>('/api/v1/auth/garmin/credentials', credentials);
    return response.data;
  },

  verifyGarminMfa: async (request: GarminMfaRequest): Promise<GarminConnectResponse> => {
    const response = await apiClient.post<GarminConnectResponse>('/api/v1/auth/garmin/mfa', request);
    return response.data;
  },

  getAuthStatus: async (): Promise<AuthStatus> => {
    const response = await apiClient.get<AuthStatus>('/api/v1/auth/status');
    return response.data;
  },

  logout: () => {
    localStorage.removeItem('auth_token');
    localStorage.removeItem('user_email');
    localStorage.removeItem('athlete_id');
    sessionStorage.removeItem('oauth_signed_state');
    window.location.href = '/auth';
  },
};
