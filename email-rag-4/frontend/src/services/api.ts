/**
 * API Client Service
 *
 * Axios-based HTTP client with interceptors for authentication,
 * error handling, and request/response transformation.
 */

import axios, {
  AxiosInstance,
  AxiosError,
  InternalAxiosRequestConfig,
  AxiosResponse,
} from 'axios';
import toast from 'react-hot-toast';
import type {
  TokenResponse,
  LoginRequest,
  RegisterRequest,
  User,
  Email,
  EmailSummary,
  PSTFile,
  ProcessingTask,
  SearchResult,
  SearchQuery,
  ChatRequest,
  ChatResponse,
  LLMProvider,
  LLMSettingsResponse,
  Attachment,
  DashboardStats,
  PaginatedResponse,
  AuditLogEntry,
  EvidenceFile,
  TimelineEvent,
  EmailAnalysis,
} from '@/types';

// API base URL from environment or default
const API_BASE_URL = import.meta.env.VITE_API_URL || '/api/v1';

// Token storage keys
const ACCESS_TOKEN_KEY = 'access_token';
const REFRESH_TOKEN_KEY = 'refresh_token';

// Token management
export const tokenManager = {
  getAccessToken: (): string | null => localStorage.getItem(ACCESS_TOKEN_KEY),
  getRefreshToken: (): string | null => localStorage.getItem(REFRESH_TOKEN_KEY),

  setTokens: (accessToken: string, refreshToken: string): void => {
    localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
    localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
  },

  clearTokens: (): void => {
    localStorage.removeItem(ACCESS_TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
  },

  hasTokens: (): boolean => {
    return !!localStorage.getItem(ACCESS_TOKEN_KEY);
  },
};

// Create axios instance
const api: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Flag to prevent multiple refresh attempts
let isRefreshing = false;
let failedQueue: Array<{
  resolve: (value?: unknown) => void;
  reject: (reason?: unknown) => void;
}> = [];

const processQueue = (error: unknown, token: string | null = null): void => {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error);
    } else {
      prom.resolve(token);
    }
  });
  failedQueue = [];
};

// Request interceptor - add auth token
api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = tokenManager.getAccessToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error: AxiosError) => {
    return Promise.reject(error);
  }
);

// Response interceptor - handle errors and token refresh
api.interceptors.response.use(
  (response: AxiosResponse) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & {
      _retry?: boolean;
    };

    // Handle 401 errors (unauthorized)
    if (error.response?.status === 401 && !originalRequest._retry) {
      if (isRefreshing) {
        // Wait for the refresh to complete
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        })
          .then((token) => {
            originalRequest.headers.Authorization = `Bearer ${token}`;
            return api(originalRequest);
          })
          .catch((err) => Promise.reject(err));
      }

      originalRequest._retry = true;
      isRefreshing = true;

      const refreshToken = tokenManager.getRefreshToken();
      if (!refreshToken) {
        tokenManager.clearTokens();
        window.location.href = '/login';
        return Promise.reject(error);
      }

      try {
        const response = await axios.post<TokenResponse>(
          `${API_BASE_URL}/auth/refresh`,
          { refresh_token: refreshToken }
        );

        const { access_token, refresh_token } = response.data;
        tokenManager.setTokens(access_token, refresh_token);

        processQueue(null, access_token);
        originalRequest.headers.Authorization = `Bearer ${access_token}`;
        return api(originalRequest);
      } catch (refreshError) {
        processQueue(refreshError, null);
        tokenManager.clearTokens();
        window.location.href = '/login';
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }

    // Handle other errors
    const message = getErrorMessage(error);
    if (error.response?.status !== 401) {
      toast.error(message);
    }

    return Promise.reject(error);
  }
);

// Extract error message from response
function getErrorMessage(error: AxiosError): string {
  if (error.response?.data) {
    const data = error.response.data as Record<string, unknown>;
    if (typeof data.detail === 'string') {
      return data.detail;
    }
    if (typeof data.detail === 'object' && data.detail !== null) {
      const detail = data.detail as { error?: string; message?: string };
      return detail.error || detail.message || 'An error occurred';
    }
    if (typeof data.message === 'string') {
      return data.message;
    }
  }
  return error.message || 'An unexpected error occurred';
}

