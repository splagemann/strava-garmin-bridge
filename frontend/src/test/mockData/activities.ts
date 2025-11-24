/**
 * Mock activity data for testing
 */

export const mockStravaActivity = {
  id: 1234567890,
  name: 'Morning Run',
  type: 'Run',
  start_date: '2025-11-24T06:00:00Z',
  distance: 5000,
  moving_time: 1800,
  elapsed_time: 1900,
  total_elevation_gain: 50,
  average_speed: 2.78,
  max_speed: 3.5,
  average_heartrate: 145,
  max_heartrate: 165,
};

export const mockGarminActivity = {
  activityId: 9876543210,
  activityName: 'Evening Ride',
  activityType: { typeKey: 'cycling', typeId: 1 },
  startTimeGMT: '2025-11-24T18:00:00Z',
  distance: 20000,
  duration: 3600,
  elevationGain: 150,
  averageSpeed: 5.56,
  maxSpeed: 8.33,
  averageHR: 135,
  maxHR: 160,
};

export const mockActivitiesList = [
  mockStravaActivity,
  {
    ...mockStravaActivity,
    id: 1234567891,
    name: 'Evening Run',
    start_date: '2025-11-24T18:00:00Z',
  },
  {
    ...mockStravaActivity,
    id: 1234567892,
    name: 'Morning Ride',
    type: 'Ride',
    start_date: '2025-11-23T06:00:00Z',
  },
];

export const mockSyncLog = {
  id: 1,
  user_id: 1,
  strava_activity_id: 1234567890,
  garmin_activity_id: 9876543210,
  sync_status: 'success',
  sync_direction: 'strava_to_garmin',
  synced_at: '2025-11-24T12:00:00Z',
  error_message: null,
};

export const mockSyncLogs = [
  mockSyncLog,
  {
    ...mockSyncLog,
    id: 2,
    strava_activity_id: 1234567891,
    garmin_activity_id: 9876543211,
    synced_at: '2025-11-24T13:00:00Z',
  },
  {
    ...mockSyncLog,
    id: 3,
    strava_activity_id: 1234567892,
    sync_status: 'failed',
    error_message: 'Network timeout',
    synced_at: '2025-11-24T14:00:00Z',
  },
];

export const mockActivityFilter = {
  id: 1,
  user_id: 1,
  filter_type: 'include',
  filter_field: 'name',
  pattern: 'Morning',
  is_regex: false,
  active: true,
};

export const mockActivityFilters = [
  mockActivityFilter,
  {
    ...mockActivityFilter,
    id: 2,
    filter_type: 'exclude',
    filter_field: 'type',
    pattern: 'Virtual.*',
    is_regex: true,
  },
];
