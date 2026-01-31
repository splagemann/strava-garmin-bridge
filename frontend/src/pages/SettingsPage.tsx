import { useEffect, useState } from 'react';
import { useAuth } from '../hooks/useAuth';
import { useSync } from '../hooks/useSync';
import { toast } from 'sonner';
import { authApi } from '../api/auth';

export default function SettingsPage() {
  const { refetchAuthStatus } = useAuth();
  const { refetch } = useSync();
  const [settingsGarminToStravaDisabled, setSettingsGarminToStravaDisabled] = useState(false);
  const [settingsAllowExportWithoutGps, setSettingsAllowExportWithoutGps] = useState(false);
  const [settingsLoading, setSettingsLoading] = useState(false);
  const [settingsSaving, setSettingsSaving] = useState(false);

  useEffect(() => {
    setSettingsLoading(true);
    authApi
      .getSettings()
      .then((s) => {
        setSettingsGarminToStravaDisabled(s.garmin_to_strava_sync_disabled);
        setSettingsAllowExportWithoutGps(s.allow_export_without_gps);
      })
      .catch(() => toast.error('Failed to load settings'))
      .finally(() => setSettingsLoading(false));
  }, []);

  const handleSaveSettings = async (e: React.FormEvent) => {
    e.preventDefault();
    setSettingsSaving(true);
    try {
      await authApi.updateSettings({
        garmin_to_strava_sync_disabled: settingsGarminToStravaDisabled,
        allow_export_without_gps: settingsAllowExportWithoutGps,
      });
      toast.success('Settings saved');
      refetchAuthStatus();
      refetch();
    } catch (error: any) {
      const res = error.response;
      const detail = res?.data?.detail;
      let message = 'Failed to save settings';
      if (typeof detail === 'string') message = detail;
      else if (Array.isArray(detail) && detail[0]?.msg) message = detail[0].msg;
      else if (res?.status) message = `Error ${res.status}: ${message}`;
      console.error('Save settings failed:', res?.status, res?.data, error.message);
      toast.error(message);
    } finally {
      setSettingsSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Settings</h1>
      <div className="bg-white rounded-lg shadow p-4 sm:p-6">
        {settingsLoading ? (
          <div className="text-gray-500">Loading settings...</div>
        ) : (
          <form onSubmit={handleSaveSettings} className="space-y-6 max-w-xl">
            <div className="flex items-start gap-4">
              <input
                id="garmin-to-strava-disabled"
                type="checkbox"
                checked={settingsGarminToStravaDisabled}
                onChange={(e) => setSettingsGarminToStravaDisabled(e.target.checked)}
                className="mt-1 h-4 w-4 rounded border-gray-300 text-primary focus:ring-primary"
              />
              <div>
                <label htmlFor="garmin-to-strava-disabled" className="font-medium text-gray-900 cursor-pointer">
                  Disable Garmin → Strava sync
                </label>
                <p className="text-sm text-gray-500 mt-0.5">
                  When checked, Garmin → Strava sync is off (only Strava → Garmin runs). When unchecked, activities are synced both ways (Strava ↔ Garmin).
                </p>
              </div>
            </div>
            <div className="flex items-start gap-4">
              <input
                id="export-without-gps"
                type="checkbox"
                checked={settingsAllowExportWithoutGps}
                onChange={(e) => setSettingsAllowExportWithoutGps(e.target.checked)}
                className="mt-1 h-4 w-4 rounded border-gray-300 text-primary focus:ring-primary"
              />
              <div>
                <label htmlFor="export-without-gps" className="font-medium text-gray-900 cursor-pointer">
                  Enable export without GPS
                </label>
                <p className="text-sm text-gray-500 mt-0.5">
                  When enabled, indoor or manual activities (no GPS) can be synced in both directions: Strava → Garmin and Garmin → Strava. When disabled, only activities with GPS are synced.
                </p>
              </div>
            </div>
            <button
              type="submit"
              disabled={settingsSaving}
              className="bg-primary hover:bg-primary/90 text-white font-medium py-2 px-4 rounded-md disabled:opacity-50 cursor-pointer"
            >
              {settingsSaving ? 'Saving...' : 'Save settings'}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
