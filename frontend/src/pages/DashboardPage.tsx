import { useEffect, useState } from 'react';
import { useAuth } from '../hooks/useAuth';
import { useSync } from '../hooks/useSync';
import { toast } from 'sonner';
import { formatRelativeTime } from '../lib/utils';
import { SYNC_STATUS_COLORS, SYNC_STATUS_LABELS } from '../lib/constants';
import { syncApi } from '../api/sync';
import { ActivitiesList } from '../components/ActivitiesList';

type SyncDirection = 'strava_to_garmin' | 'garmin_to_strava';

export default function DashboardPage() {
  const {
    authStatus,
    connectWithings,
    saveGarminCredentials,
    verifyGarminMfa,
    disconnectGarmin,
    disconnectWithings,
    isSavingGarmin,
    isVerifyingGarminMfa,
    isDisconnectingGarmin,
    isDisconnectingWithings,
  } = useAuth();
  const { syncStats, syncHistory, manualSync, isSyncing, refetch } = useSync();
  const [activeTab, setActiveTab] = useState<SyncDirection>('strava_to_garmin');
  const [stravaActivityId, setStravaActivityId] = useState('');
  const [garminActivityId, setGarminActivityId] = useState('');
  const [garminEmail, setGarminEmail] = useState('');
  const [garminPassword, setGarminPassword] = useState('');
  const [garminMfaCode, setGarminMfaCode] = useState('');
  const [isSyncingGarmin, setIsSyncingGarmin] = useState(false);
  const [requiresGarminMfa, setRequiresGarminMfa] = useState(false);

  const garminConnected = !!authStatus?.garmin_connected;
  const garminNeedsAttention = !!authStatus?.garmin_requires_mfa;
  const canDisconnectGarmin = garminConnected || garminNeedsAttention;

  useEffect(() => {
    if (!garminConnected && activeTab === 'garmin_to_strava') {
      setActiveTab('strava_to_garmin');
    }
  }, [activeTab, garminConnected]);

  useEffect(() => {
    setRequiresGarminMfa(!!authStatus?.garmin_requires_mfa);
  }, [authStatus?.garmin_requires_mfa]);

  const handleWithingsConnect = async () => {
    try {
      await connectWithings();
    } catch (error: any) {
      toast.error('Failed to initiate Withings connection');
    }
  };

  const handleGarminSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const response = await saveGarminCredentials({
        email: garminEmail,
        password: garminPassword,
      });

      if (response.requires_mfa) {
        setRequiresGarminMfa(true);
        toast.success('Garmin credentials accepted. Enter your MFA code to finish setup.');
      } else {
        setGarminEmail('');
        setGarminPassword('');
        toast.success('Garmin credentials saved successfully!');
      }
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Failed to save Garmin credentials');
    }
  };

  const handleGarminMfaSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await verifyGarminMfa(garminMfaCode);
      setGarminMfaCode('');
      setRequiresGarminMfa(false);
      toast.success('Garmin MFA verified successfully!');
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Failed to verify Garmin MFA code');
    }
  };

  const handleGarminDisconnect = async () => {
    if (!window.confirm('Disconnect Garmin? This will remove stored Garmin credentials and any pending MFA state.')) {
      return;
    }

    try {
      await disconnectGarmin();
      setGarminEmail('');
      setGarminPassword('');
      setGarminMfaCode('');
      setRequiresGarminMfa(false);
      if (activeTab === 'garmin_to_strava') {
        setActiveTab('strava_to_garmin');
      }
      toast.success('Garmin disconnected successfully.');
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Failed to disconnect Garmin');
    }
  };

  const handleWithingsDisconnect = async () => {
    if (!window.confirm('Disconnect Withings? This will remove stored Withings access for this app.')) {
      return;
    }

    try {
      await disconnectWithings();
      toast.success('Withings disconnected successfully.');
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Failed to disconnect Withings');
    }
  };

  const handleManualSync = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!garminConnected) {
      toast.error('Connect Garmin before syncing activities.');
      return;
    }

    try {
      // Keep ID as string to safely handle 64-bit Strava IDs
      await manualSync({ strava_activity_id: stravaActivityId });
      toast.success('Activity synced successfully!');
      setStravaActivityId('');
      refetch();
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Failed to sync activity');
    }
  };

  const handleManualSyncGarminToStrava = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!garminConnected) {
      toast.error('Connect Garmin before syncing activities.');
      return;
    }

    setIsSyncingGarmin(true);
    try {
      const result = await syncApi.manualSyncGarminToStrava({ garmin_activity_id: garminActivityId });
      if (result.status === 'success') {
        toast.success('Activity synced successfully from Garmin to Strava!');
      } else if (result.status === 'skipped') {
        toast.info(result.message);
      } else {
        toast.error(result.message || 'Failed to sync activity');
      }
      setGarminActivityId('');
      refetch();
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Failed to sync activity');
    } finally {
      setIsSyncingGarmin(false);
    }
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Dashboard</h1>

      {/* Connections Status */}
      <div className="bg-white rounded-lg shadow p-4 sm:p-6">
        <h2 className="text-lg font-semibold mb-4">Connections</h2>
        <div className="flex flex-wrap gap-4 mb-6">
          {canDisconnectGarmin ? (
            <div className="flex items-center gap-3 px-3 py-2 rounded-md border border-green-200 bg-green-50 text-green-700">
              <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                <path
                  fillRule="evenodd"
                  d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                  clipRule="evenodd"
                />
              </svg>
              <span className="font-medium">{garminConnected ? 'Garmin Connected' : 'Garmin MFA Pending'}</span>
              <button
                type="button"
                onClick={handleGarminDisconnect}
                disabled={isDisconnectingGarmin}
                className="text-sm font-medium text-red-700 hover:text-red-800 disabled:opacity-50"
              >
                {isDisconnectingGarmin ? 'Disconnecting...' : 'Disconnect'}
              </button>
            </div>
          ) : (
            <div className="flex items-center gap-2 px-3 py-2 bg-amber-50 text-amber-700 rounded-md border border-amber-200">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v4m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
              </svg>
              <span className="font-medium">{requiresGarminMfa ? 'Garmin MFA Required' : 'Garmin Disconnected'}</span>
            </div>
          )}

          {authStatus?.withings_connected ? (
            <div className="flex items-center gap-3 px-3 py-2 bg-green-50 text-green-700 rounded-md border border-green-200">
              <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                <path
                  fillRule="evenodd"
                  d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                  clipRule="evenodd"
                />
              </svg>
              <span className="font-medium">Withings Connected</span>
              <button
                type="button"
                onClick={handleWithingsDisconnect}
                disabled={isDisconnectingWithings}
                className="text-sm font-medium text-red-700 hover:text-red-800 disabled:opacity-50"
              >
                {isDisconnectingWithings ? 'Disconnecting...' : 'Disconnect'}
              </button>
            </div>
          ) : (
            <button
              onClick={handleWithingsConnect}
              className="flex items-center gap-2 px-3 py-2 bg-blue-50 text-blue-700 hover:bg-blue-100 rounded-md border border-blue-200 transition-colors"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4" />
              </svg>
              <span className="font-medium">Connect Withings</span>
            </button>
          )}
        </div>

        {!garminConnected && (
          <div className="border-t pt-4">
            <h3 className="text-base font-semibold mb-2">Connect Garmin</h3>
            <p className="text-sm text-gray-500 mb-4">
              Garmin is optional for app access, but required for activity syncs and Withings weight sync.
            </p>
            <div className="grid gap-4 lg:grid-cols-2">
              <form onSubmit={handleGarminSubmit} className="space-y-3">
                <div>
                  <label htmlFor="garmin-email" className="block text-sm font-medium text-gray-700 mb-1">
                    Garmin Email
                  </label>
                  <input
                    id="garmin-email"
                    type="email"
                    required
                    value={garminEmail}
                    onChange={(e) => setGarminEmail(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
                  />
                </div>
                <div>
                  <label htmlFor="garmin-password" className="block text-sm font-medium text-gray-700 mb-1">
                    Garmin Password
                  </label>
                  <input
                    id="garmin-password"
                    type="password"
                    required
                    value={garminPassword}
                    onChange={(e) => setGarminPassword(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
                  />
                </div>
                <button
                  type="submit"
                  disabled={isSavingGarmin}
                  className="w-full sm:w-auto bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-4 rounded-md transition-colors disabled:opacity-50"
                >
                  {isSavingGarmin ? 'Saving...' : requiresGarminMfa ? 'Restart Garmin Login' : 'Save Garmin Credentials'}
                </button>
              </form>

              {requiresGarminMfa && (
                <form onSubmit={handleGarminMfaSubmit} className="space-y-3">
                  <p className="text-sm text-gray-600">
                    Enter the Garmin multi-factor authentication code from your email, SMS, or authenticator app.
                  </p>
                  <div>
                    <label htmlFor="garmin-mfa-code" className="block text-sm font-medium text-gray-700 mb-1">
                      MFA Code
                    </label>
                    <input
                      id="garmin-mfa-code"
                      type="text"
                      required
                      value={garminMfaCode}
                      onChange={(e) => setGarminMfaCode(e.target.value)}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
                    />
                  </div>
                  <button
                    type="submit"
                    disabled={isVerifyingGarminMfa}
                    className="w-full sm:w-auto bg-indigo-600 hover:bg-indigo-700 text-white font-medium py-2 px-4 rounded-md transition-colors disabled:opacity-50"
                  >
                    {isVerifyingGarminMfa ? 'Verifying...' : 'Verify Garmin MFA'}
                  </button>
                </form>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Stats Grid */}
      {syncStats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 sm:gap-4">
          <div className="bg-white rounded-lg shadow p-4 sm:p-6">
            <div className="text-xs sm:text-sm font-medium text-gray-500">Total Syncs</div>
            <div className="mt-1 sm:mt-2 text-2xl sm:text-3xl font-bold">{syncStats.total}</div>
          </div>
          <div className="bg-white rounded-lg shadow p-4 sm:p-6">
            <div className="text-xs sm:text-sm font-medium text-gray-500">Success</div>
            <div className="mt-1 sm:mt-2 text-2xl sm:text-3xl font-bold text-green-600">{syncStats.success}</div>
          </div>
          <div className="bg-white rounded-lg shadow p-4 sm:p-6">
            <div className="text-xs sm:text-sm font-medium text-gray-500">Failed</div>
            <div className="mt-1 sm:mt-2 text-2xl sm:text-3xl font-bold text-red-600">{syncStats.failed}</div>
          </div>
          <div className="bg-white rounded-lg shadow p-4 sm:p-6">
            <div className="text-xs sm:text-sm font-medium text-gray-500">Success Rate</div>
            <div className="mt-1 sm:mt-2 text-2xl sm:text-3xl font-bold">{syncStats.success_rate.toFixed(1)}%</div>
          </div>
        </div>
      )}

      {/* Manual Sync Form with Tabs */}
      <div className="bg-white rounded-lg shadow">
        <div className="border-b">
          <div className="flex">
            <button
              onClick={() => setActiveTab('strava_to_garmin')}
              className={`flex-1 px-4 sm:px-6 py-3 sm:py-4 text-xs sm:text-sm font-medium transition-colors ${
                activeTab === 'strava_to_garmin'
                  ? 'border-b-2 border-primary text-primary'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              <span className="hidden sm:inline">Strava → Garmin</span>
              <span className="sm:hidden">S → G</span>
            </button>
            <button
              onClick={() => setActiveTab('garmin_to_strava')}
              disabled={!garminConnected}
              className={`flex-1 px-4 sm:px-6 py-3 sm:py-4 text-xs sm:text-sm font-medium transition-colors ${
                activeTab === 'garmin_to_strava'
                  ? 'border-b-2 border-primary text-primary'
                  : garminConnected
                    ? 'text-gray-500 hover:text-gray-700'
                    : 'text-gray-300 cursor-not-allowed'
              }`}
            >
              <span className="hidden sm:inline">Garmin → Strava</span>
              <span className="sm:hidden">G → S</span>
            </button>
          </div>
        </div>

        <div className="p-4 sm:p-6">
          {activeTab === 'strava_to_garmin' ? (
            <div>
              <h2 className="text-base sm:text-lg font-semibold mb-3 sm:mb-4">Sync from Strava to Garmin</h2>
              {!garminConnected && (
                <p className="text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded-md px-3 py-2 mb-4">
                  Connect Garmin before syncing Strava activities to Garmin.
                </p>
              )}
              <form onSubmit={handleManualSync} className="flex flex-col sm:flex-row gap-3 sm:gap-4">
                <input
                  type="text"
                  placeholder="Strava Activity ID"
                  value={stravaActivityId}
                  onChange={(e) => setStravaActivityId(e.target.value)}
                  required
                  pattern="[0-9]+"
                  title="Please enter a valid numeric activity ID"
                  className="flex-1 px-3 sm:px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary text-sm sm:text-base"
                />
                <button
                  type="submit"
                  disabled={isSyncing || !garminConnected}
                  className="bg-primary hover:bg-primary/90 text-white px-4 sm:px-6 py-2 rounded-md font-medium disabled:opacity-50 text-sm sm:text-base whitespace-nowrap"
                >
                  {isSyncing ? 'Syncing...' : 'Sync Activity'}
                </button>
              </form>
            </div>
          ) : (
            <div>
              <h2 className="text-base sm:text-lg font-semibold mb-3 sm:mb-4">Sync from Garmin to Strava</h2>
              <form onSubmit={handleManualSyncGarminToStrava} className="flex flex-col sm:flex-row gap-3 sm:gap-4">
                <input
                  type="text"
                  placeholder="Garmin Activity ID"
                  value={garminActivityId}
                  onChange={(e) => setGarminActivityId(e.target.value)}
                  required
                  className="flex-1 px-3 sm:px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary text-sm sm:text-base"
                />
                <button
                  type="submit"
                  disabled={isSyncingGarmin}
                  className="bg-primary hover:bg-primary/90 text-white px-4 sm:px-6 py-2 rounded-md font-medium disabled:opacity-50 text-sm sm:text-base whitespace-nowrap"
                >
                  {isSyncingGarmin ? 'Syncing...' : 'Sync Activity'}
                </button>
              </form>
            </div>
          )}
        </div>
      </div>

      {/* Recent Activities */}
      <ActivitiesList limit={10} />

      {/* Recent Syncs */}
      <div className="bg-white rounded-lg shadow">
        <div className="px-4 sm:px-6 py-4 border-b">
          <h2 className="text-lg font-semibold">Recent Syncs</h2>
        </div>
        <div className="divide-y">
          {syncHistory.slice(0, 10).map((log) => (
            <div key={log.id} className="px-4 sm:px-6 py-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 hover:bg-gray-50">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <div className="font-medium truncate">{log.activity_name || 'Unnamed Activity'}</div>
                  <span className="text-xs px-2 py-0.5 rounded bg-gray-100 text-gray-600 whitespace-nowrap">
                    {log.sync_direction === 'strava_to_garmin' ? 'S→G' : 'G→S'}
                  </span>
                </div>
                <div className="text-sm text-gray-500">
                  {log.activity_type} • {formatRelativeTime(log.created_at)}
                </div>
              </div>
              <span
                className={`px-3 py-1 rounded-full text-xs font-medium border self-start sm:self-auto whitespace-nowrap ${
                  SYNC_STATUS_COLORS[log.status]
                }`}
              >
                {SYNC_STATUS_LABELS[log.status]}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
