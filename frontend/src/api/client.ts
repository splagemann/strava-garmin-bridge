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

// Add user_id to all requests
apiClient.interceptors.request.use((config) => {
  const userId = localStorage.getItem('user_id');
  if (userId) {
    if (!config.params) {
      config.params = {};
    }
    config.params.user_id = userId;
  }
  return config;
});

// Handle errors globally
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Clear user_id and redirect to auth
      localStorage.removeItem('user_id');
      window.location.href = '/auth';
    }
    return Promise.reject(error);
  }
);
