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
  /** IANA timezone for displaying dates. Default UTC when omitted. */
  display_timezone?: string;
  /** Time format: '12h' or '24h'. Default 12h when omitted. */
  display_time_format?: string;
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
  display_timezone?: string | null;
  display_time_format?: string | null; // "12h" | "24h"
}

/** Sync schedule choices (minutes). Default 5. */
export const SYNC_SCHEDULE_OPTIONS = [
  { value: 5, label: '5 min' },
  { value: 10, label: '10 min' },
  { value: 15, label: '15 min' },
  { value: 30, label: '30 min' },
  { value: 45, label: '45 min' },
  { value: 60, label: '1h' },
  { value: 120, label: '2h' },
  { value: 240, label: '4h' },
] as const;

/** FIT device settings (user-level). Written into FIT files on export. */
export interface FitDeviceSettings {
  device_name?: string | null;
  serial_number?: string | null;
  manufacturer_id?: string | null;
  software_version?: string | null;
  product_id?: string | null;
}

/** User settings (GET /auth/settings) */
export interface UserSettings {
  garmin_to_strava_sync_disabled: boolean;
  garmin_to_strava_sync_disabled_override: boolean | null;
  allow_export_without_gps: boolean;
  /** Sync schedule interval in minutes. Default 5. */
  sync_schedule_minutes: number;
  /** FIT device settings for exported files. */
  fit_device_settings?: FitDeviceSettings | null;
}

/** Update user settings (PATCH /auth/settings) */
export interface SettingsUpdate {
  garmin_to_strava_sync_disabled?: boolean | null;
  allow_export_without_gps?: boolean | null;
  sync_schedule_minutes?: number | null;
  fit_device_settings?: FitDeviceSettings | null;
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
