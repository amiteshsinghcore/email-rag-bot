/**
 * Test Utilities
 *
 * Custom render functions and utilities for testing React components.
 */

import { ReactElement, ReactNode } from 'react';
import { render, RenderOptions } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ThemeProvider, createTheme } from '@mui/material';

// Create a theme for tests
const theme = createTheme({
  palette: {
    mode: 'light',
    primary: {
      main: '#1976d2',
    },
    secondary: {
      main: '#dc004e',
    },
  },
});

// Create a fresh query client for each test
const createTestQueryClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
        staleTime: 0,
      },
      mutations: {
        retry: false,
      },
    },
  });

interface ProvidersProps {
  children: ReactNode;
}

/**
 * All providers wrapper for tests
 */
function AllProviders({ children }: ProvidersProps) {
  const queryClient = createTestQueryClient();

  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider theme={theme}>
        <BrowserRouter>{children}</BrowserRouter>
      </ThemeProvider>
    </QueryClientProvider>
  );
}

/**
 * Custom render that wraps component with all providers
 */
const customRender = (
  ui: ReactElement,
  options?: Omit<RenderOptions, 'wrapper'>
) => render(ui, { wrapper: AllProviders, ...options });

// Re-export everything from testing-library
export * from '@testing-library/react';
export { customRender as render };

// Mock data factories
export const mockUser = {
  id: 'user-123',
  email: 'test@example.com',
  username: 'testuser',
  role: 'investigator' as const,
  is_active: true,
  is_verified: true,
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
};

export const mockEmail = {
  id: 'email-123',
  subject: 'Test Email Subject',
  sender: 'sender@example.com',
  sender_name: 'Test Sender',
  recipients: ['recipient@example.com'],
  cc: [],
  bcc: [],
  date_sent: '2024-01-15T10:30:00Z',
  date_received: '2024-01-15T10:30:05Z',
  body_text: 'This is the email body content.',
  body_html: '<p>This is the email body content.</p>',
  has_attachments: false,
  attachment_count: 0,
  importance: 'normal' as const,
  is_read: false,
  conversation_id: 'conv-123',
  pst_file_id: 'pst-123',
  created_at: '2024-01-15T10:30:00Z',
};

export const mockPSTFile = {
  id: 'pst-123',
  filename: 'test_emails.pst',
  original_filename: 'test_emails.pst',
  file_size: 104857600, // 100 MB
  sha256_hash: 'abc123def456',
  status: 'completed' as const,
  email_count: 1000,
  attachment_count: 150,
  processed_at: '2024-01-15T11:00:00Z',
  error_message: null,
  user_id: 'user-123',
  created_at: '2024-01-15T10:00:00Z',
};

export const mockDashboardStats = {
  total_emails: 5000,
  total_pst_files: 5,
  total_attachments: 750,
  processing_tasks: 0,
  storage_used: 524288000, // 500 MB
};

export const mockAuditLog = {
  id: 'log-123',
  user_id: 'user-123',
  user_email: 'test@example.com',
  action: 'login',
  resource_type: 'user',
  resource_id: null,
  details: null,
  ip_address: '192.168.1.1',
  created_at: '2024-01-15T10:00:00Z',
};

export const mockTimelineEvent = {
  id: 'event-123',
  email_id: 'email-123',
  subject: 'Test Email',
  sender: 'sender@example.com',
  recipients: ['recipient@example.com'],
  date_sent: '2024-01-15T10:30:00Z',
  event_type: 'sent' as const,
};

// Test helpers
export const waitForLoadingToFinish = async () => {
  // Wait for any loading states to resolve
  await new Promise((resolve) => setTimeout(resolve, 0));
};

export const mockLocalStorage = () => {
  const store: Record<string, string> = {};
  return {
    getItem: (key: string) => store[key] || null,
    setItem: (key: string, value: string) => {
      store[key] = value;
    },
    removeItem: (key: string) => {
      delete store[key];
    },
    clear: () => {
      Object.keys(store).forEach((key) => delete store[key]);
    },
  };
};
