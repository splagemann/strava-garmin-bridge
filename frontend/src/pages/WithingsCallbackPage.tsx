import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { authApi } from '../api/auth';
import { toast } from 'sonner';

export default function WithingsCallbackPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [status, setStatus] = useState<'processing' | 'error'>('processing');
  const [hasProcessed, setHasProcessed] = useState(false);

  useEffect(() => {
    const code = searchParams.get('code');
    const state = searchParams.get('state');

    const callbackKey = `${code}_${state}`;
    const lastProcessedKey = sessionStorage.getItem('last_withings_callback');

    if (hasProcessed || lastProcessedKey === callbackKey) {
      return;
    }

    const handleCallback = async () => {
      setHasProcessed(true);
      sessionStorage.setItem('last_withings_callback', callbackKey);
      
      const error = searchParams.get('error');

      if (error) {
        toast.error(`Withings authorization failed: ${error}`);
        setStatus('error');
        setTimeout(() => navigate('/auth'), 2000);
        return;
      }

      if (!code || !state) {
        toast.error('Missing code or state');
        setStatus('error');
        setTimeout(() => navigate('/auth'), 2000);
        return;
      }

      try {
        await authApi.handleWithingsCallback(code, state);
        toast.success('Successfully connected to Withings!');
        
        setTimeout(() => {
          navigate('/auth');
        }, 100);
      } catch (error: any) {
        console.error('Error connecting to Withings:', error);
        toast.error(error.message || 'Failed to connect to Withings');
        setStatus('error');
        setTimeout(() => navigate('/auth'), 2000);
      }
    };

    handleCallback();
  }, [searchParams, navigate, hasProcessed]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="text-center">
        {status === 'processing' ? (
          <>
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto mb-4"></div>
            <h2 className="text-xl font-semibold text-gray-900 mb-2">
              Connecting to Withings...
            </h2>
          </>
        ) : (
          <>
            <div className="text-red-500 mb-4">
              <svg className="w-12 h-12 mx-auto" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
              </svg>
            </div>
            <h2 className="text-xl font-semibold text-gray-900 mb-2">
              Connection Failed
            </h2>
          </>
        )}
      </div>
    </div>
  );
}
