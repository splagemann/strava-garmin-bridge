import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '../test/test-utils';
import AuthPage from './AuthPage';
import * as useAuthHook from '../hooks/useAuth';

// Mock useAuth
vi.mock('../hooks/useAuth', () => ({
  useAuth: vi.fn(),
}));

// Mock useNavigate
const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

describe('AuthPage', () => {
  const defaultAuthStatus = {
    email: 'test@example.com',
    strava_connected: false,
    garmin_connected: false,
    withings_connected: false,
    strava_athlete_id: null,
  };

  const mockConnectStrava = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    (useAuthHook.useAuth as any).mockReturnValue({
      authStatus: defaultAuthStatus,
      connectStrava: mockConnectStrava,
    });
  });

  it('renders Strava connection section', () => {
    render(<AuthPage />);
    expect(screen.getByText('Connect Strava')).toBeInTheDocument();
    expect(screen.getByText('Connect with Strava')).toBeInTheDocument();
  });

  it('handles Strava connection click', async () => {
    render(<AuthPage />);
    
    const button = screen.getByText('Connect with Strava');
    fireEvent.click(button);
    
    await waitFor(() => {
      expect(mockConnectStrava).toHaveBeenCalled();
    });
  });

  it('shows connected state for Strava', () => {
    (useAuthHook.useAuth as any).mockReturnValue({
      ...useAuthHook.useAuth(),
      authStatus: { ...defaultAuthStatus, strava_connected: true },
    });

    render(<AuthPage />);
    expect(screen.getByText('Connected to Strava')).toBeInTheDocument();
  });

  it('does not render optional integrations on the login page', () => {
    render(<AuthPage />);

    expect(screen.queryByText('Connect Withings')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Garmin Email')).not.toBeInTheDocument();
  });

  it('redirects when Strava is connected', () => {
    (useAuthHook.useAuth as any).mockReturnValue({
        authStatus: { ...defaultAuthStatus, strava_connected: true, garmin_connected: false },
        connectStrava: mockConnectStrava,
    });

    render(<AuthPage />);
    expect(mockNavigate).toHaveBeenCalledWith('/');
  });
});
