# WebSocket API

## Connection

### Endpoint
```
ws://localhost:8000/api/v1/ws
```

### Authentication
Include JWT token in connection:

```javascript
const ws = new WebSocket('ws://localhost:8000/api/v1/ws?token=YOUR_JWT_TOKEN');
```

## Message Format

### Client to Server

All messages follow this format:

```json
{
  "type": "message_type",
  "data": {},
  "request_id": "unique_request_id"
}
```

### Server to Client

```json
{
  "type": "message_type",
  "data": {},
  "request_id": "unique_request_id",
  "timestamp": "2026-01-11T10:00:00Z"
}
```

## Message Types

### Subscribe to Updates

Subscribe to real-time updates for specific resources.

**Client Message:**
```json
{
  "type": "subscribe",
  "data": {
    "channels": ["uploads", "search_results", "system_status"]
  },
  "request_id": "req_1"
}
```

**Server Response:**
```json
{
  "type": "subscribed",
  "data": {
    "channels": ["uploads", "search_results", "system_status"]
  },
  "request_id": "req_1"
}
```

### Unsubscribe

**Client Message:**
```json
{
  "type": "unsubscribe",
  "data": {
    "channels": ["uploads"]
  },
  "request_id": "req_2"
}
```

### Upload Progress

Receive real-time upload processing updates.

**Server Message:**
```json
{
  "type": "upload_progress",
  "data": {
    "upload_id": "upload_123",
    "status": "processing",
    "progress": 45,
    "emails_processed": 4500,
    "total_emails": 10000,
    "current_operation": "indexing_emails"
  },
  "timestamp": "2026-01-11T10:00:00Z"
}
```

### Search Results Streaming

Stream search results as they're found.

**Client Message:**
```json
{
  "type": "stream_search",
  "data": {
    "query": "Find urgent emails",
    "limit": 50
  },
  "request_id": "search_1"
}
```

**Server Messages:**
```json
{
  "type": "search_result",
  "data": {
    "email_id": "email_123",
    "subject": "Urgent: Action Required",
    "score": 0.95
  },
  "request_id": "search_1"
}
```

```json
{
  "type": "search_complete",
  "data": {
    "total_results": 25,
    "processing_time_ms": 850
  },
  "request_id": "search_1"
}
```

### RAG Chat

Interactive chat with streaming responses.

**Client Message:**
```json
{
  "type": "chat_message",
  "data": {
    "message": "Summarize emails about the project",
    "conversation_id": "conv_123"
  },
  "request_id": "chat_1"
}
```

**Server Messages (Streaming):**
```json
{
  "type": "chat_response_chunk",
  "data": {
    "chunk": "Based on the project emails...",
    "conversation_id": "conv_123"
  },
  "request_id": "chat_1"
}
```

```json
{
  "type": "chat_response_complete",
  "data": {
    "conversation_id": "conv_123",
    "sources": [
      {
        "email_id": "email_1",
        "relevance": 0.92
      }
    ]
  },
  "request_id": "chat_1"
}
```

### System Notifications

**Server Message:**
```json
{
  "type": "system_notification",
  "data": {
    "level": "info",
    "message": "System maintenance scheduled for 2026-01-15",
    "action_required": false
  },
  "timestamp": "2026-01-11T10:00:00Z"
}
```

### Email Updates

Notification when new emails are indexed.

**Server Message:**
```json
{
  "type": "new_emails",
  "data": {
    "count": 150,
    "upload_id": "upload_123"
  },
  "timestamp": "2026-01-11T10:00:00Z"
}
```

### Heartbeat/Ping

**Client Message:**
```json
{
  "type": "ping",
  "request_id": "ping_1"
}
```

**Server Response:**
```json
{
  "type": "pong",
  "request_id": "ping_1",
  "timestamp": "2026-01-11T10:00:00Z"
}
```

## Error Messages

**Server Error:**
```json
{
  "type": "error",
  "data": {
    "error_code": "INVALID_REQUEST",
    "message": "Invalid message format",
    "details": {}
  },
  "request_id": "req_1",
  "timestamp": "2026-01-11T10:00:00Z"
}
```

## Connection Events

### Connection Established

```json
{
  "type": "connected",
  "data": {
    "session_id": "session_123",
    "user_id": "user_456"
  },
  "timestamp": "2026-01-11T10:00:00Z"
}
```

### Connection Closed

Server sends before closing:

```json
{
  "type": "disconnecting",
  "data": {
    "reason": "server_shutdown",
    "reconnect_delay_ms": 5000
  },
  "timestamp": "2026-01-11T10:00:00Z"
}
```

## Client Example

### JavaScript/TypeScript

```typescript
class EmailRAGWebSocket {
  private ws: WebSocket;
  private requestId = 0;

  connect(token: string) {
    this.ws = new WebSocket(`ws://localhost:8000/api/v1/ws?token=${token}`);

    this.ws.onopen = () => {
      console.log('Connected');
      this.subscribe(['uploads', 'search_results']);
    };

    this.ws.onmessage = (event) => {
      const message = JSON.parse(event.data);
      this.handleMessage(message);
    };

    this.ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    this.ws.onclose = () => {
      console.log('Disconnected');
      // Implement reconnection logic
    };
  }

  subscribe(channels: string[]) {
    this.send('subscribe', { channels });
  }

  searchStream(query: string) {
    this.send('stream_search', { query, limit: 50 });
  }

  send(type: string, data: any) {
    const message = {
      type,
      data,
      request_id: `req_${++this.requestId}`
    };
    this.ws.send(JSON.stringify(message));
  }

  handleMessage(message: any) {
    switch (message.type) {
      case 'upload_progress':
        console.log('Upload progress:', message.data);
        break;
      case 'search_result':
        console.log('Search result:', message.data);
        break;
      // Handle other message types
    }
  }
}
```

## Best Practices

1. **Heartbeat**: Send ping every 30 seconds to keep connection alive
2. **Reconnection**: Implement exponential backoff for reconnection
3. **Request IDs**: Use unique request IDs for tracking
4. **Error Handling**: Handle all error message types
5. **Cleanup**: Unsubscribe from channels when not needed
6. **Authentication**: Refresh JWT token before expiration

## Rate Limiting

- Maximum 100 messages per minute per connection
- Streaming responses don't count towards limit
- Server may throttle high-frequency clients
