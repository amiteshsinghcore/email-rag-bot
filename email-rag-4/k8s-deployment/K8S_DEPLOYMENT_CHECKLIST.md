# Email RAG Bot - Kubernetes Deployment Checklist

## 📋 Pre-Deployment Checklist

### Environment Setup
- [ ] Kubernetes cluster is running and accessible
- [ ] kubectl is configured with correct context
- [ ] Helm 3 is installed
- [ ] Docker is installed and logged into registry
- [ ] Common-helmchart is available locally
- [ ] Storage class `nfs-csi` exists (or update to your class)
- [ ] Ingress controller is installed (nginx recommended)
- [ ] Namespace created (if using non-default)

### Docker Images
- [ ] Backend Dockerfile reviewed and tested locally
- [ ] Frontend Dockerfile reviewed and tested locally
- [ ] Backend image built: `amiteshhsingh/email-rag-backend:v1.0.0`
- [ ] Frontend image built: `amiteshhsingh/email-rag-frontend:v1.0.0`
- [ ] Images pushed to Docker Hub
- [ ] Docker Hub credentials configured (if private)
- [ ] Test image pull: `docker pull amiteshhsingh/email-rag-backend:v1.0.0`

### Configuration Files
- [ ] `k8s-secrets.yaml` created from example
- [ ] Database passwords generated (strong, random)
- [ ] Secret keys generated: `openssl rand -hex 32`
- [ ] JWT secret key generated
- [ ] LLM API keys added (OpenAI, Anthropic, etc.)
- [ ] Domain names updated in ingress configs
- [ ] CORS origins updated in backend values
- [ ] Image tags verified in all values files
- [ ] Node selectors reviewed
- [ ] Resource limits adjusted for your cluster

### Security Review
- [ ] Secrets not committed to git
- [ ] `.gitignore` includes `k8s-secrets.yaml`
- [ ] Plan for production secret management (Sealed Secrets/Vault)
- [ ] TLS certificates configured (cert-manager)
- [ ] Network policies defined (optional)
- [ ] Pod security contexts reviewed

## 🚀 Deployment Checklist

### Step 1: Deploy Dependencies
- [ ] Apply secrets: `kubectl apply -f k8s-secrets.yaml`
- [ ] Create PVCs: `kubectl apply -f k8s-pvcs.yaml`
- [ ] Deploy dependencies: `kubectl apply -f k8s-dependencies.yaml`
- [ ] Verify PostgreSQL is running
- [ ] Verify Redis is running
- [ ] Verify RabbitMQ is running
- [ ] Test database connection from pod
- [ ] Test Redis connection
- [ ] Access RabbitMQ management UI

### Step 2: Deploy Backend
- [ ] Run helm install for backend
- [ ] Wait for pods to be ready
- [ ] Check pod logs for errors
- [ ] Verify health endpoint responds
- [ ] Confirm database migrations ran (init container)
- [ ] Test API endpoints
- [ ] Check ingress configuration
- [ ] Verify backend accessible via ingress

### Step 3: Deploy Celery Workers
- [ ] Run helm install for celery workers
- [ ] Wait for pods to be ready
- [ ] Check worker logs
- [ ] Verify workers registered in RabbitMQ
- [ ] Test with a sample task (if possible)
- [ ] Confirm workers can access shared storage
- [ ] Verify KEDA ScaledObject created (if enabled)

### Step 4: Deploy Frontend
- [ ] Run helm install for frontend
- [ ] Wait for pods to be ready
- [ ] Check nginx logs
- [ ] Access frontend via port-forward
- [ ] Test frontend health endpoint
- [ ] Verify ingress configuration
- [ ] Test frontend accessible via domain
- [ ] Confirm frontend can reach backend API

## ✅ Post-Deployment Verification

### Functional Tests
- [ ] Frontend loads successfully
- [ ] User registration works
- [ ] User login works
- [ ] PST file upload interface loads
- [ ] Upload a small test PST file
- [ ] Verify processing task appears
- [ ] Check Celery worker processes the file
- [ ] Verify emails indexed in database
- [ ] Test chat/query functionality
- [ ] Verify search returns results
- [ ] Test attachment viewing
- [ ] Check WebSocket connection
- [ ] Test real-time updates

