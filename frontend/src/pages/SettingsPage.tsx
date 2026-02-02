import { useEffect, useState } from 'react';
import { useAuth } from '../hooks/useAuth';
import { useSync } from '../hooks/useSync';
import { toast } from 'sonner';
import { authApi } from '../api/auth';
import { SYNC_SCHEDULE_OPTIONS } from '../types/auth';
import type { FitDeviceSettings } from '../types/auth';

const DEFAULT_DEVICE: FitDeviceSettings = {
  device_name: '',
  serial_number: '',
  product_id: '',
  manufacturer_id: '',
  software_version: '',
};

export default function SettingsPage() {
  const { refetchAuthStatus } = useAuth();
  const { refetch } = useSync();
  const [settingsGarminToStravaDisabled, setSettingsGarminToStravaDisabled] = useState(false);
  const [settingsAllowExportWithoutGps, setSettingsAllowExportWithoutGps] = useState(false);
  const [settingsSyncScheduleMinutes, setSettingsSyncScheduleMinutes] = useState(5);
  const [fitDevice, setFitDevice] = useState<FitDeviceSettings>(DEFAULT_DEVICE);
  const [settingsLoading, setSettingsLoading] = useState(false);
  const [settingsSaving, setSettingsSaving] = useState(false);

  useEffect(() => {
    setSettingsLoading(true);
    authApi
      .getSettings()
      .then((s) => {
        setSettingsGarminToStravaDisabled(s.garmin_to_strava_sync_disabled);
        setSettingsAllowExportWithoutGps(s.allow_export_without_gps);
        setSettingsSyncScheduleMinutes(s.sync_schedule_minutes ?? 5);
        setFitDevice({ ...DEFAULT_DEVICE, ...s.fit_device_settings });
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
        sync_schedule_minutes: settingsSyncScheduleMinutes,
        fit_device_settings: fitDevice,
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
            <div>
              <label htmlFor="sync-schedule" className="font-medium text-gray-900 block mb-1">
                Sync schedule
              </label>
              <select
                id="sync-schedule"
                value={settingsSyncScheduleMinutes}
                onChange={(e) => setSettingsSyncScheduleMinutes(Number(e.target.value))}
                className="mt-1 block w-full max-w-xs rounded-md border border-gray-300 bg-white py-2 pl-3 pr-8 text-base focus:border-primary focus:ring-primary sm:text-sm"
              >
                {SYNC_SCHEDULE_OPTIONS.map(({ value, label }) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
              <p className="text-sm text-gray-500 mt-0.5">
                How often to check for new activities to sync. Default is 5 minutes.
              </p>
            </div>
            <div className="border-t border-gray-200 pt-6">
              <h2 className="font-medium text-gray-900 mb-2">FIT device settings</h2>
              <p className="text-sm text-gray-500 mb-4">
                Device info written into exported FIT files (Strava → Garmin): device name, serial number, manufacturer ID, software version (e.g. 20.29), product ID (0–65535). Optional.
              </p>
              <div className="space-y-4 max-w-xl">
                {[
                  { key: 'device_name' as const, label: 'Device Name' },
                  { key: 'serial_number' as const, label: 'Serial Number' },
                  { key: 'product_id' as const, label: 'Product ID (FIT product, 0–65535)' },
                  { key: 'manufacturer_id' as const, label: 'Manufacturer ID' },
                  { key: 'software_version' as const, label: 'Software Version (e.g. 20.29)' },
                ].map(({ key, label }) => (
                  <div key={key}>
                    <label htmlFor={key} className="block text-sm font-medium text-gray-700 mb-0.5">
                      {label}
                    </label>
                    <input
                      id={key}
                      type="text"
                      value={fitDevice[key] ?? ''}
                      onChange={(e) =>
                        setFitDevice((prev) => ({ ...prev, [key]: e.target.value || undefined }))
                      }
                      className="block w-full rounded-md border border-gray-300 bg-white py-1.5 px-2 text-sm focus:border-primary focus:ring-primary"
                    />
                  </div>
                ))}
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
