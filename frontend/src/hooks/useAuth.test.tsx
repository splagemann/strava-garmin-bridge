import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { useAuth } from './useAuth';
import { authApi } from '../api';
import * as clientApi from '../api/client';
import { createTestQueryClient } from '../test/test-utils';
import { QueryClientProvider } from '@tanstack/react-query';

// Mock authApi
vi.mock('../api', () => ({
  authApi: {
    getAuthStatus: vi.fn(),
    saveGarminCredentials: vi.fn(),
    connectStrava: vi.fn(),
    connectWithings: vi.fn(),
    logout: vi.fn(),
  },
}));

// Mock clientApi
vi.mock('../api/client', async () => {
  const actual = await vi.importActual('../api/client');
  return {
    ...actual,
    isAuthenticated: vi.fn(),
  };
});

describe('useAuth', () => {
  const testQueryClient = createTestQueryClient();
  const wrapper = ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={testQueryClient}>{children}</QueryClientProvider>
  );

  beforeEach(() => {
    vi.clearAllMocks();
    testQueryClient.clear();
  });

  it('fetches auth status when authenticated', async () => {
    (clientApi.isAuthenticated as any).mockReturnValue(true);
    const mockStatus = {
      email: 'test@example.com',
      strava_connected: true,
      garmin_connected: true,
    };
    (authApi.getAuthStatus as any).mockResolvedValue(mockStatus);

    const { result } = renderHook(() => useAuth(), { wrapper });

    await waitFor(() => {
      expect(result.current.authStatus).toEqual(mockStatus);
    });
    
    expect(result.current.isAuthenticated).toBe(true);
  });

  it('does not fetch auth status when not authenticated', () => {
    (clientApi.isAuthenticated as any).mockReturnValue(false);

    renderHook(() => useAuth(), { wrapper });

    expect(authApi.getAuthStatus).not.toHaveBeenCalled();
  });

  it('connectStrava calls API', async () => {
    (clientApi.isAuthenticated as any).mockReturnValue(true);
    const { result } = renderHook(() => useAuth(), { wrapper });

    await result.current.connectStrava();
    expect(authApi.connectStrava).toHaveBeenCalled();
  });

  it('connectWithings calls API', async () => {
    (clientApi.isAuthenticated as any).mockReturnValue(true);
    const { result } = renderHook(() => useAuth(), { wrapper });

    await result.current.connectWithings();
    expect(authApi.connectWithings).toHaveBeenCalled();
  });

  it('logout calls API', () => {
    (clientApi.isAuthenticated as any).mockReturnValue(true);
    const { result } = renderHook(() => useAuth(), { wrapper });

    result.current.logout();
    expect(authApi.logout).toHaveBeenCalled();
  });

  it('saveGarminCredentials calls mutation', async () => {
    (clientApi.isAuthenticated as any).mockReturnValue(true);
    const { result } = renderHook(() => useAuth(), { wrapper });
    
    const creds = { email: 'e', password: 'p' };
    await result.current.saveGarminCredentials(creds);
    
    // React Query v5 might pass extra context to mutationFn, so we check the first argument
    expect(authApi.saveGarminCredentials).toHaveBeenCalled();
    expect((authApi.saveGarminCredentials as any).mock.calls[0][0]).toEqual(creds);
  });
});