### Infrastructure Tests
- [ ] All pods are running
- [ ] All pods pass health checks
- [ ] HPA is created and monitoring
- [ ] Service endpoints are correct
- [ ] Ingress routes traffic correctly
- [ ] TLS certificates are valid
- [ ] DNS resolves correctly
- [ ] PVCs are bound and accessible
- [ ] Logs are accessible
- [ ] Metrics are being collected (if monitoring enabled)

### Performance Tests
- [ ] Check pod resource usage
- [ ] Verify database performance
- [ ] Test with larger PST files
- [ ] Monitor memory usage during processing
- [ ] Check Redis cache hit rate
- [ ] Verify autoscaling triggers work
- [ ] Test concurrent user sessions
- [ ] Load test API endpoints (optional)

### Security Tests
- [ ] Pods run as non-root user
- [ ] Read-only root filesystem where possible
- [ ] Network policies enforced (if configured)
- [ ] Secrets not exposed in logs
- [ ] API authentication works
- [ ] JWT tokens expire correctly
- [ ] CORS properly configured
- [ ] Rate limiting works (if enabled)

## 📊 Monitoring Setup

- [ ] Prometheus scraping configured (if using ServiceMonitor)
- [ ] Grafana dashboards created
- [ ] Alerting rules defined
- [ ] Log aggregation configured (ELK/Loki)
- [ ] Resource usage alerts set
- [ ] Pod failure alerts set
- [ ] Database connection alerts set
- [ ] Disk space alerts set
- [ ] Uptime monitoring configured

## 🔄 Operational Readiness

### Documentation
- [ ] Deployment guide reviewed
- [ ] Quick reference accessible to team
- [ ] Troubleshooting guide available
- [ ] Runbooks created for common issues
- [ ] Contact information documented
- [ ] Escalation procedures defined

### Backup & Recovery
- [ ] Database backup strategy defined
- [ ] Automated backup cronjob created
- [ ] PVC snapshot process documented
- [ ] Backup restoration tested
- [ ] Disaster recovery plan documented
- [ ] RTO/RPO defined

### Change Management
- [ ] Rollback procedure tested
- [ ] Blue-green deployment strategy (if applicable)
- [ ] Canary deployment process (if applicable)
- [ ] Change approval process defined
- [ ] Maintenance window scheduled
- [ ] Stakeholders notified

## 🎯 Production Readiness

### Before Go-Live
- [ ] All tests passed
- [ ] Performance acceptable
- [ ] Security reviewed
- [ ] Backups verified
- [ ] Monitoring active
- [ ] Documentation complete
- [ ] Team trained
- [ ] Support plan in place
- [ ] Rollback tested
- [ ] Stakeholders approve

### Day 1 Activities
- [ ] Monitor all metrics closely
- [ ] Check logs for errors
- [ ] Verify backups running
- [ ] Test user access
- [ ] Respond to any issues quickly
- [ ] Document any unexpected behavior
- [ ] Update documentation as needed

### Week 1 Activities
- [ ] Review resource usage trends
- [ ] Adjust autoscaling if needed
- [ ] Optimize pod counts
- [ ] Review logs for patterns
- [ ] Update alerts if too noisy
- [ ] Collect user feedback
- [ ] Plan optimizations

## 📝 Notes Section

Use this space to track issues, decisions, and customizations:

```
Date: ____________
Issue/Decision: _______________________________________________
Resolution: ___________________________________________________
```

```
Date: ____________
Issue/Decision: _______________________________________________
Resolution: ___________________________________________________
```

```
Date: ____________
Issue/Decision: _______________________________________________
Resolution: ___________________________________________________
```

## ✨ Completion

**Deployment Date:** _______________
**Deployed By:** _______________
**Version:** v1.0.0
**Status:** [ ] Success [ ] Partial [ ] Failed

**Sign-off:**
- Tech Lead: _______________
- DevOps: _______________
- Product Owner: _______________
