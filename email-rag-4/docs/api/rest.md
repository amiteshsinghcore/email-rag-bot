# REST API Endpoints

## Authentication

### POST /api/v1/auth/login
Login to the system.

**Request Body:**
```json
{
  "username": "user@example.com",
  "password": "password123"
}
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

### POST /api/v1/auth/register
Register a new user.

**Request Body:**
```json
{
  "username": "user@example.com",
  "password": "password123",
  "full_name": "John Doe"
}
```

### POST /api/v1/auth/refresh
Refresh access token.

## Email Endpoints

### GET /api/v1/emails
List emails with pagination.

**Query Parameters:**
- `skip`: Number of records to skip (default: 0)
- `limit`: Maximum records to return (default: 20)
- `from_date`: Filter by date (ISO format)
- `to_date`: Filter by date (ISO format)
- `sender`: Filter by sender email
- `recipient`: Filter by recipient email

**Response:**
```json
{
  "total": 1000,
  "items": [
    {
      "id": "email_123",
      "subject": "Project Update",
      "sender": "alice@example.com",
      "recipients": ["bob@example.com"],
      "date": "2026-01-10T10:30:00Z",
      "preview": "Here's the latest update...",
      "has_attachments": true
    }
  ],
  "skip": 0,
  "limit": 20
}
```

### GET /api/v1/emails/{email_id}
Get email details.

**Response:**
```json
{
  "id": "email_123",
  "subject": "Project Update",
  "sender": "alice@example.com",
  "recipients": ["bob@example.com"],
  "cc": [],
  "bcc": [],
  "date": "2026-01-10T10:30:00Z",
  "body": "Full email body content...",
  "html_body": "<html>...</html>",
  "attachments": [
    {
      "id": "att_1",
      "filename": "report.pdf",
      "size": 1024000,
      "content_type": "application/pdf"
    }
  ],
  "headers": {}
}
```

### GET /api/v1/emails/{email_id}/attachments/{attachment_id}
Download email attachment.

## Search Endpoints

### POST /api/v1/search/query
Search emails using natural language.

**Request Body:**
```json
{
  "query": "Find emails about project deadlines",
  "limit": 10,
  "filters": {
    "from_date": "2026-01-01",
    "to_date": "2026-01-31",
    "sender": "alice@example.com"
  }
}
```

**Response:**
```json
{
  "query": "Find emails about project deadlines",
  "results": [
    {
      "email_id": "email_123",
      "score": 0.95,
      "subject": "Q1 Project Deadlines",
      "snippet": "...important deadline approaching...",
      "date": "2026-01-10T10:30:00Z"
    }
  ],
  "total": 5,
  "processing_time_ms": 150
}
```

### POST /api/v1/search/advanced
Advanced search with multiple criteria.

**Request Body:**
```json
{
  "keywords": ["deadline", "urgent"],
  "sender": "alice@example.com",
  "date_range": {
    "start": "2026-01-01",
    "end": "2026-01-31"
  },
  "has_attachments": true,
  "boolean_operator": "AND"
}
```

### GET /api/v1/search/history
Get user's search history.

## Upload Endpoints

### POST /api/v1/upload/pst
Upload PST file for processing.

**Request:**
- Content-Type: multipart/form-data
- Field: file (PST file)

**Response:**
```json
{
  "upload_id": "upload_123",
  "filename": "emails.pst",
  "size": 104857600,
  "status": "queued",
  "created_at": "2026-01-11T10:00:00Z"
}
```

### GET /api/v1/upload/{upload_id}/status
Get upload processing status.

**Response:**
```json
{
  "upload_id": "upload_123",
  "status": "processing",
  "progress": 45,
  "emails_processed": 4500,
  "total_emails": 10000,
  "errors": []
}
```

### GET /api/v1/upload/list
List all uploads.

## RAG Endpoints

### POST /api/v1/rag/chat
Chat with RAG assistant.

**Request Body:**
```json
{
  "message": "Summarize emails from Alice last week",
  "conversation_id": "conv_123",
  "context_emails": ["email_1", "email_2"]
}
```

**Response:**
```json
{
  "response": "Based on the emails from Alice last week...",
  "sources": [
    {
      "email_id": "email_1",
      "subject": "Weekly Update",
      "relevance": 0.92
    }
  ],
  "conversation_id": "conv_123"
}
```

### POST /api/v1/rag/summarize
Summarize email thread.

**Request Body:**
```json
{
  "email_ids": ["email_1", "email_2", "email_3"]
}
```

## User Endpoints

### GET /api/v1/users/me
Get current user profile.

### PUT /api/v1/users/me
Update user profile.

### GET /api/v1/users/activity
Get user activity log.

## System Endpoints

### GET /api/v1/health
Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "database": "connected",
  "redis": "connected",
  "version": "1.0.0"
}
```

