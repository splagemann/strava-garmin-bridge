/**
 * Mock authentication data for testing
 */

export const mockUser = {
  id: 1,
  email: 'test@example.com',
  created_at: '2025-11-01T00:00:00Z',
};

export const mockStravaAuth = {
  user_id: 1,
  access_token: 'mock_strava_access_token',
  refresh_token: 'mock_strava_refresh_token',
  expires_at: Math.floor(Date.now() / 1000) + 21600, // 6 hours from now
  athlete_id: 123456,
};

export const mockGarminAuth = {
  user_id: 1,
  email: 'encrypted_email',
  password: 'encrypted_password',
};

export const mockAuthStatus = {
  authenticated: true,
  strava_connected: true,
  garmin_connected: true,
  user: mockUser,
};

export const mockStravaAuthUrl = {
  auth_url: 'https://www.strava.com/oauth/authorize?client_id=test&redirect_uri=http://localhost&response_type=code&scope=activity:read_all&state=test_state',
  state: 'test_state_token',
};

export const mockStravaTokenResponse = {
  access_token: 'new_access_token',
  refresh_token: 'new_refresh_token',
  expires_at: Math.floor(Date.now() / 1000) + 21600,
  athlete: {
    id: 123456,
    firstname: 'Test',
    lastname: 'User',
  },
};
