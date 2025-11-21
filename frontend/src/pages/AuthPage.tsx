import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { toast } from 'sonner';

export default function AuthPage() {
  const navigate = useNavigate();
  const { authStatus, connectStrava, saveGarminCredentials, isSavingGarmin, hasAuthToken } = useAuth();
  const [garminEmail, setGarminEmail] = useState('');
  const [garminPassword, setGarminPassword] = useState('');
  const [isConnectingStrava, setIsConnectingStrava] = useState(false);

  // Redirect if fully authenticated
  useEffect(() => {
    if (authStatus?.strava_connected && authStatus?.garmin_connected) {
      navigate('/');
    }
  }, [authStatus, navigate]);

  const handleStravaConnect = async () => {
    setIsConnectingStrava(true);
    try {
      await connectStrava();
    } catch (error: any) {
      console.error('Strava connection error:', error);
      toast.error(error.response?.data?.detail || 'Failed to connect to Strava');
      setIsConnectingStrava(false);
    }
  };

  const handleGarminSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await saveGarminCredentials({
        email: garminEmail,
        password: garminPassword,
      });
      toast.success('Garmin credentials saved successfully!');
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Failed to save Garmin credentials');
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8">
        <div className="text-center">
          <h2 className="text-3xl font-bold text-gray-900">
            Strava → Garmin Bridge
          </h2>
          <p className="mt-2 text-sm text-gray-600">
            Connect your Strava and Garmin accounts to start syncing
          </p>
        </div>

        <div className="space-y-6">
          {/* Strava Connection */}
          <div className="border rounded-lg p-6 bg-white shadow-sm">
            <h3 className="text-lg font-medium mb-4">1. Connect Strava</h3>
            {!authStatus?.strava_connected ? (
              <button
                onClick={handleStravaConnect}
                disabled={isConnectingStrava}
                className="w-full bg-orange-500 hover:bg-orange-600 text-white font-medium py-2 px-4 rounded-md transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isConnectingStrava ? 'Connecting...' : 'Connect with Strava'}
              </button>
            ) : (
              <div className="flex items-center text-green-600">
                <svg className="w-5 h-5 mr-2" fill="currentColor" viewBox="0 0 20 20">
                  <path
                    fillRule="evenodd"
                    d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                    clipRule="evenodd"
                  />
                </svg>
                Connected to Strava
              </div>
            )}
          </div>

          {/* Garmin Connection */}
          {hasAuthToken && (
            <div className="border rounded-lg p-6 bg-white shadow-sm">
              <h3 className="text-lg font-medium mb-4">2. Add Garmin Credentials</h3>
              {!authStatus?.garmin_connected ? (
                <form onSubmit={handleGarminSubmit} className="space-y-4">
                  <div>
                    <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-1">
                      Garmin Email
                    </label>
                    <input
                      id="email"
                      type="email"
                      required
                      value={garminEmail}
                      onChange={(e) => setGarminEmail(e.target.value)}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
                    />
                  </div>
                  <div>
                    <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-1">
                      Garmin Password
                    </label>
                    <input
                      id="password"
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
                    className="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-4 rounded-md transition-colors disabled:opacity-50"
                  >
                    {isSavingGarmin ? 'Saving...' : 'Save Garmin Credentials'}
                  </button>
                </form>
              ) : (
                <div className="flex items-center text-green-600">
                  <svg className="w-5 h-5 mr-2" fill="currentColor" viewBox="0 0 20 20">
                    <path
                      fillRule="evenodd"
                      d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                      clipRule="evenodd"
                    />
                  </svg>
                  Garmin Connected
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
