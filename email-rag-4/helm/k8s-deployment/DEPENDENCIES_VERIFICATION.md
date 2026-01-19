# ✅ k8s-dependencies.yaml - Verification Report

## 🎯 Quick Answer: YES, it will work! ✅

The dependencies file is correctly configured and will work as expected with only ONE potential issue to check.

---

## ✅ What's Correct

### PostgreSQL ✅
- **Image**: `postgres:15-alpine` (matches docker-compose)
- **Port**: 5432 ✅
- **Service name**: `postgres` (matches connection strings)
- **Secrets**: Uses `postgres-secrets` ✅
- **Health checks**: Properly configured ✅
- **Resources**: Appropriate (512Mi-2Gi memory)
- **Storage**: 50Gi with RWO (ReadWriteOnce) ✅

### Redis ✅
- **Image**: `redis:7-alpine` (matches docker-compose)
- **Port**: 6379 ✅
- **Service name**: `redis` (matches connection strings)
- **Configuration**: AOF enabled, 512mb memory limit ✅
- **Health checks**: Properly configured ✅
- **Resources**: Appropriate (256Mi-512Mi memory)
- **Storage**: 10Gi with RWO ✅

### RabbitMQ ✅
- **Image**: `rabbitmq:3-management-alpine` (matches docker-compose)
- **Ports**: 5672 (AMQP), 15672 (Management UI) ✅
- **Service name**: `rabbitmq` (matches connection strings)
- **Secrets**: Uses `rabbitmq-secrets` ✅
- **Health checks**: Properly configured ✅
- **Resources**: Appropriate (512Mi-1Gi memory)
- **Storage**: 20Gi with RWO ✅

---

## ⚠️ ONE THING TO CHECK

### Storage Class: `nfs-csi`

**Lines to check**: 96, 184, 283

```yaml
storageClassName: "nfs-csi"  # Is this available in your cluster?
```

**Check if this storage class exists:**
```bash
kubectl get storageclass
```

### If `nfs-csi` doesn't exist:

**Option 1: Use default storage class**
```yaml
# Change lines 96, 184, 283 to:
storageClassName: ""  # Uses cluster default
```

**Option 2: Use specific storage class**
```bash
# Find available storage classes
kubectl get storageclass

# Update to one that exists, e.g.:
storageClassName: "standard"
# or
storageClassName: "local-path"
# or  
storageClassName: "hostpath"
```

---

## 📊 Resource Summary

| Service | Memory Request | Memory Limit | CPU Request | CPU Limit | Storage |
|---------|----------------|--------------|-------------|-----------|---------|
| PostgreSQL | 512Mi | 2Gi | 250m | 1000m | 50Gi |
| Redis | 256Mi | 512Mi | 100m | 500m | 10Gi |
| RabbitMQ | 512Mi | 1Gi | 250m | 1000m | 20Gi |
| **Total** | **1.25Gi** | **3.5Gi** | **600m** | **2.5 CPUs** | **80Gi** |

**Cluster Requirements:**
- Minimum: ~2Gi RAM, 1 CPU, 80Gi storage
- Recommended: 4Gi+ RAM, 2+ CPUs

---

## 🔍 How Dependencies Connect to Your App

### Connection Flow:
```
Backend → postgres:5432 (PostgreSQL)
Backend → redis:6379 (Redis)
Backend → rabbitmq:5672 (RabbitMQ)
Workers → postgres:5432 (PostgreSQL)
Workers → redis:6379 (Redis)
Workers → rabbitmq:5672 (RabbitMQ)
```

### Connection Strings in Secrets:
```yaml
# k8s-secrets.yaml
database-url: "postgresql+asyncpg://pstrag:PASSWORD@postgres:5432/pstrag_db"
                                                     ^^^^^^^^
                                                Service name matches!

redis-url: "redis://redis:6379/0"
                    ^^^^^
                Service name matches!

celery-broker-url: "amqp://pstrag:PASSWORD@rabbitmq:5672//"
                                            ^^^^^^^^
                                        Service name matches!
```

✅ All service names match! ✅

---

## 🚀 Deployment Order

The dependencies should be deployed **BEFORE** your application:

```bash
# 1. Deploy dependencies FIRST
kubectl apply -f k8s-pvcs.yaml        # Create PVCs (not used by dependencies)
kubectl apply -f k8s-dependencies.yaml

# 2. Wait for dependencies to be ready
kubectl wait --for=condition=ready pod -l app=postgres --timeout=300s
kubectl wait --for=condition=ready pod -l app=redis --timeout=300s
kubectl wait --for=condition=ready pod -l app=rabbitmq --timeout=300s

# 3. Then deploy application
helm install email-rag-backend ../common-helmchart -f k8s-values.yaml
helm install email-rag-celery ../common-helmchart -f k8s-values-celery-worker.yaml
helm install email-rag-frontend ../common-helmchart -f k8s-values-frontend.yaml
```

**The deploy-k8s.sh script already does this in the correct order!** ✅

---

## ✅ Verification Commands

### After deployment, verify:

