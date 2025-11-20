import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { authApi } from '../api/auth';
import { toast } from 'sonner';

export default function CallbackPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [status, setStatus] = useState<'processing' | 'error'>('processing');

  useEffect(() => {
    const handleCallback = async () => {
      const code = searchParams.get('code');
      const scope = searchParams.get('scope');
      const error = searchParams.get('error');

      // Handle Strava OAuth error
      if (error) {
        toast.error(`Strava authorization failed: ${error}`);
        setStatus('error');
        setTimeout(() => navigate('/auth'), 2000);
        return;
      }

      // Handle missing code
      if (!code) {
        toast.error('No authorization code received from Strava');
        setStatus('error');
        setTimeout(() => navigate('/auth'), 2000);
        return;
      }

      // Exchange code for user data
      try {
        const response = await authApi.exchangeStravaCode(code, scope || undefined);

        if (response.success && response.user_id) {
          // Store user ID in localStorage
          localStorage.setItem('user_id', response.user_id.toString());

          toast.success('Successfully connected to Strava!');

          // Redirect to auth page to complete setup
          navigate('/auth');
        } else {
          throw new Error('Invalid response from server');
        }
      } catch (error: any) {
        console.error('Error exchanging Strava code:', error);
        toast.error(error.response?.data?.detail || 'Failed to connect to Strava');
        setStatus('error');
        setTimeout(() => navigate('/auth'), 2000);
      }
    };

    handleCallback();
  }, [searchParams, navigate]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="text-center">
        {status === 'processing' ? (
          <>
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-orange-500 mx-auto mb-4"></div>
            <h2 className="text-xl font-semibold text-gray-900 mb-2">
              Connecting to Strava...
            </h2>
            <p className="text-gray-600">Please wait while we complete the connection.</p>
          </>
        ) : (
          <>
            <div className="text-red-500 mb-4">
              <svg className="w-12 h-12 mx-auto" fill="currentColor" viewBox="0 0 20 20">
                <path
                  fillRule="evenodd"
                  d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
                  clipRule="evenodd"
                />
              </svg>
            </div>
            <h2 className="text-xl font-semibold text-gray-900 mb-2">
              Connection Failed
            </h2>
            <p className="text-gray-600">Redirecting back to login...</p>
          </>
        )}
      </div>
    </div>
  );
}
