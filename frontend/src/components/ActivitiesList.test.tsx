import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '../test/test-utils';
import { ActivitiesList } from './ActivitiesList';
import { activitiesApi, type Activity } from '../api/activities';
import { useAuth } from '../hooks/useAuth';

vi.mock('../api/activities', () => ({
  activitiesApi: {
    getStravaActivities: vi.fn(),
    getGarminActivities: vi.fn(),
  },
}));

vi.mock('../api/sync', () => ({
  syncApi: {
    manualSync: vi.fn(),
    manualSyncGarminToStrava: vi.fn(),
  },
}));

vi.mock('../hooks/useAuth', () => ({
  useAuth: vi.fn(),
}));

vi.mock('sonner', () => ({
  toast: {
    error: vi.fn(),
    success: vi.fn(),
    info: vi.fn(),
  },
}));

function createDeferred<T>() {
  let resolve!: (value: T | PromiseLike<T>) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });

  return { promise, resolve, reject };
}

const stravaActivity: Activity = {
  id: 'strava-1',
  name: 'Morning Run',
  type: 'Run',
  start_date: '2026-04-22T07:00:00Z',
  distance: 5000,
  moving_time: 1800,
  total_elevation_gain: 50,
  source: 'strava',
  synced: false,
};

const garminActivity: Activity = {
  id: 'garmin-1',
  name: 'Lunch Ride',
  type: 'Ride',
  start_date: '2026-04-22T12:00:00Z',
  distance: 20000,
  moving_time: 3600,
  total_elevation_gain: 150,
  source: 'garmin',
  synced: false,
};

describe('ActivitiesList', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('starts Strava and Garmin requests concurrently when Garmin is connected', async () => {
    const stravaDeferred = createDeferred<Activity[]>();

    (useAuth as any).mockReturnValue({
      authStatus: { garmin_connected: true },
    });
    (activitiesApi.getStravaActivities as any).mockReturnValue(stravaDeferred.promise);
    (activitiesApi.getGarminActivities as any).mockResolvedValue([garminActivity]);

    render(<ActivitiesList limit={5} />);

    await waitFor(() => {
      expect(activitiesApi.getStravaActivities).toHaveBeenCalledWith(5);
      expect(activitiesApi.getGarminActivities).toHaveBeenCalledWith(5);
    });

    stravaDeferred.resolve([stravaActivity]);

    await waitFor(() => {
      expect(screen.getByText('Morning Run')).toBeInTheDocument();
      expect(screen.getByText('Lunch Ride')).toBeInTheDocument();
    });
  });

  it('skips Garmin requests when Garmin is not connected', async () => {
    (useAuth as any).mockReturnValue({
      authStatus: { garmin_connected: false },
    });
    (activitiesApi.getStravaActivities as any).mockResolvedValue([stravaActivity]);

    render(<ActivitiesList limit={3} />);

    await waitFor(() => {
      expect(activitiesApi.getStravaActivities).toHaveBeenCalledWith(3);
      expect(activitiesApi.getGarminActivities).not.toHaveBeenCalled();
      expect(screen.getByText('Morning Run')).toBeInTheDocument();
    });
  });
});
