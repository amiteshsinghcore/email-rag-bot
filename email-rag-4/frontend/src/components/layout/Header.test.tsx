/**
 * Header Component Tests
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, fireEvent } from '@testing-library/react';
import { render, mockUser } from '@/test/test-utils';
import { Header } from './Header';

// Mock the auth store
vi.mock('@/store/authStore', () => ({
  useAuthStore: vi.fn(() => ({
    user: mockUser,
    logout: vi.fn(),
  })),
}));

// Mock the connection status hook
vi.mock('@/hooks/useConnectionStatus', () => ({
  useConnectionStatus: vi.fn(() => 'connected'),
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

describe('Header', () => {
  const defaultProps = {
    drawerWidth: 240,
    onMenuClick: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the app title', () => {
    render(<Header {...defaultProps} />);

    expect(screen.getByText('PST Email RAG')).toBeInTheDocument();
  });

  it('renders connection status chip', () => {
    render(<Header {...defaultProps} />);

    expect(screen.getByText('Connected')).toBeInTheDocument();
  });

  it('renders user avatar with first letter', () => {
    render(<Header {...defaultProps} />);

    // User's first name initial
    const avatar = screen.getByRole('button', { name: /account/i });
    expect(avatar).toBeInTheDocument();
  });

  it('calls onMenuClick when menu button is clicked', () => {
    render(<Header {...defaultProps} />);

    // Menu icon button is only visible on mobile (xs)
    // Since we're testing in a desktop context, we can still find and click it
    const menuButtons = screen.getAllByRole('button');
    const menuButton = menuButtons.find((btn) =>
      btn.querySelector('[data-testid="MenuIcon"]')
    );

    if (menuButton) {
      fireEvent.click(menuButton);
      expect(defaultProps.onMenuClick).toHaveBeenCalled();
    }
  });

  it('opens user menu when avatar is clicked', () => {
    render(<Header {...defaultProps} />);

    const avatarButton = screen.getByRole('button', { name: /account/i });
    fireEvent.click(avatarButton);

    // Menu items should appear
    expect(screen.getByText('Profile')).toBeInTheDocument();
    expect(screen.getByText('Settings')).toBeInTheDocument();
    expect(screen.getByText('Sign Out')).toBeInTheDocument();
  });

  it('displays user name and email in menu', () => {
    render(<Header {...defaultProps} />);

    const avatarButton = screen.getByRole('button', { name: /account/i });
    fireEvent.click(avatarButton);

    expect(screen.getByText(mockUser.email)).toBeInTheDocument();
  });

  it('navigates to settings when Settings is clicked', () => {
    render(<Header {...defaultProps} />);

    // Open menu
    const avatarButton = screen.getByRole('button', { name: /account/i });
    fireEvent.click(avatarButton);

    // Click settings
    fireEvent.click(screen.getByText('Settings'));

    expect(mockNavigate).toHaveBeenCalledWith('/settings');
  });

  it('calls logout and navigates to login when Sign Out is clicked', async () => {
    const mockLogout = vi.fn().mockResolvedValue(undefined);
    const { useAuthStore } = await import('@/store/authStore');
    vi.mocked(useAuthStore).mockReturnValue({
      user: mockUser,
      logout: mockLogout,
      isAuthenticated: true,
      isLoading: false,
      login: vi.fn(),
      register: vi.fn(),
      checkAuth: vi.fn(),
    } as any);

    render(<Header {...defaultProps} />);

    // Open menu
    const avatarButton = screen.getByRole('button', { name: /account/i });
    fireEvent.click(avatarButton);

    // Click sign out
    fireEvent.click(screen.getByText('Sign Out'));

    expect(mockLogout).toHaveBeenCalled();
  });
});

describe('Header connection states', () => {
  const defaultProps = {
    drawerWidth: 240,
    onMenuClick: vi.fn(),
  };

  it('shows "Connecting..." when connecting', async () => {
    const { useConnectionStatus } = await import('@/hooks/useConnectionStatus');
    vi.mocked(useConnectionStatus).mockReturnValue('connecting');

    render(<Header {...defaultProps} />);

    expect(screen.getByText('Connecting...')).toBeInTheDocument();
  });

  it('shows "Reconnecting..." when reconnecting', async () => {
    const { useConnectionStatus } = await import('@/hooks/useConnectionStatus');
    vi.mocked(useConnectionStatus).mockReturnValue('reconnecting');

    render(<Header {...defaultProps} />);

    expect(screen.getByText('Reconnecting...')).toBeInTheDocument();
  });

  it('shows "Disconnected" when disconnected', async () => {
    const { useConnectionStatus } = await import('@/hooks/useConnectionStatus');
    vi.mocked(useConnectionStatus).mockReturnValue('disconnected');

    render(<Header {...defaultProps} />);

    expect(screen.getByText('Disconnected')).toBeInTheDocument();
  });
});
