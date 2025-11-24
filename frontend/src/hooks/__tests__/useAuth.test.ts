import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { useAuth } from '../useAuth';
import { createTestQueryClient } from '../../test/test-utils';
import { QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import * as api from '../../api';

// Mock the API
vi.mock('../../api', () => ({
  getAuthStatus: vi.fn(),
  getStravaAuthUrl: vi.fn(),
  loginWithGarmin: vi.fn(),
  logout: vi.fn(),
}));

describe('useAuth', () => {
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={createTestQueryClient()}>
      {children}
    </QueryClientProvider>
  );

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should return loading state initially', () => {
    vi.mocked(api.getAuthStatus).mockResolvedValue({
      authenticated: false,
      strava_connected: false,
      garmin_connected: false,
    });

    const { result } = renderHook(() => useAuth(), { wrapper });

    expect(result.current.isLoading).toBe(true);
  });

  it('should return authenticated state when user is logged in', async () => {
    const mockAuthStatus = {
      authenticated: true,
      strava_connected: true,
      garmin_connected: true,
      user: { id: 1, email: 'test@example.com' },
    };

    vi.mocked(api.getAuthStatus).mockResolvedValue(mockAuthStatus);

    const { result } = renderHook(() => useAuth(), { wrapper });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.isAuthenticated).toBe(true);
    expect(result.current.hasStravaAuth).toBe(true);
    expect(result.current.hasGarminAuth).toBe(true);
  });

  it('should return unauthenticated state when user is not logged in', async () => {
    vi.mocked(api.getAuthStatus).mockResolvedValue({
      authenticated: false,
      strava_connected: false,
      garmin_connected: false,
    });

    const { result } = renderHook(() => useAuth(), { wrapper });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.isAuthenticated).toBe(false);
    expect(result.current.hasStravaAuth).toBe(false);
    expect(result.current.hasGarminAuth).toBe(false);
  });

  it('should handle partial authentication (Strava only)', async () => {
    vi.mocked(api.getAuthStatus).mockResolvedValue({
      authenticated: true,
      strava_connected: true,
      garmin_connected: false,
    });

    const { result } = renderHook(() => useAuth(), { wrapper });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.hasStravaAuth).toBe(true);
    expect(result.current.hasGarminAuth).toBe(false);
  });

  it('should handle API errors gracefully', async () => {
    vi.mocked(api.getAuthStatus).mockRejectedValue(new Error('Network error'));

    const { result } = renderHook(() => useAuth(), { wrapper });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.isAuthenticated).toBe(false);
  });
});