```bash
# Check if pods are running
kubectl get pods -l 'app in (postgres,redis,rabbitmq)'

# Expected output:
# NAME          READY   STATUS    RESTARTS   AGE
# postgres-0    1/1     Running   0          2m
# redis-0       1/1     Running   0          2m
# rabbitmq-0    1/1     Running   0          2m

# Check services
kubectl get svc -l 'app in (postgres,redis,rabbitmq)'

# Expected output:
# NAME       TYPE        CLUSTER-IP      EXTERNAL-IP   PORT(S)              AGE
# postgres   ClusterIP   10.x.x.x        <none>        5432/TCP             2m
# redis      ClusterIP   10.x.x.x        <none>        6379/TCP             2m
# rabbitmq   ClusterIP   10.x.x.x        <none>        5672/TCP,15672/TCP   2m

# Check PVCs
kubectl get pvc

# Test PostgreSQL connection
kubectl exec -it postgres-0 -- psql -U pstrag -d pstrag_db -c "SELECT 1;"

# Test Redis connection
kubectl exec -it redis-0 -- redis-cli ping

# Test RabbitMQ
kubectl exec -it rabbitmq-0 -- rabbitmq-diagnostics ping
```

---

## 🐛 Common Issues & Solutions

### Issue 1: Storage Class Not Found
```
Error: storageclass.storage.k8s.io "nfs-csi" not found
```

**Solution:**
```bash
# Check available storage classes
kubectl get storageclass

# Update k8s-dependencies.yaml lines 96, 184, 283
# Change to available storage class or use default ("")
```

### Issue 2: Insufficient Resources
```
0/3 nodes are available: insufficient memory/cpu
```

**Solution:**
```bash
# Check node resources
kubectl describe nodes | grep -A 5 "Allocated resources"

# Reduce resource requests in k8s-dependencies.yaml
# Or add more nodes to cluster
```

### Issue 3: PVC Stuck in Pending
```
NAME                 STATUS    VOLUME   CAPACITY
postgres-data-0      Pending
```

**Solution:**
```bash
# Check PVC events
kubectl describe pvc postgres-data-postgres-0

# Usually caused by:
# - Storage class doesn't exist
# - No storage provisioner
# - Insufficient storage capacity
```

### Issue 4: Pods CrashLoopBackOff
```bash
# Check logs
kubectl logs postgres-0
kubectl logs redis-0
kubectl logs rabbitmq-0

# Check events
kubectl describe pod postgres-0
```

---

## 📝 Optional Modifications

### For Local Development (Reduce Resources):

```yaml
# PostgreSQL (line 84-90)
resources:
  requests:
    memory: "256Mi"   # Reduced from 512Mi
    cpu: "100m"       # Reduced from 250m
  limits:
    memory: "1Gi"     # Reduced from 2Gi
    cpu: "500m"       # Reduced from 1000m

# Redis (line 172-178)
resources:
  requests:
    memory: "128Mi"   # Reduced from 256Mi
    cpu: "50m"        # Reduced from 100m
  limits:
    memory: "256Mi"   # Reduced from 512Mi
    cpu: "250m"       # Reduced from 500m

# RabbitMQ (line 271-277)
resources:
  requests:
    memory: "256Mi"   # Reduced from 512Mi
    cpu: "100m"       # Reduced from 250m
  limits:
    memory: "512Mi"   # Reduced from 1Gi
    cpu: "500m"       # Reduced from 1000m
```

### For Smaller Storage:

```yaml
# PostgreSQL (line 98-99)
storage: 20Gi  # Reduced from 50Gi

# Redis (line 186-187)
storage: 5Gi   # Reduced from 10Gi

# RabbitMQ (line 285-286)
storage: 10Gi  # Reduced from 20Gi
```

---

## ✅ Final Verdict

### YES, k8s-dependencies.yaml will work! ✅

**Only action needed:**
1. ✅ Check storage class exists: `kubectl get storageclass`
2. ✅ Update `storageClassName` if needed (lines 96, 184, 283)

**Everything else is correct:**
- ✅ Service names match connection strings
- ✅ Ports are correct
- ✅ Images match docker-compose
- ✅ Secrets references are correct
- ✅ Health checks are configured
- ✅ Resources are appropriate
- ✅ StatefulSets with persistent storage

**Deploy with confidence!** 🚀

---

## 🚀 Quick Deploy Test

```bash
# 1. Check storage class
kubectl get storageclass
# If nfs-csi doesn't exist, update k8s-dependencies.yaml

# 2. Deploy secrets
kubectl apply -f k8s-secrets.yaml

# 3. Deploy dependencies
kubectl apply -f k8s-dependencies.yaml

# 4. Wait and verify
kubectl get pods -w -l 'app in (postgres,redis,rabbitmq)'
# Wait until all show 1/1 Running

# 5. Test connections
kubectl exec -it postgres-0 -- psql -U pstrag -d pstrag_db -c "SELECT 1;"
kubectl exec -it redis-0 -- redis-cli ping
kubectl exec -it rabbitmq-0 -- rabbitmqctl status

# ✅ If all work, you're good to deploy the application!
```

---

Need help with storage class or any issues? Let me know! 🚀