// ============================================================
// Auth API
// ============================================================

export const authApi = {
  login: async (data: LoginRequest): Promise<{ user: User; tokens: TokenResponse }> => {
    const response = await api.post<{ user: User; tokens: TokenResponse }>('/auth/login', data);
    tokenManager.setTokens(response.data.tokens.access_token, response.data.tokens.refresh_token);
    return response.data;
  },

  register: async (data: RegisterRequest): Promise<User> => {
    const response = await api.post<User>('/auth/register', data);
    return response.data;
  },

  logout: async (): Promise<void> => {
    try {
      await api.post('/auth/logout');
    } finally {
      tokenManager.clearTokens();
    }
  },

  refreshToken: async (): Promise<TokenResponse> => {
    const refreshToken = tokenManager.getRefreshToken();
    const response = await api.post<TokenResponse>('/auth/refresh', {
      refresh_token: refreshToken,
    });
    tokenManager.setTokens(response.data.access_token, response.data.refresh_token);
    return response.data;
  },

  getCurrentUser: async (): Promise<User> => {
    const response = await api.get<User>('/auth/me');
    return response.data;
  },
};

// ============================================================
// Users API
// ============================================================

export const usersApi = {
  getUsers: async (
    page = 1,
    pageSize = 20
  ): Promise<PaginatedResponse<User>> => {
    const response = await api.get<PaginatedResponse<User>>('/users', {
      params: { page, page_size: pageSize },
    });
    return response.data;
  },

  getUser: async (id: string): Promise<User> => {
    const response = await api.get<User>(`/users/${id}`);
    return response.data;
  },

  updateUser: async (id: string, data: Partial<User>): Promise<User> => {
    const response = await api.patch<User>(`/users/${id}`, data);
    return response.data;
  },

  deleteUser: async (id: string): Promise<void> => {
    await api.delete(`/users/${id}`);
  },
};

// ============================================================
// Emails API
// ============================================================

export const emailsApi = {
  getEmails: async (
    page = 1,
    pageSize = 20,
    filters?: Record<string, unknown>
  ): Promise<PaginatedResponse<EmailSummary>> => {
    const response = await api.get<PaginatedResponse<EmailSummary>>('/emails', {
      params: { page, page_size: pageSize, ...filters },
    });
    return response.data;
  },

  getEmail: async (id: string): Promise<Email> => {
    const response = await api.get<Email>(`/emails/${id}`);
    return response.data;
  },

  getEmailAttachments: async (id: string): Promise<Attachment[]> => {
    const response = await api.get<Attachment[]>(`/emails/${id}/attachments`);
    return response.data;
  },

  downloadAttachment: async (
    emailId: string,
    attachmentId: string
  ): Promise<Blob> => {
    const response = await api.get(
      `/emails/${emailId}/attachments/${attachmentId}/download`,
      { responseType: 'blob' }
    );
    return response.data;
  },

  getThread: async (conversationId: string): Promise<EmailSummary[]> => {
    const response = await api.get<EmailSummary[]>(
      `/emails/thread/${conversationId}`
    );
    return response.data;
  },
};

// ============================================================
// Upload API
// ============================================================

