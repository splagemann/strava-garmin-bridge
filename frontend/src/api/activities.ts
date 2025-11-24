import { apiClient } from './client';

export interface Activity {
  id: string;
  name: string;
  type: string;
  start_date: string;
  distance?: number;  // in meters
  moving_time?: number;  // in seconds
  elapsed_time?: number;  // in seconds
  total_elevation_gain?: number;  // in meters
  source: 'strava' | 'garmin';
  synced: boolean;
  sync_direction?: 'strava_to_garmin' | 'garmin_to_strava';
}

export const activitiesApi = {
  /**
   * Get recent activities from Garmin Connect
   */
  getGarminActivities: async (limit: number = 10): Promise<Activity[]> => {
    const response = await apiClient.get(`/api/v1/activities/garmin?limit=${limit}`);
    return response.data;
  },

  /**
   * Get recent activities from Strava
   */
  getStravaActivities: async (limit: number = 10): Promise<Activity[]> => {
    const response = await apiClient.get(`/api/v1/activities/strava?limit=${limit}`);
    return response.data;
  },
};
