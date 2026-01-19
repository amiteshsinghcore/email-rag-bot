/**
 * WebSocket Client Service
 *
 * Manages WebSocket connection with automatic reconnection,
 * channel subscriptions, and message handling.
 */

import { tokenManager } from './api';

// WebSocket URL from environment or default (use API prefix so nginx proxy upgrades work)
const WS_BASE_URL = import.meta.env.VITE_WS_URL ||
  `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/api/v1/ws`;

// Connection states
export type ConnectionState = 'connecting' | 'connected' | 'disconnected' | 'reconnecting';

// Message types matching backend
export type MessageType =
  | 'connected'
  | 'disconnected'
  | 'error'
  | 'ping'
  | 'pong'
  | 'task_started'
  | 'task_progress'
  | 'task_completed'
  | 'task_failed'
  | 'task_cancelled'
  | 'rag_chunk'
  | 'rag_complete'
  | 'rag_error'
  | 'notification'
  | 'subscribe'
  | 'unsubscribe'
  | 'subscribed'
  | 'unsubscribed';

export interface WebSocketMessage {
  type: MessageType;
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

type MessageHandler = (message: WebSocketMessage) => void;
type ConnectionHandler = (state: ConnectionState) => void;

class WebSocketClient {
  private ws: WebSocket | null = null;
  private url: string;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 10;
  private reconnectDelay = 1000;
  private maxReconnectDelay = 30000;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private pingInterval: ReturnType<typeof setInterval> | null = null;
  private subscriptions: Set<string> = new Set();
  private messageHandlers: Map<string, Set<MessageHandler>> = new Map();
  private connectionHandlers: Set<ConnectionHandler> = new Set();
  private state: ConnectionState = 'disconnected';

  constructor() {
    this.url = WS_BASE_URL;
  }

  /**
   * Connect to WebSocket server.
   */
  connect(): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      return;
    }

    const token = tokenManager.getAccessToken();
    if (!token) {
      console.warn('WebSocket: No auth token available');
      return;
    }

    this.setState('connecting');

    // Add token to URL
    const wsUrl = `${this.url}?token=${encodeURIComponent(token)}`;
    console.log('WebSocket: Connecting to', wsUrl);
    this.ws = new WebSocket(wsUrl);

