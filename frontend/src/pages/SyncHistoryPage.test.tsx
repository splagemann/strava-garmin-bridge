import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '../test/test-utils';
import SyncHistoryPage from './SyncHistoryPage';
import { useSync } from '../hooks/useSync';
import { syncApi } from '../api';

// Mock useSync
vi.mock('../hooks/useSync', () => ({
  useSync: vi.fn(),
}));

// Mock syncApi
vi.mock('../api', () => ({
  syncApi: {
    getSyncLogDetails: vi.fn(),
  },
}));

describe('SyncHistoryPage', () => {
  const mockSyncHistory = [
    {
      id: 1,
      activity_name: 'Morning Run',
      activity_type: 'Run',
      status: 'success',
      sync_direction: 'strava_to_garmin',
      created_at: '2023-01-01T10:00:00Z',
      source_activity_id: '123',
    },
    {
      id: 2,
      activity_name: 'Evening Ride',
      activity_type: 'Ride',
      status: 'failed',
      error_message: 'Some error',
      sync_direction: 'garmin_to_strava',
      created_at: '2023-01-02T10:00:00Z',
      source_activity_id: '456',
    },
    {
        id: 3,
        activity_name: 'Weight',
        activity_type: 'weight',
        status: 'success',
        sync_direction: 'withings_to_garmin',
        created_at: '2023-01-03T10:00:00Z',
        source_activity_id: '789',
    }
  ];

  const mockRetrySync = vi.fn();
  const mockDeleteSyncLog = vi.fn();
  const mockBulkDeleteSyncLogs = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    (useSync as any).mockReturnValue({
      syncHistory: mockSyncHistory,
      retrySync: mockRetrySync,
      deleteSyncLog: mockDeleteSyncLog,
      bulkDeleteSyncLogs: mockBulkDeleteSyncLogs,
      isRetrying: false,
      isDeleting: false,
    });
  });

  it('renders sync history list', () => {
    render(<SyncHistoryPage />);
    expect(screen.getByText('Morning Run')).toBeInTheDocument();
    expect(screen.getByText('Evening Ride')).toBeInTheDocument();
    expect(screen.getByText('Weight')).toBeInTheDocument();
  });

  it('filters by direction', () => {
    render(<SyncHistoryPage />);
    
    // Select filter
    const select = screen.getByRole('combobox'); // The first one is likely the direction filter if structure is flat
    // Or we can find by label if present, or surrounding text. 
    // In code: <label ...>Direction:</label><select ...>
    
    // Let's use fireEvent on the select directly by finding it near the label
    // Using getAllByRole might return multiple if bulk delete is open (it's not initially)
    
    fireEvent.change(select, { target: { value: 'strava_to_garmin' } });
    
    // Should show Morning Run but not Evening Ride
    expect(screen.getByText('Morning Run')).toBeInTheDocument();
    expect(screen.queryByText('Evening Ride')).not.toBeInTheDocument();
    
    fireEvent.change(select, { target: { value: 'withings_to_garmin' } });
    expect(screen.getByText('Weight')).toBeInTheDocument();
    expect(screen.queryByText('Morning Run')).not.toBeInTheDocument();
  });

  it('handles delete', async () => {
    // Mock window.confirm
    window.confirm = vi.fn(() => true);
    
    render(<SyncHistoryPage />);
    
    // Find delete buttons. There are multiple.
    const deleteButtons = screen.getAllByText('Delete');
    fireEvent.click(deleteButtons[0]); // Delete first item
    
    await waitFor(() => {
      expect(mockDeleteSyncLog).toHaveBeenCalledWith(1);
    });
  });

  it('handles retry', async () => {
    render(<SyncHistoryPage />);
    
    // Retry button only appears for failed items
    const retryButton = screen.getByText('Retry');
    fireEvent.click(retryButton);
    
    await waitFor(() => {
      expect(mockRetrySync).toHaveBeenCalledWith(2);
    });
  });

  it('handles bulk delete', async () => {
    window.confirm = vi.fn(() => true);
    mockBulkDeleteSyncLogs.mockResolvedValue({ message: 'Deleted' });

    render(<SyncHistoryPage />);
    
    // Open bulk delete
    fireEvent.click(screen.getByText('Bulk Delete'));
    
    // Click actual delete button inside the panel
    const deleteButton = screen.getByText('Delete Logs');
    fireEvent.click(deleteButton);
    
    await waitFor(() => {
      expect(mockBulkDeleteSyncLogs).toHaveBeenCalledWith({});
    });
  });

  it('views details', async () => {
    const mockDetails = { ...mockSyncHistory[0], strava_data: { id: 123 } };
    (syncApi.getSyncLogDetails as any).mockResolvedValue(mockDetails);

    render(<SyncHistoryPage />);
    
    const detailsButtons = screen.getAllByText('Details');
    fireEvent.click(detailsButtons[0]);
    
    await waitFor(() => {
      expect(syncApi.getSyncLogDetails).toHaveBeenCalledWith(1);
      expect(screen.getByText('Sync Details')).toBeInTheDocument();
      // Check if details content is rendered
      expect(screen.getByText(/Source Activity ID:/)).toBeInTheDocument();
    });
    
    // Close modal
    fireEvent.click(screen.getByText('Close'));
    expect(screen.queryByText('Sync Details')).not.toBeInTheDocument();
  });
});
