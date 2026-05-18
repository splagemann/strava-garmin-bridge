import { vi, describe, it, expect, beforeEach } from 'vitest';
import { authApi } from './auth';
import { apiClient } from './client';

// Mock apiClient
vi.mock('./client', async () => {
  const actual = await vi.importActual('./client');
  return {
    ...actual,
    apiClient: {
      get: vi.fn(),
      post: vi.fn(),
      delete: vi.fn(),
    },
  };
});

describe('authApi', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    sessionStorage.clear();
    localStorage.clear();
  });

  describe('getStravaAuthUrl', () => {
    it('should fetch auth URL', async () => {
      const mockResponse = {
        data: {
          auth_url: 'http://test.com/auth',
          state: 'test_state',
        },
      };
      (apiClient.get as any).mockResolvedValue(mockResponse);

      const result = await authApi.getStravaAuthUrl();

      expect(apiClient.get).toHaveBeenCalledWith('/api/v1/auth/strava/auth-url');
      expect(result).toEqual(mockResponse.data);
    });
  });

  describe('exchangeStravaCode', () => {
    it('should exchange code for token', async () => {
      const mockResponse = {
        data: {
          access_token: 'test_token',
          token_type: 'bearer',
          email: 'test@example.com',
          athlete_id: '123',
        },
      };
      (apiClient.post as any).mockResolvedValue(mockResponse);

      const result = await authApi.exchangeStravaCode('code', 'state', 'signed_state');

      expect(apiClient.post).toHaveBeenCalledWith('/api/v1/auth/strava/exchange', {
        code: 'code',
        state: 'state',
        signed_state: 'signed_state',
        scope: undefined,
      });
      expect(result).toEqual(mockResponse.data);
    });
  });

  describe('connectStrava', () => {
    it('should redirect to auth URL and store state', async () => {
      const mockAuthData = {
        auth_url: 'http://test.com/auth',
        state: 'test_state',
      };
      
      // Mock getStravaAuthUrl since it calls apiClient
      vi.spyOn(authApi, 'getStravaAuthUrl').mockResolvedValue(mockAuthData);
      
      // Mock window.location
      const originalLocation = window.location;
      delete (window as any).location;
      (window as any).location = { href: '' };

      await authApi.connectStrava();

      expect(sessionStorage.getItem('oauth_signed_state')).toBe('test_state');
      expect(window.location.href).toBe('http://test.com/auth');

      // Cleanup
      (window as any).location = originalLocation;
    });
  });

  describe('handleOAuthCallback', () => {
    it('should handle successful callback', async () => {
      sessionStorage.setItem('oauth_signed_state', 'signed_state');
      
      const mockAuthResponse = {
        access_token: 'jwt_token',
        token_type: 'bearer',
        email: 'test@example.com',
        athlete_id: '123',
      };

      vi.spyOn(authApi, 'exchangeStravaCode').mockResolvedValue(mockAuthResponse);

      const result = await authApi.handleOAuthCallback('code', 'state');

      expect(authApi.exchangeStravaCode).toHaveBeenCalledWith('code', 'state', 'signed_state');
      expect(localStorage.getItem('auth_token')).toBe('jwt_token');
      expect(result).toEqual(mockAuthResponse);
    });

    it('should use state from URL as fallback if signed state missing', async () => {
        const mockAuthResponse = {
            access_token: 'jwt_token',
            token_type: 'bearer',
            email: 'test@example.com',
            athlete_id: '123',
        };
        
        vi.spyOn(authApi, 'exchangeStravaCode').mockResolvedValue(mockAuthResponse);
        
        await authApi.handleOAuthCallback('code', 'state');
        
        // Should verify that 'state' was passed as the signed_state parameter (3rd arg)
        expect(authApi.exchangeStravaCode).toHaveBeenCalledWith('code', 'state', 'state');
    });
  });

  describe('Withings Auth', () => {
    it('should get auth URL', async () => {
      const mockResponse = { data: { auth_url: 'url', state: 'state' } };
      (apiClient.get as any).mockResolvedValue(mockResponse);
      
      const result = await authApi.getWithingsAuthUrl();
      expect(result).toEqual(mockResponse.data);
    });

    it('should exchange code', async () => {
      const mockResponse = { data: { message: 'success' } };
      (apiClient.post as any).mockResolvedValue(mockResponse);
      
      const result = await authApi.exchangeWithingsCode('code', 'state', 'signed');
      expect(apiClient.post).toHaveBeenCalledWith('/api/v1/auth/withings/exchange', {
        code: 'code',
        state: 'state',
        signed_state: 'signed'
      });
      expect(result).toEqual(mockResponse.data);
    });
  });

  describe('disconnects', () => {
    it('should disconnect Garmin', async () => {
      const mockResponse = { data: { message: 'Garmin disconnected successfully' } };
      (apiClient.delete as any).mockResolvedValue(mockResponse);

      const result = await authApi.disconnectGarmin();

      expect(apiClient.delete).toHaveBeenCalledWith('/api/v1/auth/garmin');
      expect(result).toEqual(mockResponse.data);
    });

    it('should disconnect Withings', async () => {
      const mockResponse = { data: { message: 'Withings disconnected successfully' } };
      (apiClient.delete as any).mockResolvedValue(mockResponse);

      const result = await authApi.disconnectWithings();

      expect(apiClient.delete).toHaveBeenCalledWith('/api/v1/auth/withings');
      expect(result).toEqual(mockResponse.data);
    });
  });
});