export const uploadApi = {
  uploadPSTFile: async (
    file: File,
    onProgress?: (progress: number) => void
  ): Promise<{ task_id: string; pst_file_id: string }> => {
    const formData = new FormData();
    formData.append('file', file);

    const response = await api.post<{ task_id: string; pst_file_id: string }>(
      '/upload',
      formData,
      {
        timeout: -1,
        headers: { 'Content-Type': 'multipart/form-data' },
        onUploadProgress: (progressEvent) => {
          if (onProgress && progressEvent.total) {
            const progress = Math.round(
              (progressEvent.loaded * 100) / progressEvent.total
            );
            onProgress(progress);
          }
        },
      }
    );
    return response.data;
  },

  getPSTFiles: async (): Promise<PSTFile[]> => {
    const response = await api.get<PSTFile[]>('/upload/files');
    return response.data;
  },

  getPSTFile: async (id: string): Promise<PSTFile> => {
    const response = await api.get<PSTFile>(`/upload/files/${id}`);
    return response.data;
  },

  deletePSTFile: async (id: string): Promise<void> => {
    await api.delete(`/upload/files/${id}`);
  },

  getTaskStatus: async (taskId: string): Promise<ProcessingTask> => {
    const response = await api.get<ProcessingTask>(`/upload/tasks/${taskId}`);
    return response.data;
  },

  cancelTask: async (taskId: string): Promise<void> => {
    await api.post(`/upload/tasks/${taskId}/cancel`);
  },

  initChunkUpload: async (
    filename: string,
    totalSize: number,
    totalChunks: number
  ): Promise<{ upload_id: string; chunk_size: number }> => {
    const response = await api.post('/upload/chunk/init', {
      filename,
      total_size: totalSize,
      total_chunks: totalChunks,
    });
    return response.data;
  },

  uploadChunk: async (
    uploadId: string,
    chunkIndex: number,
    chunk: Blob,
    onProgress?: (progress: number) => void
  ): Promise<void> => {
    const formData = new FormData();
    formData.append('file', chunk);

    await api.post(`/upload/chunk/${uploadId}`, formData, {
      params: { chunk_index: chunkIndex },
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (progressEvent) => {
        if (onProgress && progressEvent.total) {
          // This is progress for the single chunk, not total
          const progress = Math.round(
            (progressEvent.loaded * 100) / progressEvent.total
          );
          onProgress(progress);
        }
      },
    });
  },

  completeChunkUpload: async (
    uploadId: string,
    filename: string
  ): Promise<{ task_id: string; pst_file_id: string }> => {
    const response = await api.post<{ task_id: string; pst_file_id: string }>(
      `/upload/chunk/${uploadId}/complete`,
      null,
      { params: { filename } }
    );
    return response.data;
  },
};

// ============================================================
// Search API
// ============================================================

// Backend search response type (different from frontend SearchResult)
interface BackendSearchResult {
  results: Array<{
    email_id: string;
    subject: string;
    sender_email: string;
    sender_name: string | null;
    sent_date: string;
    snippet: string;
    score: number;
    match_type: string;
    highlights: string[];
    has_attachments: boolean;
    attachment_count: number;
    folder_path: string;
    pst_file_id: string;
  }>;
  total_count: number;
  query: string;
  processed_query: Record<string, unknown> | null;
  search_time_ms: number;
  page: number;
  page_size: number;
  has_more: boolean;
}

// Transform backend response to frontend SearchResult type
function transformSearchResult(data: BackendSearchResult): SearchResult {
  return {
    emails: data.results.map((r) => ({
      id: r.email_id,
      subject: r.subject,
      sender: r.sender_email,
      sender_name: r.sender_name,
      date_sent: r.sent_date,
      preview: r.snippet,
      has_attachments: r.has_attachments,
      importance: 'normal' as const, // Default, not provided by backend
    })),
    total: data.total_count,
    page: data.page,
    page_size: data.page_size,
    total_pages: Math.ceil(data.total_count / data.page_size),
    query_time_ms: data.search_time_ms,
  };
}

export const searchApi = {
  search: async (query: SearchQuery): Promise<SearchResult> => {
    const response = await api.post<BackendSearchResult>('/search', query);
    return transformSearchResult(response.data);
  },

  advancedSearch: async (query: SearchQuery): Promise<SearchResult> => {
    const response = await api.post<BackendSearchResult>('/search/advanced', query);
    return transformSearchResult(response.data);
  },

  getSearchHistory: async (): Promise<string[]> => {
    const response = await api.get<string[]>('/search/history');
    return response.data;
  },

  clearSearchHistory: async (): Promise<void> => {
    await api.delete('/search/history');
  },
};

// ============================================================
// RAG API
// ============================================================

