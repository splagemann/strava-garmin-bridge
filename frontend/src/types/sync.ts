export interface SyncLog {
  id: number;
  sync_direction: 'strava_to_garmin' | 'garmin_to_strava' | 'withings_to_garmin';
  source_activity_id: string;
  target_activity_id: string | null;
  strava_activity_id: string;  // Legacy field for backward compatibility
  garmin_activity_id: string | null;  // Legacy field for backward compatibility
  status: 'success' | 'failed' | 'skipped' | 'pending';
  error_message: string | null;
  activity_name: string | null;
  activity_type: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface SyncStats {
  total: number;
  success: number;
  failed: number;
  skipped: number;
  success_rate: number;
}

export interface ManualSyncRequest {
  strava_activity_id: string;  // String to safely handle 64-bit Strava IDs in JavaScript
}

export interface ManualSyncResponse {
  status: string;
  strava_activity_id: string;  // String to safely handle 64-bit IDs
  message: string;
  garmin_activity_id?: string;
}
