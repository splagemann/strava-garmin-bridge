export interface User {
  id: number;
  email: string;
  created_at: string;
}

export interface AuthStatus {
  email: string;
  username: string | null;
  first_name: string | null;
  last_name: string | null;
  strava_connected: boolean;
  garmin_connected: boolean;
  withings_connected?: boolean;
  strava_athlete_id: string | null;
  /** When true, Garmin → Strava sync is off (only Strava → Garmin runs). */
  garmin_to_strava_sync_disabled?: boolean;
}

/** Update profile (PATCH /auth/profile) */
export interface ProfileUpdate {
  email?: string | null;
  username?: string | null;
  first_name?: string | null;
  last_name?: string | null;
}

/** User settings (GET /auth/settings) */
export interface UserSettings {
  garmin_to_strava_sync_disabled: boolean;
  garmin_to_strava_sync_disabled_override: boolean | null;
  allow_export_without_gps: boolean;
}

/** Update user settings (PATCH /auth/settings) */
export interface SettingsUpdate {
  garmin_to_strava_sync_disabled?: boolean | null;
  allow_export_without_gps?: boolean | null;
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
  state: string;  // Signed state token for CSRF protection
}

export interface GarminCredentials {
  email: string;
  password: string;
}

/** Response from POST /auth/garmin/credentials; may require MFA step */
export interface GarminCredentialsResponse {
  message: string;
  mfa_required?: boolean;
  mfa_token?: string;
}
