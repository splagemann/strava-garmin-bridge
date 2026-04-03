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

function GarminReAuthSection() {
  const { saveGarminCredentials, submitGarminMfa, isSavingGarmin, isSubmittingGarminMfa, refetchAuthStatus } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [mfaToken, setMfaToken] = useState<string | null>(null);
  const [mfaCode, setMfaCode] = useState('');

  const handleCredentialsSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const result = await saveGarminCredentials({ email, password });
      if (result?.mfa_required && result?.mfa_token) {
        setMfaToken(result.mfa_token);
        toast.info('Enter the 6-digit code from your authenticator app');
      } else {
        toast.success('Garmin credentials saved');
        setEmail('');
        setPassword('');
        refetchAuthStatus();
      }
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to save Garmin credentials');
    }
  };

  const handleMfaSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!mfaToken || !mfaCode.trim()) return;
    try {
      await submitGarminMfa(mfaToken, mfaCode.trim());
      toast.success('Garmin re-authenticated successfully');
      setMfaToken(null);
      setMfaCode('');
      setEmail('');
      setPassword('');
      refetchAuthStatus();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Invalid verification code');
    }
  };

  return (
    <div className="border-t border-gray-200 pt-6">
      <h2 className="font-medium text-gray-900 mb-1">Garmin account</h2>
      <p className="text-sm text-gray-500 mb-4">
        Re-enter your Garmin credentials if the connection has expired or MFA was requested.
        This will refresh the stored session without affecting any other settings.
      </p>

      {mfaToken ? (
        <form onSubmit={handleMfaSubmit} className="space-y-4 max-w-sm">
          <p className="text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded-md px-3 py-2">
            Garmin requires a verification code. Enter the 6-digit code from your authenticator app.
          </p>
          <div>
            <label htmlFor="settings-mfa-code" className="block text-sm font-medium text-gray-700 mb-1">
              Verification code
            </label>
            <input
              id="settings-mfa-code"
              type="text"
              inputMode="numeric"
              autoComplete="one-time-code"
              placeholder="000000"
              maxLength={8}
              value={mfaCode}
              onChange={(e) => setMfaCode(e.target.value.replace(/\D/g, ''))}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary font-mono text-lg tracking-widest"
              autoFocus
            />
          </div>
          <div className="flex gap-3">
            <button
              type="button"
              onClick={() => { setMfaToken(null); setMfaCode(''); }}
              className="flex-1 py-2 px-4 border border-gray-300 rounded-md text-sm text-gray-700 hover:bg-gray-50 cursor-pointer"
            >
              Back
            </button>
            <button
              type="submit"
              disabled={isSubmittingGarminMfa || mfaCode.length < 6}
              className="flex-1 py-2 px-4 bg-primary text-white rounded-md text-sm font-medium hover:bg-primary/90 disabled:opacity-50 cursor-pointer"
            >
              {isSubmittingGarminMfa ? 'Verifying…' : 'Verify'}
            </button>
          </div>
        </form>
      ) : (
        <form onSubmit={handleCredentialsSubmit} className="space-y-4 max-w-sm">
          <div>
            <label htmlFor="settings-garmin-email" className="block text-sm font-medium text-gray-700 mb-1">
              Garmin email
            </label>
            <input
              id="settings-garmin-email"
              type="email"
              required
              autoComplete="username"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary text-sm"
            />
          </div>
          <div>
            <label htmlFor="settings-garmin-password" className="block text-sm font-medium text-gray-700 mb-1">
              Garmin password
            </label>
            <input
              id="settings-garmin-password"
              type="password"
              required
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary text-sm"
            />
          </div>
          <button
            type="submit"
            disabled={isSavingGarmin}
            className="w-full py-2 px-4 bg-primary text-white rounded-md text-sm font-medium hover:bg-primary/90 disabled:opacity-50 cursor-pointer"
          >
            {isSavingGarmin ? 'Connecting…' : 'Re-authenticate Garmin'}
          </button>
        </form>
      )}
    </div>
  );
}

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

      {/* Garmin re-auth — always visible so users can fix a broken session */}
      <div className="bg-white rounded-lg shadow p-4 sm:p-6">
        <GarminReAuthSection />
      </div>
    </div>
  );
}
