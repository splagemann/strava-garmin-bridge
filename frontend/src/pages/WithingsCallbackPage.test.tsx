import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '../test/test-utils';
import WithingsCallbackPage from './WithingsCallbackPage';
import { authApi } from '../api/auth';

// Mock authApi
vi.mock('../api/auth', () => ({
  authApi: {
    handleWithingsCallback: vi.fn(),
  },
}));

// Mock react-router-dom
const mockNavigate = vi.fn();
const mockSearchParams = new URLSearchParams();

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
    useSearchParams: () => [mockSearchParams],
  };
});

describe('WithingsCallbackPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    sessionStorage.clear();
    // Reset search params
    for (const key of Array.from(mockSearchParams.keys())) {
        mockSearchParams.delete(key);
    }
  });

  it('shows processing state initially', async () => {
    // Provide valid params so it doesn't immediately error
    mockSearchParams.set('code', 'test_code');
    mockSearchParams.set('state', 'test_state');
    
    // Return a pending promise to keep it in processing state
    (authApi.handleWithingsCallback as any).mockReturnValue(new Promise(() => {}));

    render(<WithingsCallbackPage />);
    expect(screen.getByText('Connecting to Withings...')).toBeInTheDocument();
  });

  it('handles successful callback', async () => {
    mockSearchParams.set('code', 'test_code');
    mockSearchParams.set('state', 'test_state');
    (authApi.handleWithingsCallback as any).mockResolvedValue({ message: 'success' });

    render(<WithingsCallbackPage />);

    await waitFor(() => {
      expect(authApi.handleWithingsCallback).toHaveBeenCalledWith('test_code', 'test_state');
      expect(mockNavigate).toHaveBeenCalledWith('/auth');
    });
  });

  it('handles missing params', async () => {
    mockSearchParams.delete('code');
    mockSearchParams.delete('state');

    render(<WithingsCallbackPage />);

    await waitFor(() => {
      expect(screen.getByText('Connection Failed')).toBeInTheDocument();
      // It waits 2000ms, so we might need to fast-forward timers or just wait
    });
  });

  it('handles error param', async () => {
    mockSearchParams.set('error', 'access_denied');

    render(<WithingsCallbackPage />);

    await waitFor(() => {
      expect(screen.getByText('Connection Failed')).toBeInTheDocument();
    });
  });

  it('handles API error', async () => {
    mockSearchParams.set('code', 'test_code');
    mockSearchParams.set('state', 'test_state');
    (authApi.handleWithingsCallback as any).mockRejectedValue(new Error('API Error'));

    render(<WithingsCallbackPage />);

    await waitFor(() => {
      expect(screen.getByText('Connection Failed')).toBeInTheDocument();
    });
  });
});
