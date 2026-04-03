import { useState, useEffect } from 'react';
import { useAuth } from '../hooks/useAuth';
import { toast } from 'sonner';
import { authApi } from '../api/auth';

function getDisplayTimezoneOptions(): { value: string; label: string }[] {
  const utc = { value: 'UTC', label: 'UTC' };
  if (typeof Intl?.supportedValuesOf !== 'function') return [utc];
  const rest = Intl.supportedValuesOf('timeZone')
    .filter((tz) => tz !== 'UTC')
    .sort()
    .map((tz) => ({ value: tz, label: tz }));
  return [utc, ...rest];
}
const DISPLAY_TIMEZONE_OPTIONS = getDisplayTimezoneOptions();

export default function ProfilePage() {
  const { authStatus, refetchAuthStatus } = useAuth();
  const [email, setEmail] = useState('');
  const [username, setUsername] = useState('');
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [displayTimezone, setDisplayTimezone] = useState('UTC');
  const [displayTimeFormat, setDisplayTimeFormat] = useState<'12h' | '24h'>('12h');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (authStatus) {
      setEmail(authStatus.email ?? '');
      setUsername(authStatus.username ?? '');
      setFirstName(authStatus.first_name ?? '');
      setLastName(authStatus.last_name ?? '');
      setDisplayTimezone(authStatus.display_timezone ?? 'UTC');
      setDisplayTimeFormat((authStatus.display_time_format === '24h' ? '24h' : '12h'));
    }
  }, [authStatus]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      await authApi.updateProfile({
        email: email.trim() || undefined,
        username: username.trim() || null,
        first_name: firstName.trim() || null,
        last_name: lastName.trim() || null,
        display_timezone: displayTimezone || 'UTC',
        display_time_format: displayTimeFormat,
      });
      toast.success('Profile updated');
      refetchAuthStatus();
    } catch (error: any) {
      const msg = error.response?.data?.detail ?? 'Failed to update profile';
      toast.error(typeof msg === 'string' ? msg : 'Failed to update profile');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Profile</h1>
      <div className="bg-white rounded-lg shadow p-4 sm:p-6">
        <form onSubmit={handleSubmit} className="space-y-6 max-w-xl">
          <div>
            <label htmlFor="profile-email" className="block text-sm font-medium text-gray-700 mb-1">
              Email
            </label>
            <input
              id="profile-email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
              required
            />
          </div>
          <div>
            <label htmlFor="profile-username" className="block text-sm font-medium text-gray-700 mb-1">
              Username
            </label>
            <input
              id="profile-username"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="Optional"
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
            />
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label htmlFor="profile-first-name" className="block text-sm font-medium text-gray-700 mb-1">
                First name
              </label>
              <input
                id="profile-first-name"
                type="text"
                value={firstName}
                onChange={(e) => setFirstName(e.target.value)}
                placeholder="Optional"
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
              />
            </div>
            <div>
              <label htmlFor="profile-last-name" className="block text-sm font-medium text-gray-700 mb-1">
                Last name
              </label>
              <input
                id="profile-last-name"
                type="text"
                value={lastName}
                onChange={(e) => setLastName(e.target.value)}
                placeholder="Optional"
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
              />
            </div>
          </div>
          <div>
            <label htmlFor="profile-display-timezone" className="block text-sm font-medium text-gray-700 mb-1">
              Display timezone
            </label>
            <select
              id="profile-display-timezone"
              value={displayTimezone}
              onChange={(e) => setDisplayTimezone(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
            >
              {DISPLAY_TIMEZONE_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
            <p className="text-xs text-gray-500 mt-1">Used for dates in Sync History and elsewhere. Stored times are UTC.</p>
          </div>
          <div>
            <label htmlFor="profile-display-time-format" className="block text-sm font-medium text-gray-700 mb-1">
              Time format
            </label>
            <select
              id="profile-display-time-format"
              value={displayTimeFormat}
              onChange={(e) => setDisplayTimeFormat(e.target.value as '12h' | '24h')}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
            >
              <option value="12h">12-hour (AM/PM)</option>
              <option value="24h">24-hour</option>
            </select>
          </div>
          <button
            type="submit"
            disabled={saving}
            className="bg-primary hover:bg-primary/90 text-white font-medium py-2 px-4 rounded-md disabled:opacity-50 cursor-pointer"
          >
            {saving ? 'Saving...' : 'Save profile'}
          </button>
        </form>
      </div>
    </div>
  );
}
