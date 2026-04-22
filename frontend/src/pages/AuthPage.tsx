import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { toast } from 'sonner';

export default function AuthPage() {
  const navigate = useNavigate();
  const {
    authStatus,
    connectStrava,
  } = useAuth();
  const [isConnectingStrava, setIsConnectingStrava] = useState(false);

  useEffect(() => {
    if (authStatus?.strava_connected) {
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

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8">
        <div className="text-center">
          <h2 className="text-3xl font-bold text-gray-900">
            Strava → Garmin Bridge
          </h2>
          <p className="mt-2 text-sm text-gray-600">
            Connect Strava to sign in. Garmin can be added from the dashboard.
          </p>
        </div>

        <div className="space-y-6">
          <div className="border rounded-lg p-6 bg-white shadow-sm">
            <h3 className="text-lg font-medium mb-4">Connect Strava</h3>
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
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                </svg>
                Connected to Strava
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
