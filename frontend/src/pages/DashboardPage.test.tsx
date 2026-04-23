import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '../test/test-utils';
import DashboardPage from './DashboardPage';
import { useAuth } from '../hooks/useAuth';
import { useSync } from '../hooks/useSync';
import { syncApi } from '../api/sync';

// Mock hooks
vi.mock('../hooks/useAuth', () => ({
  useAuth: vi.fn(),
}));

vi.mock('../hooks/useSync', () => ({
  useSync: vi.fn(),
}));

// Mock syncApi
vi.mock('../api/sync', () => ({
  syncApi: {
    manualSyncGarminToStrava: vi.fn(),
  },
}));

// Mock ActivitiesList component to simplify test
vi.mock('../components/ActivitiesList', () => ({
  ActivitiesList: () => <div data-testid="activities-list">Activities List</div>,
}));

describe('DashboardPage', () => {
  const mockSyncStats = {
    total: 10,
    success: 8,
    failed: 2,
    skipped: 0,
    success_rate: 80,
  };

  const mockSyncHistory = [
    {
      id: 1,
      activity_name: 'Activity 1',
      activity_type: 'Run',
      status: 'success',
      sync_direction: 'strava_to_garmin',
      created_at: '2023-01-01T10:00:00Z',
    },
  ];

  const mockConnectWithings = vi.fn();
  const mockSaveGarminCredentials = vi.fn();
  const mockVerifyGarminMfa = vi.fn();
  const mockManualSync = vi.fn();
  const mockRefetch = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    (useAuth as any).mockReturnValue({
      authStatus: { garmin_connected: true, withings_connected: false },
      connectWithings: mockConnectWithings,
      saveGarminCredentials: mockSaveGarminCredentials,
      verifyGarminMfa: mockVerifyGarminMfa,
      isSavingGarmin: false,
      isVerifyingGarminMfa: false,
    });
    (useSync as any).mockReturnValue({
      syncStats: mockSyncStats,
      syncHistory: mockSyncHistory,
      manualSync: mockManualSync,
      isSyncing: false,
      refetch: mockRefetch,
    });
  });

  it('renders stats', () => {
    render(<DashboardPage />);
    expect(screen.getByText('80.0%')).toBeInTheDocument();
    expect(screen.getByText('Total Syncs')).toBeInTheDocument();
  });

  it('renders connections status', () => {
    render(<DashboardPage />);
    expect(screen.getByText('Strava')).toBeInTheDocument();
    expect(screen.getByText('Garmin')).toBeInTheDocument();
    expect(screen.getByText('Connect Withings')).toBeInTheDocument();
  });

  it('shows Garmin setup and blocks manual sync when Garmin is disconnected', async () => {
    (useAuth as any).mockReturnValue({
      authStatus: { garmin_connected: false, withings_connected: false },
      connectWithings: mockConnectWithings,
      saveGarminCredentials: mockSaveGarminCredentials,
      verifyGarminMfa: mockVerifyGarminMfa,
      isSavingGarmin: false,
      isVerifyingGarminMfa: false,
    });

    render(<DashboardPage />);

    expect(screen.getByText('Garmin Disconnected')).toBeInTheDocument();
    expect(screen.getByText('Connect Garmin')).toBeInTheDocument();
    expect(screen.getByText('Connect Garmin before syncing Strava activities to Garmin.')).toBeInTheDocument();
    expect(screen.getByText('Sync Activity')).toBeDisabled();
    expect(screen.getByRole('button', { name: /Garmin → Strava/ })).toBeDisabled();
  });

  it('handles Garmin credentials submission', async () => {
    mockSaveGarminCredentials.mockResolvedValue({ requires_mfa: false });
    (useAuth as any).mockReturnValue({
      authStatus: { garmin_connected: false, withings_connected: false },
      connectWithings: mockConnectWithings,
      saveGarminCredentials: mockSaveGarminCredentials,
      verifyGarminMfa: mockVerifyGarminMfa,
      isSavingGarmin: false,
      isVerifyingGarminMfa: false,
    });

    render(<DashboardPage />);

    fireEvent.change(screen.getByLabelText('Garmin Email'), { target: { value: 'test@garmin.com' } });
    fireEvent.change(screen.getByLabelText('Garmin Password'), { target: { value: 'password123' } });
    fireEvent.click(screen.getByText('Save Garmin Credentials'));

    await waitFor(() => {
      expect(mockSaveGarminCredentials).toHaveBeenCalledWith({
        email: 'test@garmin.com',
        password: 'password123',
      });
    });
  });

  it('handles Withings connection', async () => {
    render(<DashboardPage />);
    fireEvent.click(screen.getByText('Connect Withings'));
    
    await waitFor(() => {
      expect(mockConnectWithings).toHaveBeenCalled();
    });
  });

  it('handles Strava to Garmin manual sync', async () => {
    render(<DashboardPage />);
    
    const input = screen.getByPlaceholderText('Strava Activity ID');
    fireEvent.change(input, { target: { value: '12345' } });
    
    const button = screen.getByText('Sync Activity');
    fireEvent.click(button);
    
    await waitFor(() => {
      expect(mockManualSync).toHaveBeenCalledWith({ strava_activity_id: '12345' });
      expect(mockRefetch).toHaveBeenCalled();
    });
  });

  it('switches tabs and handles Garmin to Strava sync', async () => {
    (syncApi.manualSyncGarminToStrava as any).mockResolvedValue({ status: 'success' });

    render(<DashboardPage />);
    
    // Switch tab
    const tabButton = screen.getByText('Garmin → Strava');
    fireEvent.click(tabButton);
    
    expect(screen.getByPlaceholderText('Garmin Activity ID')).toBeInTheDocument();
    
    const input = screen.getByPlaceholderText('Garmin Activity ID');
    fireEvent.change(input, { target: { value: '67890' } });
    
    // Find button again as re-render happened
    const syncButtons = screen.getAllByText('Sync Activity');
    fireEvent.click(syncButtons[0]); // Visible one
    
    await waitFor(() => {
      expect(syncApi.manualSyncGarminToStrava).toHaveBeenCalledWith({ garmin_activity_id: '67890' });
      expect(mockRefetch).toHaveBeenCalled();
    });
  });

  it('renders recent syncs', () => {
    render(<DashboardPage />);
    expect(screen.getByText('Activity 1')).toBeInTheDocument();
  });
});
