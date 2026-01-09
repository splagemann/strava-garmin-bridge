import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import App from './App';

// Mock child components to avoid full render tree
vi.mock('./pages/AuthPage', () => ({ default: () => <div>Auth Page</div> }));
vi.mock('./pages/DashboardPage', () => ({ default: () => <div>Dashboard Page</div> }));
vi.mock('./components/layout/Layout', () => ({ default: () => <div>Layout</div> }));

// Mock hooks
vi.mock('./hooks/useAuth', () => ({
  useAuth: () => ({
    isAuthenticated: false,
    isLoading: false,
    hasAuthToken: false,
  }),
}));

describe('App', () => {
  it('renders without crashing', () => {
    render(<App />);
    // Should redirect to auth or show loading, eventually hitting AuthPage mock
    // Since we mocked useAuth to return unauthenticated, it should hit AuthPage via Navigate
    // But testing-library render doesn't handle Navigate well outside of Router?
    // App includes BrowserRouter, so it should be fine.
    
    // Check if something rendered. AuthPage is the default fallback.
    expect(screen.getByText('Auth Page')).toBeInTheDocument();
  });
});
