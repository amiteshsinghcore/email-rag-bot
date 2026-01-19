# Migration Guide: Docker Compose → Kubernetes

## Overview

This guide explains the differences between your current Docker Compose setup and the new Kubernetes deployment.

## Architecture Comparison

### Docker Compose (Current)

```yaml
frontend (1 container) → backend (1 container) → celery (1 container)
                              ↓
        postgres (1) | redis (1) | rabbitmq (1)
                              ↓
                  local volumes (bind mounts)
```

**Limitations:**
- ❌ Single host (no distribution)
- ❌ Manual scaling
- ❌ No self-healing
- ❌ Limited load balancing
- ❌ Local storage only

### Kubernetes (New)

```yaml
frontend (2-5 pods) → backend (2-6 pods) → celery (2-10 pods)
                              ↓
        postgres (1) | redis (1) | rabbitmq (1)
                              ↓
      distributed storage (PVCs with NFS)
```

**Advantages:**
- ✅ Multi-node distribution
- ✅ Automatic scaling (HPA/KEDA)
- ✅ Self-healing (auto-restart)
- ✅ Built-in load balancing
- ✅ Distributed storage (RWX)
- ✅ Rolling updates (zero downtime)
- ✅ Production-grade

## Service Mapping

### Frontend

**Docker Compose:**
```yaml
ports:
  - "80:80"
  - "443:443"
volumes:
  - ./nginx/nginx.prod.conf:/etc/nginx/nginx.conf
```

**Kubernetes:**
```yaml
# Uses Ingress instead of exposed ports
# Configuration baked into container image
# Multiple replicas with load balancing
```

**Migration Notes:**
- Nginx config must be in the image (already done in your Dockerfile)
- Access via Ingress instead of direct ports
- SSL/TLS handled by cert-manager + Ingress

### Backend

**Docker Compose:**
```yaml
environment:
  - DATABASE_URL=postgresql+asyncpg://...
  - REDIS_URL=redis://redis:6379/0
volumes:
  - upload_data:/app/uploads
  - chroma_data:/app/data/chroma
```

**Kubernetes:**
```yaml
# Environment from Secrets (more secure)
# Volumes from PVCs (distributed storage)
# Multiple replicas with shared storage
# Database migration via init container
```

**Migration Notes:**
- All secrets moved to Kubernetes Secrets
- Shared storage uses NFS (RWX) for multi-pod access
- ChromaDB data persisted in PVC

### Celery Workers

**Docker Compose:**
```yaml
command: celery -A app.workers.celery_app worker ...
environment:
  - same as backend
```

**Kubernetes:**
```yaml
# Separate deployment with different resources
# KEDA autoscaling based on queue depth
# Higher memory limits for PST processing
```

**Migration Notes:**
- Workers can scale independently from backend
- KEDA scales based on RabbitMQ queue length
- Shared storage with backend for PST files

### PostgreSQL

**Docker Compose:**
```yaml
image: postgres:15-alpine
volumes:
  - postgres_data:/var/lib/postgresql/data
```

**Kubernetes:**
```yaml
# StatefulSet with persistent storage
# ReadWriteOnce PVC (single pod)
# Health checks configured
```

**Migration Notes:**
- Data persists in PVC
- Can be migrated using pg_dump/restore
- Consider managed database for production (RDS, Cloud SQL)

### Redis

**Docker Compose:**
```yaml
command: redis-server --appendonly yes --maxmemory 256mb
volumes:
  - redis_data:/data
```

**Kubernetes:**
```yaml
# StatefulSet with persistent storage
# Same configuration
# Health checks added
```

**Migration Notes:**
- Data persists in PVC
- Consider Redis Cluster for HA
- Or use managed Redis (ElastiCache, Cloud Memorystore)

### RabbitMQ

**Docker Compose:**
```yaml
image: rabbitmq:3-management-alpine
volumes:
  - rabbitmq_data:/var/lib/rabbitmq
```

**Kubernetes:**
```yaml
# StatefulSet with persistent storage
# Management UI accessible via port-forward
# Health checks added
```

**Migration Notes:**
- Queue data persists in PVC
- Management UI: `kubectl port-forward svc/rabbitmq 15672:15672`
- Consider RabbitMQ cluster for HA

## Configuration Changes

### Environment Variables

**Docker Compose (.env file):**
```bash
POSTGRES_USER=pstrag
POSTGRES_PASSWORD=password123
OPENAI_API_KEY=sk-...
```

**Kubernetes (Secret):**
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: email-rag-secrets
stringData:
  postgres-password: password123
  openai-api-key: sk-...
```

**Migration:**
1. Copy values from `.env` to `k8s-secrets.yaml`
2. Generate new secret keys for production
3. Apply: `kubectl apply -f k8s-secrets.yaml`

### Storage

**Docker Compose (Named Volumes):**
```yaml
volumes:
  postgres_data:
  redis_data:
  rabbitmq_data:
  upload_data:
  chroma_data:
```

**Kubernetes (PVCs):**
```yaml
# Managed PVCs with storage class
# Can use NFS, Ceph, or cloud storage
# ReadWriteMany for shared access
```

**Migration:**
1. Data needs to be copied from Docker volumes to PVCs
2. Or start fresh (for non-critical data)
3. For PostgreSQL: use pg_dump → restore

### Networking

**Docker Compose:**
- Services communicate via service names on `email-rag-network`
- Ports exposed on host

**Kubernetes:**
- Services communicate via DNS (servicename.namespace.svc.cluster.local)
- Ingress for external access
- No host port binding needed

## Data Migration

### PostgreSQL Database

```bash
# 1. Export from Docker Compose
docker exec email-rag-postgres pg_dump -U pstrag pstrag_db > backup.sql

