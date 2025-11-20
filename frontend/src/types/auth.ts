export interface User {
  id: number;
  email: string;
  created_at: string;
}

export interface AuthStatus {
  user_id: number;
  email: string;
  strava_connected: boolean;
  garmin_connected: boolean;
  strava_athlete_id: string | null;
}

export interface GarminCredentials {
  email: string;
  password: string;
}
