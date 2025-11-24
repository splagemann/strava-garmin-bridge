import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { useSync } from '../useSync';
import { createTestQueryClient } from '../../test/test-utils';
import { QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import * as api from '../../api';

// Mock the API
vi.mock('../../api', () => ({
  syncStravaToGarmin: vi.fn(),
  syncGarminToStrava: vi.fn(),
  getSyncHistory: vi.fn(),
}));

describe('useSync', () => {
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={createTestQueryClient()}>
      {children}
    </QueryClientProvider>
  );

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should sync activity from Strava to Garmin', async () => {
    const mockResponse = {
      status: 'success',
      message: 'Activity synced successfully',
    };

    vi.mocked(api.syncStravaToGarmin).mockResolvedValue(mockResponse);

    const { result } = renderHook(() => useSync(), { wrapper });

    await act(async () => {
      await result.current.syncStravaToGarmin(1234567890);
    });

    expect(api.syncStravaToGarmin).toHaveBeenCalledWith(1234567890, false);
  });

  it('should sync activity from Garmin to Strava', async () => {
    const mockResponse = {
      status: 'success',
      message: 'Activity synced successfully',
    };

    vi.mocked(api.syncGarminToStrava).mockResolvedValue(mockResponse);

    const { result } = renderHook(() => useSync(), { wrapper });

    await act(async () => {
      await result.current.syncGarminToStrava('9876543210');
    });

    expect(api.syncGarminToStrava).toHaveBeenCalledWith('9876543210', false);
  });

  it('should support force sync parameter', async () => {
    vi.mocked(api.syncStravaToGarmin).mockResolvedValue({
      status: 'success',
      message: 'Activity synced successfully',
    });

    const { result } = renderHook(() => useSync(), { wrapper });

    await act(async () => {
      await result.current.syncStravaToGarmin(1234567890, true);
    });

    expect(api.syncStravaToGarmin).toHaveBeenCalledWith(1234567890, true);
  });

  it('should handle sync errors', async () => {
    vi.mocked(api.syncStravaToGarmin).mockRejectedValue(
      new Error('Sync failed')
    );

    const { result } = renderHook(() => useSync(), { wrapper });

    await act(async () => {
      try {
        await result.current.syncStravaToGarmin(1234567890);
      } catch (error) {
        expect(error).toBeInstanceOf(Error);
      }
    });
  });

  it('should fetch sync history', async () => {
    const mockHistory = [
      {
        id: 1,
        strava_activity_id: 1234567890,
        garmin_activity_id: 9876543210,
        sync_status: 'success',
        sync_direction: 'strava_to_garmin',
        synced_at: '2025-11-24T12:00:00Z',
      },
    ];

    vi.mocked(api.getSyncHistory).mockResolvedValue(mockHistory);

    const { result } = renderHook(() => useSync(), { wrapper });

    await waitFor(() => {
      expect(result.current.syncHistory).toBeDefined();
    });
  });
});