    this.ws.onopen = this.handleOpen.bind(this);
    this.ws.onclose = this.handleClose.bind(this);
    this.ws.onerror = this.handleError.bind(this);
    this.ws.onmessage = this.handleMessage.bind(this);
  }

  /**
   * Disconnect from WebSocket server.
   */
  disconnect(): void {
    this.stopReconnect();
    this.stopPing();

    if (this.ws) {
      this.ws.close(1000, 'Client disconnect');
      this.ws = null;
    }

    this.setState('disconnected');
    this.subscriptions.clear();
  }

  /**
   * Subscribe to a channel.
   */
  subscribe(channel: string): void {
    this.subscriptions.add(channel);

    if (this.isConnected()) {
      this.send({
        type: 'subscribe',
        data: { channel },
      });
    }
  }

  /**
   * Unsubscribe from a channel.
   */
  unsubscribe(channel: string): void {
    this.subscriptions.delete(channel);

    if (this.isConnected()) {
      this.send({
        type: 'unsubscribe',
        data: { channel },
      });
    }
  }

  /**
   * Send a message.
   */
  send(message: WebSocketMessage): void {
    if (!this.isConnected()) {
      console.warn('WebSocket: Cannot send message, not connected');
      return;
    }

    this.ws?.send(JSON.stringify(message));
  }

  /**
   * Add a message handler for a specific message type.
   */
  on(type: MessageType | '*', handler: MessageHandler): () => void {
    const key = type;
    if (!this.messageHandlers.has(key)) {
      this.messageHandlers.set(key, new Set());
    }
    this.messageHandlers.get(key)!.add(handler);

    // Return unsubscribe function
    return () => {
      this.messageHandlers.get(key)?.delete(handler);
    };
  }

  /**
   * Remove a message handler.
   */
  off(type: MessageType | '*', handler: MessageHandler): void {
    this.messageHandlers.get(type)?.delete(handler);
  }

  /**
   * Add a connection state handler.
   */
  onConnectionChange(handler: ConnectionHandler): () => void {
    this.connectionHandlers.add(handler);
    // Immediately call with current state
    handler(this.state);

    return () => {
      this.connectionHandlers.delete(handler);
    };
  }

  /**
   * Check if connected.
   */
  isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }

  /**
   * Get current connection state.
   */
  getState(): ConnectionState {
    return this.state;
  }

  /**
   * Subscribe to task updates.
   */
  subscribeToTask(taskId: string): () => void {
    const channel = `task:${taskId}`;
    this.subscribe(channel);
    return () => this.unsubscribe(channel);
  }

  /**
   * Subscribe to RAG session updates.
   */
  subscribeToRagSession(sessionId: string): () => void {
    const channel = `rag:${sessionId}`;
    this.subscribe(channel);
    return () => this.unsubscribe(channel);
  }

  // Private methods

  private handleOpen(): void {
    console.log('WebSocket: Connected');
    this.reconnectAttempts = 0;
    this.setState('connected');
    this.startPing();

    // Resubscribe to all channels
    for (const channel of this.subscriptions) {
      this.send({
        type: 'subscribe',
        data: { channel },
      });
    }
  }

  private handleClose(event: CloseEvent): void {
    console.log('WebSocket: Closed', event.code, event.reason);
    this.stopPing();

    if (event.code !== 1000) {
      // Abnormal close, attempt reconnect
      this.scheduleReconnect();
    } else {
      this.setState('disconnected');
    }
  }

  private handleError(event: Event): void {
    console.error('WebSocket: Error', event);
  }

  private handleMessage(event: MessageEvent): void {
    try {
      const message: WebSocketMessage = JSON.parse(event.data);

      // Handle pong silently
      if (message.type === 'pong') {
        return;
      }

      // Log for debugging
      console.log('WebSocket: Message', message.type, message);

      // Call type-specific handlers
      const typeHandlers = this.messageHandlers.get(message.type);
      if (typeHandlers) {
        for (const handler of typeHandlers) {
          try {
            handler(message);
          } catch (error) {
            console.error('WebSocket: Handler error', error);
          }
        }
      }

      // Call wildcard handlers
      const wildcardHandlers = this.messageHandlers.get('*');
      if (wildcardHandlers) {
        for (const handler of wildcardHandlers) {
          try {
            handler(message);
          } catch (error) {
            console.error('WebSocket: Handler error', error);
          }
        }
      }
    } catch (error) {
      console.error('WebSocket: Failed to parse message', error);
    }
  }

  private setState(state: ConnectionState): void {
    if (this.state !== state) {
      this.state = state;
      for (const handler of this.connectionHandlers) {
        try {
          handler(state);
        } catch (error) {
          console.error('WebSocket: Connection handler error', error);
        }
      }
    }
  }

  private scheduleReconnect(): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.log('WebSocket: Max reconnect attempts reached');
      this.setState('disconnected');
      return;
    }

    this.setState('reconnecting');
    this.reconnectAttempts++;

    // Exponential backoff with jitter
    const delay = Math.min(
      this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1) +
      Math.random() * 1000,
      this.maxReconnectDelay
    );

    console.log(
      `WebSocket: Reconnecting in ${Math.round(delay / 1000)}s (attempt ${this.reconnectAttempts})`
    );

    this.reconnectTimer = setTimeout(() => {
      this.connect();
    }, delay);
  }

  private stopReconnect(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.reconnectAttempts = 0;
  }

  private startPing(): void {
    // Send ping every 30 seconds to keep connection alive
    this.pingInterval = setInterval(() => {
      if (this.isConnected()) {
        this.send({ type: 'ping', data: {} });
      }
    }, 30000);
  }

  private stopPing(): void {
    if (this.pingInterval) {
      clearInterval(this.pingInterval);
      this.pingInterval = null;
    }
  }
}

// Create singleton instance
export const wsClient = new WebSocketClient();

// Export convenience functions
export function connectWebSocket(): void {
  wsClient.connect();
}

export function disconnectWebSocket(): void {
  wsClient.disconnect();
}

export function subscribeToChannel(channel: string): () => void {
  wsClient.subscribe(channel);
  return () => wsClient.unsubscribe(channel);
}

export function subscribeToTask(taskId: string): () => void {
  return wsClient.subscribeToTask(taskId);
}

export function onMessage(
  type: MessageType | '*',
  handler: MessageHandler
): () => void {
  return wsClient.on(type, handler);
}

export function onConnectionChange(handler: ConnectionHandler): () => void {
  return wsClient.onConnectionChange(handler);
}
