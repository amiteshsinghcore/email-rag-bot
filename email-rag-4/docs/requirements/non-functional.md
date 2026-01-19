# Non-Functional Requirements

## NFR1: Performance

### NFR1.1 PST Processing Speed
| Metric | Target | Notes |
|--------|--------|-------|
| Processing rate | 10,000+ emails/minute | Including metadata extraction |
| 10GB PST (100K emails) | < 20 minutes | End-to-end processing |
| Embedding generation | 256 chunks/batch | Optimal batch size |

### NFR1.2 Query Response Time
| Query Type | Target (p95) | Notes |
|------------|--------------|-------|
| Simple lookup | < 2 seconds | Keyword-based search |
| Semantic search | < 3 seconds | Vector similarity |
| RAG chat response | < 5 seconds | First token, then streaming |
| Complex analytical | < 10 seconds | Aggregations, trends |

### NFR1.3 Database Performance
| Operation | Target (p95) | Notes |
|-----------|--------------|-------|
| Single email fetch | < 50ms | By ID |
| Paginated list (20 items) | < 100ms | With filtering |
| Full-text search | < 200ms | PostgreSQL tsvector |
| Vector search (top-10) | < 150ms | ChromaDB query |

### NFR1.4 Concurrent Users
- Support 50+ simultaneous users
- Support 100+ WebSocket connections
- No degradation up to 1000 req/minute

---

## NFR2: Scalability

### NFR2.1 Data Limits
| Resource | Minimum | Maximum |
|----------|---------|---------|
| PST file size | 1 MB | 50 GB |
| Emails per archive | 1 | 1,000,000+ |
| Concurrent PST uploads | 1 | 10 |
| Total storage | - | Limited by disk |

### NFR2.2 Horizontal Scaling
- Stateless API servers (can add more instances)
- Celery workers scale independently
- Database read replicas supported
- Vector database sharding supported

### NFR2.3 Database Partitioning
- Partition emails by year (for archives > 1M emails)
- Partition audit logs by month
- Archive old data to cold storage

---

## NFR3: Reliability

### NFR3.1 Availability
| Service | Target Uptime | Notes |
|---------|---------------|-------|
| API Server | 99.9% | ~8.7 hours downtime/year |
| WebSocket | 99.5% | Reconnection supported |
| Background Workers | 99.0% | Job retry on failure |

### NFR3.2 Data Durability
- PostgreSQL: WAL archiving enabled
- Daily automated backups
- Point-in-time recovery capability
- Backup verification tests

### NFR3.3 Fault Tolerance
- Resumable PST processing after crash
- Automatic retry with exponential backoff:
  - Initial delay: 1 second
  - Max delay: 5 minutes
  - Max retries: 5
- Graceful degradation when LLM unavailable

### NFR3.4 Recovery
| Scenario | RTO | RPO |
|----------|-----|-----|
| Server crash | 5 minutes | 0 (no data loss) |
| Database failure | 30 minutes | 1 hour |
| Full disaster | 4 hours | 24 hours |

---

## NFR4: Security

### NFR4.1 Authentication
- JWT-based authentication
- Access token expiry: 30 minutes
- Refresh token expiry: 7 days
- Password requirements:
  - Minimum 8 characters
  - At least one uppercase, lowercase, number
  - Bcrypt hashing with salt

### NFR4.2 Authorization (RBAC)
| Role | Permissions |
|------|-------------|
| Admin | Full access, user management, system config |
| Investigator | Upload PST, search, view forensics |
| Viewer | Search and view only, no uploads |

### NFR4.3 Data Protection
- HTTPS/TLS 1.3 for all communications
- Encryption at rest for sensitive data (AES-256)
- API keys stored encrypted
- No sensitive data in logs

### NFR4.4 Audit & Compliance
- All evidence access logged immutably
- User action audit trail
- Session tracking
- IP address logging
- GDPR-compliant data handling

### NFR4.5 Rate Limiting
| User Type | Limit | Window |
|-----------|-------|--------|
| Standard | 100 requests | 1 minute |
| Premium | 1000 requests | 1 minute |
| Unauthenticated | 10 requests | 1 minute |

---

## NFR5: Maintainability

### NFR5.1 Code Quality
- Test coverage: > 80% (unit + integration)
- Linting: Zero warnings (Ruff, ESLint)
- Type coverage: 100% (Python type hints, TypeScript)
- Documentation: All public APIs documented

### NFR5.2 Architecture
- Modular service architecture
- Clear separation of concerns
- Dependency injection
- Interface-based design for LLM providers

### NFR5.3 Logging
- Structured JSON logging (Loguru)
- Log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
- Correlation IDs for request tracing
- Log retention: 30 days

### NFR5.4 Monitoring
- Prometheus metrics endpoint
- Key metrics:
  - Request latency (p50, p95, p99)
  - Error rates
  - Queue depths
  - Database connection pool
- Grafana dashboards
- Alerting on anomalies

### NFR5.5 Deployment
- Docker containerization
- Docker Compose for development
- Health check endpoints
- Zero-downtime deployments

---

## NFR6: Usability

### NFR6.1 Learning Curve
- New user productive within 5 minutes
- No training required for basic operations
- Contextual help tooltips
- Getting started guide

### NFR6.2 Accessibility
- WCAG 2.1 AA compliance
- Keyboard navigation support
- Screen reader compatible
- Color contrast ratios met

### NFR6.3 Responsiveness
- Desktop: 1920x1080 and above
- Tablet: 768px and above
- Mobile: 375px and above (limited features)
- Touch-friendly UI elements

### NFR6.4 Error Handling
- User-friendly error messages
- Suggested actions for common errors
- Error recovery options
- No technical jargon in user-facing errors

### NFR6.5 Feedback
- Loading indicators for all async operations
- Progress bars for long operations
- Success/failure notifications
- Real-time status updates via WebSocket

---

## NFR7: Compatibility

### NFR7.1 Browser Support
| Browser | Minimum Version |
|---------|-----------------|
| Chrome | 90+ |
| Firefox | 88+ |
| Safari | 14+ |
| Edge | 90+ |

### NFR7.2 Platform Support
- Linux (Ubuntu 20.04+, Debian 11+)
- macOS (11+)
- Windows (10+ with WSL2, or native Docker)

### NFR7.3 Database Compatibility
- PostgreSQL 15+
- Redis 7+
- ChromaDB 0.4+

---

## NFR8: Internationalization (Future)

### NFR8.1 Language Support
- English (primary)
- UI text externalized for translation
- Date/time formatting locale-aware
- Email content in any language (UTF-8)

---

## Summary Table

| Category | Key Metric | Target |
|----------|------------|--------|
| Performance | 10GB PST processing | < 20 minutes |
| Performance | Query response | < 5 seconds |
| Scalability | Max PST size | 50 GB |
| Scalability | Concurrent users | 50+ |
| Reliability | API uptime | 99.9% |
| Security | Auth method | JWT + RBAC |
| Maintainability | Test coverage | > 80% |
| Usability | Learning curve | < 5 minutes |
