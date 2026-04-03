import axios from 'axios';

// Support runtime configuration via window.ENV (for Docker production)
// Falls back to build-time Vite env var (for development), then localhost
const API_BASE_URL = (window as any).ENV?.BACKEND_API_URL || import.meta.env.VITE_API_URL || 'http://localhost:8000';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add JWT Bearer token to all requests
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('auth_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Handle errors globally
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      const url: string = error.config?.url ?? '';
      // Garmin/Withings credential endpoints return 401 for bad third-party credentials,
      // NOT because the app session is invalid. Don't log the user out for those.
      const isThirdPartyCredentialEndpoint =
        url.includes('/auth/garmin/') || url.includes('/auth/withings/');

      if (!isThirdPartyCredentialEndpoint) {
        localStorage.removeItem('auth_token');
        localStorage.removeItem('user_email');
        localStorage.removeItem('athlete_id');
        window.location.href = '/auth';
      }
    }
    return Promise.reject(error);
  }
);

/**
 * Check if JWT token is expired
 */
export function isTokenExpired(token: string): boolean {
  try {
    const payload = JSON.parse(atob(token.split('.')[1]));
    return payload.exp * 1000 < Date.now();
  } catch {
    return true;
  }
}

/**
 * Get current auth token
 */
export function getAuthToken(): string | null {
  const token = localStorage.getItem('auth_token');
  if (!token) {
    return null;
  }

  // Check if token is expired
  if (isTokenExpired(token)) {
    localStorage.removeItem('auth_token');
    localStorage.removeItem('user_email');
    localStorage.removeItem('athlete_id');
    return null;
  }

  return token;
}

/**
 * Check if user is authenticated
 */
export function isAuthenticated(): boolean {
  return getAuthToken() !== null;
}
