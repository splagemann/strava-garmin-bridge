export interface User {
  id: number;
  email: string;
  created_at: string;
}

export interface AuthStatus {
  email: string;
  strava_connected: boolean;
  garmin_connected: boolean;
  strava_athlete_id: string | null;
}

export interface StravaAuthResponse {
  access_token: string;
  token_type: string;
  email: string;
  athlete_id: string;
}

export interface StravaAuthUrlResponse {
  auth_url: string;
  state: string;  // Signed state token for CSRF protection
}

export interface GarminCredentials {
  email: string;
  password: string;
}
