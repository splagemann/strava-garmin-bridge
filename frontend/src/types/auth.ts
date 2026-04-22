export interface User {
  id: number;
  email: string;
  created_at: string;
}

export interface AuthStatus {
  email: string;
  strava_connected: boolean;
  garmin_connected: boolean;
  garmin_requires_mfa?: boolean;
  withings_connected?: boolean;
  strava_athlete_id: string | null;
}

export interface StravaAuthResponse {
  access_token: string;
  token_type: string;
  email: string;
  athlete_id: string;
}

export interface WithingsAuthUrlResponse {
  auth_url: string;
  state: string;
}

export interface WithingsAuthResponse {
  message: string;
}

export interface StravaAuthUrlResponse {
  auth_url: string;
  state: string;
}

export interface GarminCredentials {
  email: string;
  password: string;
}

export interface GarminConnectResponse {
  message: string;
  requires_mfa: boolean;
}

export interface GarminMfaRequest {
  code: string;
}