export const ragApi = {
  chat: async (request: ChatRequest): Promise<ChatResponse> => {
    const response = await api.post<ChatResponse>('/rag/chat', request);
    return response.data;
  },

  chatStream: async function* (
    request: ChatRequest
  ): AsyncGenerator<string, void, unknown> {
    const response = await fetch(`${API_BASE_URL}/rag/chat/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${tokenManager.getAccessToken()}`,
      },
      body: JSON.stringify({ ...request, stream: true }),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const reader = response.body?.getReader();
    if (!reader) {
      throw new Error('No response body');
    }

    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = line.slice(6);
          try {
            const parsed = JSON.parse(data);
            if (parsed.event === 'chunk' && parsed.data?.content) {
              yield parsed.data.content;
            } else if (parsed.event === 'error') {
              throw new Error(parsed.data?.error || 'Stream error');
            }
          } catch {
            // Ignore parse errors for non-JSON data
          }
        }
      }
    }
  },

  getProviders: async (): Promise<{
    providers: LLMProvider[];
    default_provider: string;
  }> => {
    const response = await api.get<{
      providers: LLMProvider[];
      default_provider: string;
    }>('/rag/providers');
    return response.data;
  },

  healthCheck: async (): Promise<{
    status: string;
    components: Record<string, { status: string; error?: string }>;
  }> => {
    const response = await api.get('/rag/health');
    return response.data;
  },

  testApiKey: async (request: {
    provider: string;
    api_key: string;
    model?: string;
    base_url?: string;
  }): Promise<{
    success: boolean;
    provider: string;
    model: string | null;
    message: string;
    error: string | null;
  }> => {
    const response = await api.post('/rag/test-api-key', request);
    return response.data;
  },

  // LLM Settings endpoints
  getLLMSettings: async (): Promise<{
    settings: LLMSettingsResponse[];
    default_provider: string | null;
  }> => {
    const response = await api.get('/rag/settings');
    return response.data;
  },

  createOrUpdateLLMSettings: async (request: {
    provider: string;
    api_key?: string;
    model?: string;
    base_url?: string;
    is_enabled?: boolean;
    is_default?: boolean;
  }): Promise<LLMSettingsResponse> => {
    const response = await api.post('/rag/settings', request);
    return response.data;
  },

  updateLLMSettings: async (
    settingsId: string,
    request: {
      api_key?: string;
      model?: string;
      base_url?: string;
      is_enabled?: boolean;
      is_default?: boolean;
    }
  ): Promise<LLMSettingsResponse> => {
    const response = await api.put(`/rag/settings/${settingsId}`, request);
    return response.data;
  },

  deleteLLMSettings: async (settingsId: string): Promise<void> => {
    await api.delete(`/rag/settings/${settingsId}`);
  },

  setDefaultProvider: async (provider: string): Promise<{ message: string }> => {
    const response = await api.post(`/rag/settings/${provider}/set-default`);
    return response.data;
  },
};

// ============================================================
// Stats API
// ============================================================

export const statsApi = {
  getDashboardStats: async (): Promise<DashboardStats> => {
    const response = await api.get<DashboardStats>('/stats/dashboard');
    return response.data;
  },
};

// ============================================================
// Forensic API
// ============================================================

export const forensicApi = {
  getAuditLogs: async (
    page = 1,
    pageSize = 50,
    filters?: { action?: string; resource_type?: string; user_id?: string }
  ): Promise<PaginatedResponse<AuditLogEntry>> => {
    const response = await api.get<PaginatedResponse<AuditLogEntry>>('/forensic/audit-logs', {
      params: { page, page_size: pageSize, ...filters },
    });
    return response.data;
  },

  getEvidence: async (): Promise<EvidenceFile[]> => {
    const response = await api.get<EvidenceFile[]>('/forensic/evidence');
    return response.data;
  },

  verifyEvidence: async (id: string): Promise<{ is_valid: boolean; message: string }> => {
    const response = await api.post<{ is_valid: boolean; message: string }>(
      `/forensic/evidence/${id}/verify`
    );
    return response.data;
  },

  getTimeline: async (
    pstFileIds?: string[],
    dateFrom?: string,
    dateTo?: string
  ): Promise<TimelineEvent[]> => {
    const response = await api.get<TimelineEvent[]>('/forensic/timeline', {
      params: { pst_file_ids: pstFileIds?.join(','), date_from: dateFrom, date_to: dateTo },
    });
    return response.data;
  },

  analyzeEmail: async (emailId: string): Promise<EmailAnalysis> => {
    const response = await api.get<EmailAnalysis>(`/forensic/analyze/${emailId}`);
    return response.data;
  },
};

// Export the axios instance for custom requests
export default api;
