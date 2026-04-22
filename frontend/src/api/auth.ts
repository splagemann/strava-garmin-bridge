import { apiClient } from './client';
import type {
  AuthStatus,
  GarminConnectResponse,
  GarminCredentials,
  GarminMfaRequest,
  StravaAuthResponse,
  StravaAuthUrlResponse,
  WithingsAuthResponse,
  WithingsAuthUrlResponse,
} from '../types';

const storeAuthResponse = (authResponse: StravaAuthResponse) => {
  localStorage.setItem('auth_token', authResponse.access_token);
  localStorage.setItem('user_email', authResponse.email);
  localStorage.setItem('athlete_id', authResponse.athlete_id);
};

export const authApi = {
  getStravaAuthUrl: async (): Promise<StravaAuthUrlResponse> => {
    const response = await apiClient.get<StravaAuthUrlResponse>('/api/v1/auth/strava/auth-url');
    return response.data;
  },

  connectStrava: async () => {
    const response = await authApi.getStravaAuthUrl();
    const { auth_url, state } = response;
    sessionStorage.setItem('oauth_signed_state', state);
    window.location.href = auth_url;
  },

  getWithingsAuthUrl: async (): Promise<WithingsAuthUrlResponse> => {
    const response = await apiClient.get<WithingsAuthUrlResponse>('/api/v1/auth/withings/auth-url');
    return response.data;
  },

  connectWithings: async () => {
    const response = await authApi.getWithingsAuthUrl();
    const { auth_url, state } = response;
    sessionStorage.setItem('oauth_signed_state', state);
    window.location.href = auth_url;
  },

  exchangeStravaCode: async (code: string, state: string, signedState: string): Promise<StravaAuthResponse> => {
    const response = await apiClient.post<StravaAuthResponse>('/api/v1/auth/strava/exchange', {
      code,
      state,
      signed_state: signedState,
      scope: undefined,
    });

    const authResponse = response.data;
    storeAuthResponse(authResponse);
    return authResponse;
  },

  handleOAuthCallback: async (code: string, state: string): Promise<StravaAuthResponse> => {
    const signedState = sessionStorage.getItem('oauth_signed_state') || state;
    const authResponse = await authApi.exchangeStravaCode(code, state, signedState);
    storeAuthResponse(authResponse);
    return authResponse;
  },

  exchangeWithingsCode: async (code: string, state: string, signedState: string): Promise<WithingsAuthResponse> => {
    const response = await apiClient.post<WithingsAuthResponse>('/api/v1/auth/withings/exchange', {
      code,
      state,
      signed_state: signedState,
    });
    return response.data;
  },

  handleWithingsCallback: async (code: string, state: string): Promise<WithingsAuthResponse> => {
    const signedState = sessionStorage.getItem('oauth_signed_state') || state;
    return authApi.exchangeWithingsCode(code, state, signedState);
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
