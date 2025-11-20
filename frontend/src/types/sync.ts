export interface SyncLog {
  id: number;
  strava_activity_id: string;
  garmin_activity_id: string | null;
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
  strava_activity_id: number;
}

export interface ManualSyncResponse {
  status: string;
  strava_activity_id: number;
  message: string;
  garmin_activity_id?: string;
}