### GET /api/v1/stats
System statistics.

**Response:**
```json
{
  "total_emails": 100000,
  "total_users": 50,
  "total_uploads": 25,
  "storage_used_gb": 45.2
}
```

## Error Responses

All endpoints may return the following error format:

```json
{
  "detail": "Error message",
  "error_code": "VALIDATION_ERROR",
  "timestamp": "2026-01-11T10:00:00Z"
}
```

### HTTP Status Codes
- `200`: Success
- `201`: Created
- `400`: Bad Request
- `401`: Unauthorized
- `403`: Forbidden
- `404`: Not Found
- `422`: Validation Error
- `500`: Internal Server Error

## Rate Limiting

### Limits by User Type

| User Type | Requests/Minute | Burst Limit | Notes |
|-----------|-----------------|-------------|-------|
| Unauthenticated | 10 | 5 | Very limited |
| Standard (Viewer) | 100 | 20 | Normal usage |
| Investigator | 500 | 50 | Heavy search usage |
| Admin | 1000 | 100 | Management tasks |

### Rate Limit Headers

All responses include rate limit information:
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1704931200
```

### Rate Limit Exceeded Response

```json
{
  "detail": "Rate limit exceeded",
  "error_code": "RATE_LIMIT_EXCEEDED",
  "retry_after": 45,
  "timestamp": "2026-01-11T10:00:00Z"
}
```
HTTP Status: `429 Too Many Requests`

---

## Error Handling Patterns

### Standard Error Response Format

```json
{
  "detail": "Human-readable error message",
  "error_code": "MACHINE_READABLE_CODE",
  "timestamp": "2026-01-11T10:00:00Z",
  "request_id": "req_abc123",
  "errors": [
    {
      "field": "email",
      "message": "Invalid email format"
    }
  ]
}
```

### Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `VALIDATION_ERROR` | 422 | Request body validation failed |
| `AUTHENTICATION_REQUIRED` | 401 | No valid JWT token provided |
| `PERMISSION_DENIED` | 403 | User lacks required role |
| `RESOURCE_NOT_FOUND` | 404 | Requested resource doesn't exist |
| `RATE_LIMIT_EXCEEDED` | 429 | Too many requests |
| `FILE_TOO_LARGE` | 413 | PST file exceeds 50GB limit |
| `INVALID_FILE_FORMAT` | 400 | File is not a valid PST |
| `PROCESSING_FAILED` | 500 | PST processing error |
| `LLM_UNAVAILABLE` | 503 | LLM provider not responding |
| `DATABASE_ERROR` | 500 | Database operation failed |

### Retry Strategy

For transient errors (5xx), clients should implement exponential backoff:
- Initial delay: 1 second
- Multiplier: 2x
- Max delay: 60 seconds
- Max retries: 5

---

## Pagination

List endpoints support pagination:
- `skip`: Offset (default: 0)
- `limit`: Page size (default: 20, max: 100)
- Response includes `total` count

### Pagination Response Format

```json
{
  "items": [...],
  "total": 1000,
  "skip": 0,
  "limit": 20,
  "has_more": true
}
```
