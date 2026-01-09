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
  const mockConnectWithings = vi.fn();
  const mockSaveGarminCredentials = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    (useAuthHook.useAuth as any).mockReturnValue({
      authStatus: defaultAuthStatus,
      connectStrava: mockConnectStrava,
      connectWithings: mockConnectWithings,
      saveGarminCredentials: mockSaveGarminCredentials,
      isSavingGarmin: false,
      hasAuthToken: false,
    });
  });

  it('renders Strava connection section', () => {
    render(<AuthPage />);
    expect(screen.getByText('1. Connect Strava')).toBeInTheDocument();
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

  it('shows Withings and Garmin sections when authenticated', () => {
    (useAuthHook.useAuth as any).mockReturnValue({
        ...useAuthHook.useAuth(),
        hasAuthToken: true,
    });

    render(<AuthPage />);
    expect(screen.getByText('2. Connect Withings (Optional)')).toBeInTheDocument();
    expect(screen.getByText('3. Add Garmin Credentials')).toBeInTheDocument();
  });

  it('handles Withings connection click', async () => {
    (useAuthHook.useAuth as any).mockReturnValue({
        ...useAuthHook.useAuth(),
        hasAuthToken: true,
    });

    render(<AuthPage />);
    
    const button = screen.getByText('Connect with Withings');
    fireEvent.click(button);
    
    await waitFor(() => {
        expect(mockConnectWithings).toHaveBeenCalled();
    });
  });

  it('handles Garmin credentials submission', async () => {
    (useAuthHook.useAuth as any).mockReturnValue({
        ...useAuthHook.useAuth(),
        hasAuthToken: true,
    });

    render(<AuthPage />);
    
    const emailInput = screen.getByLabelText('Garmin Email');
    const passwordInput = screen.getByLabelText('Garmin Password');
    const submitButton = screen.getByText('Save Garmin Credentials');

    fireEvent.change(emailInput, { target: { value: 'test@garmin.com' } });
    fireEvent.change(passwordInput, { target: { value: 'password123' } });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(mockSaveGarminCredentials).toHaveBeenCalledWith({
        email: 'test@garmin.com',
        password: 'password123',
      });
    });
  });

  it('redirects when fully connected', () => {
    (useAuthHook.useAuth as any).mockReturnValue({
        authStatus: { ...defaultAuthStatus, strava_connected: true, garmin_connected: true },
    });

    render(<AuthPage />);
    expect(mockNavigate).toHaveBeenCalledWith('/');
  });
});