# 2. Wait for K8s PostgreSQL to be ready
kubectl wait --for=condition=ready pod -l app=postgres --timeout=300s

# 3. Import to Kubernetes
cat backup.sql | kubectl exec -i postgres-0 -- psql -U pstrag pstrag_db
```

### Upload Files

```bash
# 1. Find Docker volume location
docker volume inspect email-rag_upload_data

# 2. Copy to a temporary location
docker cp email-rag-backend:/app/uploads ./uploads-backup

# 3. Copy to Kubernetes pod (after deployment)
kubectl cp ./uploads-backup $(kubectl get pod -l app=email-rag,component=backend -o jsonpath='{.items[0].metadata.name}'):/app/uploads/
```

### ChromaDB Vector Data

```bash
# Similar to uploads
docker cp email-rag-backend:/app/data/chroma ./chroma-backup
kubectl cp ./chroma-backup $(kubectl get pod -l app=email-rag,component=backend -o jsonpath='{.items[0].metadata.name}'):/app/data/chroma/
```

## Deployment Process

### Step 1: Prepare

```bash
# 1. Build and push new images
docker build --platform linux/amd64 -t amiteshhsingh/email-rag-backend:v1.0.0 ./backend
docker build --platform linux/amd64 -t amiteshhsingh/email-rag-frontend:v1.0.0 ./frontend
docker push amiteshhsingh/email-rag-backend:v1.0.0
docker push amiteshhsingh/email-rag-frontend:v1.0.0

# 2. Configure secrets
cp k8s-secrets.example.yaml k8s-secrets.yaml
# Edit and update all values
```

### Step 2: Deploy to K8s

```bash
# Option 1: Use automated script
./deploy-k8s.sh

# Option 2: Manual deployment
kubectl apply -f k8s-secrets.yaml
kubectl apply -f k8s-pvcs.yaml
kubectl apply -f k8s-dependencies.yaml
helm install email-rag-backend ../common-helmchart -f k8s-values.yaml
helm install email-rag-celery ../common-helmchart -f k8s-values-celery-worker.yaml
helm install email-rag-frontend ../common-helmchart -f k8s-values-frontend.yaml
```

### Step 3: Migrate Data (if needed)

```bash
# Follow data migration steps above
```

### Step 4: Verify

```bash
# Check all pods running
kubectl get pods -l app=email-rag

# Test application
kubectl port-forward svc/email-rag-frontend 8080:80
open http://localhost:8080
```

### Step 5: Update DNS

```bash
# Get ingress IP
kubectl get ingress

# Update DNS to point to ingress IP
# email-rag.iamsaif.ai → <ingress-ip>
```

### Step 6: Stop Docker Compose (after verification)

```bash
# Only after K8s is verified working!
docker-compose -f docker-compose.prod.yml down
```

## Feature Comparison

| Feature | Docker Compose | Kubernetes |
|---------|---------------|------------|
| **Scaling** | Manual | Automatic (HPA) |
| **High Availability** | No | Yes (replicas) |
| **Self-healing** | No | Yes |
| **Load Balancing** | Manual | Built-in |
| **Rolling Updates** | Downtime | Zero-downtime |
| **Storage** | Local | Distributed |
| **Secrets** | .env file | Encrypted secrets |
| **Monitoring** | Basic | Full observability |
| **Resource Limits** | Host limits | Per-pod limits |
| **Health Checks** | Basic | Comprehensive |

## Cost Considerations

### Docker Compose
- Single server cost
- Manual scaling = waste or shortage
- Downtime during updates

### Kubernetes
- Multiple servers (but efficient)
- Autoscaling = cost optimization
- No downtime = better availability
- Potential cost savings with spot instances

## Rollback Plan

If you need to rollback to Docker Compose:

```bash
# 1. Export data from K8s (follow migration steps in reverse)

# 2. Update .env file with any new settings

# 3. Start Docker Compose
cd /Users/amiteshsingh/saif/26apps/Email-Rag
docker-compose -f docker-compose.prod.yml up -d

# 4. Restore data
docker exec -i email-rag-postgres psql -U pstrag pstrag_db < backup.sql
docker cp uploads-backup/. email-rag-backend:/app/uploads/
```

## Best Practices

### For Development
- Keep using Docker Compose locally
- Test K8s deployment in staging
- Use minikube/kind for local K8s testing

### For Production
- Use K8s for production (this deployment)
- Set up CI/CD pipeline
- Monitor everything
- Regular backups
- Disaster recovery plan

## Troubleshooting Common Issues

### Issue: Pods can't access shared storage

**Solution:** Ensure PVCs are using ReadWriteMany (RWX) access mode
```yaml
accessModes:
  - ReadWriteMany
```

### Issue: Database connection errors

**Solution:** Check if PostgreSQL is ready before backend starts
```bash
kubectl get pod -l app=postgres
kubectl logs postgres-0
```

### Issue: High memory usage

**Solution:** Adjust resource limits in values files
```yaml
resources:
  limits:
    memory: 4Gi  # Increase if needed
```

## Next Steps

1. ✅ Review this migration guide
2. ✅ Set up staging K8s environment
3. ✅ Test deployment in staging
4. ✅ Migrate data (if needed)
5. ✅ Deploy to production K8s
6. ✅ Monitor for 24-48 hours
7. ✅ Optimize based on metrics
8. ✅ Document any issues/solutions

## Resources

- **K8s Deployment Guide**: `KUBERNETES_DEPLOYMENT.md`
- **Quick Reference**: `K8S_QUICK_REFERENCE.md`
- **Checklist**: `K8S_DEPLOYMENT_CHECKLIST.md`
- **Summary**: `K8S_DEPLOYMENT_SUMMARY.md`

---

**Questions?** Refer to the troubleshooting section in `KUBERNETES_DEPLOYMENT.md`
