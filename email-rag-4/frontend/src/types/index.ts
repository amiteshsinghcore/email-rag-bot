/**
 * Type Definitions
 *
 * Shared TypeScript types for the application.
 */

// User types
export interface User {
  id: string;
  email: string;
  full_name: string;
  role: 'admin' | 'analyst' | 'viewer';
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

// Auth types
export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest {
  email: string;
  username: string;
  password: string;
  confirm_password: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

// Email types
export interface Email {
  id: string;
  subject: string;
  sender: string;
  sender_name: string | null;
  recipients: string[];
  cc: string[];
  bcc: string[];
  date_sent: string;
  date_received: string | null;
  body_text: string | null;
  body_html: string | null;
  has_attachments: boolean;
  attachment_count: number;
  importance: 'low' | 'normal' | 'high';
  is_read: boolean;
  conversation_id: string | null;
  pst_file_id: string;
  created_at: string;
}

export interface EmailSummary {
  id: string;
  subject: string;
  sender: string;
  sender_name: string | null;
  date_sent: string;
  preview: string;
  has_attachments: boolean;
  importance: 'low' | 'normal' | 'high';
}

export interface Attachment {
  id: string;
  email_id: string;
  filename: string;
  content_type: string;
  size: number;
  sha256_hash: string;
  created_at: string;
}

// PST File types
export interface PSTFile {
  id: string;
  filename: string;
  original_filename: string;
  file_size: number;
  sha256_hash?: string;
  status: 'pending' | 'uploading' | 'validating' | 'parsing' | 'extracting' | 'embedding' | 'indexing' | 'processing' | 'completed' | 'failed' | 'cancelled';
  progress?: number;
  current_phase?: string;
  email_count: number;
  emails_total?: number;
  attachment_count: number;
  processed_at: string | null;
  error_message: string | null;
  user_id?: string;
  created_at: string;
}

// Task types
export interface ProcessingTask {
  id: string;
  task_type: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  progress: number;
  message: string | null;
  result: Record<string, unknown> | null;
  error: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

// Search types
export interface SearchQuery {
  query: string;
  filters?: SearchFilters;
  page?: number;
  page_size?: number;
}

export interface SearchFilters {
  pst_file_ids?: string[];
  date_from?: string;
  date_to?: string;
  sender?: string;
  has_attachments?: boolean;
  importance?: ('low' | 'normal' | 'high')[];
}

export interface SearchResult {
  emails: EmailSummary[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  query_time_ms: number;
}

// RAG types
export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface ChatRequest {
  question: string;
  chat_history?: ChatMessage[];
  pst_file_ids?: string[];
  provider?: string;
  model?: string;
  stream?: boolean;
  top_k?: number;
  temperature?: number;
  max_tokens?: number;
  include_sources?: boolean;
}

export interface ChatResponse {
  answer: string;
  sources: Source[];
  query_type: string;
  processed_query: ProcessedQuery | null;
  model_used: string;
  provider_used: string;
  total_tokens: number;
}

export interface Source {
  email_id: string;
  subject: string;
  sender: string;
  date: string;
  relevance_score: number;
  snippet: string;
}

export interface ProcessedQuery {
  original_query: string;
  query_type: string;
  expanded_terms: string[];
  entities: Record<string, string[]>;
}

export interface LLMProvider {
  name: string;
  display_name: string;
  is_available: boolean;
  models: string[];
  default_model: string;
}

export interface LLMSettingsResponse {
  id: string;
  provider: string;
  user_id: string | null;
  api_key_set: boolean;
  api_key_preview: string | null;
  model: string | null;
  base_url: string | null;
  is_enabled: boolean;
  is_default: boolean;
  created_at: string | null;
  updated_at: string | null;
}

// WebSocket types
export interface WebSocketMessage {
  type: string;
  data: Record<string, unknown>;
  channel?: string;
  timestamp?: string;
}

export interface TaskUpdate {
  task_id: string;
  status: string;
  progress: number;
  message: string;
  details?: Record<string, unknown>;
}

// Pagination types
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

// API Error types
export interface APIError {
  detail: string | ErrorDetail;
  status_code?: number;
}

export interface ErrorDetail {
  error: string;
  error_type: string;
  field?: string;
}

// Stats types
export interface DashboardStats {
  total_emails: number;
  emails_with_attachments: number;
  total_pst_files: number;
  total_attachments: number;
  completed_tasks: number;
  processing_tasks: number;
  storage_used: number;
}

// Settings types
export interface UserSettings {
  default_provider: string;
  default_model: string;
  theme: 'light' | 'dark' | 'system';
  notifications_enabled: boolean;
}

// Forensic types
export interface AuditLogEntry {
  id: string;
  user_id: string;
  user_email: string;
  action: string;
  resource_type: string;
  resource_id: string | null;
  details: Record<string, unknown> | null;
  ip_address: string | null;
  created_at: string;
}

export interface EvidenceFile {
  id: string;
  pst_file_id: string;
  filename: string;
  sha256_hash: string;
  md5_hash: string;
  file_size: number;
  registered_at: string;
  registered_by: string;
  chain_of_custody: CustodyEntry[];
  is_verified: boolean;
}

export interface CustodyEntry {
  timestamp: string;
  action: string;
  user_id: string;
  user_email: string;
  notes: string | null;
}

export interface TimelineEvent {
  id: string;
  email_id: string;
  subject: string;
  sender: string;
  recipients: string[];
  date_sent: string;
  event_type: 'sent' | 'received' | 'replied' | 'forwarded';
}

export interface EmailAnalysis {
  email_id: string;
  headers: Record<string, string>;
  spf_result: string | null;
  dkim_result: string | null;
  dmarc_result: string | null;
  routing_path: string[];
  anomalies: string[];
}
