/**
 * Services Index
 *
 * Re-exports all services for convenient importing.
 */

export {
  default as api,
  tokenManager,
  authApi,
  usersApi,
  emailsApi,
  uploadApi,
  searchApi,
  ragApi,
  statsApi,
} from './api';

export {
  wsClient,
  connectWebSocket,
  disconnectWebSocket,
  subscribeToChannel,
  subscribeToTask,
  onMessage,
  onConnectionChange,
  type ConnectionState,
  type MessageType,
  type WebSocketMessage,
  type TaskUpdate,
} from './websocket';
