import { beforeEach, describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import App from './App';

const mockUseAuth = vi.hoisted(() => vi.fn());

// Mock child components to avoid full render tree
vi.mock('./pages/AuthPage', () => ({ default: () => <div>Auth Page</div> }));
vi.mock('./pages/DashboardPage', () => ({ default: () => <div>Dashboard Page</div> }));
vi.mock('./components/layout/Layout', () => ({ default: () => <div>Layout</div> }));

// Mock hooks
vi.mock('./hooks/useAuth', () => ({
  useAuth: mockUseAuth,
}));

describe('App', () => {
  beforeEach(() => {
    window.history.pushState({}, '', '/');
    mockUseAuth.mockReturnValue({
      isAuthenticated: false,
      isLoading: false,
      hasAuthToken: false,
    });
  });

  it('renders without crashing', () => {
    render(<App />);
    // Should redirect to auth or show loading, eventually hitting AuthPage mock
    // Since we mocked useAuth to return unauthenticated, it should hit AuthPage via Navigate
    // But testing-library render doesn't handle Navigate well outside of Router?
    // App includes BrowserRouter, so it should be fine.
    
    // Check if something rendered. AuthPage is the default fallback.
    expect(screen.getByText('Auth Page')).toBeInTheDocument();
  });

  it('allows protected routes with a Strava-only authenticated session', () => {
    mockUseAuth.mockReturnValue({
      isAuthenticated: true,
      isLoading: false,
      hasAuthToken: true,
      authStatus: {
        email: 'test@example.com',
        strava_connected: true,
        garmin_connected: false,
      },
    });

    render(<App />);

    expect(screen.getByText('Layout')).toBeInTheDocument();
  });
});
