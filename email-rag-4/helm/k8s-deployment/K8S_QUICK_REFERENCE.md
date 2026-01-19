# Email RAG Bot - Quick Reference

## 🚀 Quick Deploy Commands

```bash
# 1. Build and push images (with platform flag for AMD64 compatibility)
docker build --platform linux/amd64 -t amiteshhsingh/email-rag-backend:v1.0.0 ./backend
docker build --platform linux/amd64 -t amiteshhsingh/email-rag-frontend:v1.0.0 ./frontend
docker push amiteshhsingh/email-rag-backend:v1.0.0
docker push amiteshhsingh/email-rag-frontend:v1.0.0

# 2. Create secrets (update with your values first!)
kubectl apply -f k8s-secrets.yaml

kubectl apply -f k8s-dependencies.yaml

# Wait for dependencies
kubectl wait --for=condition=ready pod -l app=postgres --timeout=300s
kubectl wait --for=condition=ready pod -l app=redis --timeout=300s
kubectl wait --for=condition=ready pod -l app=rabbitmq --timeout=300s

# Deploy backend
helm install email-rag-backend ../common-helmchart -f k8s-values.yaml

# Deploy workers
helm install email-rag-celery ../common-helmchart -f k8s-values-celery-worker.yaml

# Deploy frontend
helm install email-rag-frontend ../common-helmchart -f k8s-values-frontend.yaml
```

## 📊 Monitoring Commands

```bash
# Check all pods
kubectl get pods -l app=email-rag

# Check services
kubectl get svc -l app=email-rag

# Check ingress
kubectl get ingress

# View logs
kubectl logs -l app=email-rag,component=backend --tail=50 -f
kubectl logs -l app=email-rag,component=celery-worker --tail=50 -f
kubectl logs -l app=email-rag,component=frontend --tail=50 -f

# Check pod resources
kubectl top pods -l app=email-rag

# Check HPA status
kubectl get hpa
```

## 🔄 Update Commands

```bash
# Update backend
helm upgrade email-rag-backend ../common-helmchart -f k8s-values.yaml

# Update workers
helm upgrade email-rag-celery ../common-helmchart -f k8s-values-celery-worker.yaml

# Update frontend
helm upgrade email-rag-frontend ../common-helmchart -f k8s-values-frontend.yaml

# Rollback if needed
helm rollback email-rag-backend 0
```

## 🧪 Testing Commands

```bash
# Port-forward for local testing
kubectl port-forward svc/email-rag-backend 8000:8000 &
kubectl port-forward svc/email-rag-frontend 8080:80 &
kubectl port-forward svc/rabbitmq 15672:15672 &

# Test backend health
curl http://localhost:8000/health

# Test frontend
open http://localhost:8080

# Test RabbitMQ UI
open http://localhost:15672  # user: pstrag, pass: from secrets
```

## 🛠 Debugging Commands

```bash
# Describe pod issues
kubectl describe pod <pod-name>

# Get previous logs (if pod crashed)
kubectl logs <pod-name> --previous

# Execute into pod
kubectl exec -it <pod-name> -- bash

# Test database connection from backend pod
kubectl exec -it $(kubectl get pod -l app=email-rag,component=backend -o jsonpath='{.items[0].metadata.name}') -- bash
# Inside pod:
python -c "from app.db import engine; print('DB OK')"

# Check events
kubectl get events --sort-by='.lastTimestamp' | head -20

# Check storage
kubectl get pvc
kubectl describe pvc email-rag-uploads-pvc
```

## 🔐 Secret Management

```bash
# View secrets (encoded)
kubectl get secret email-rag-secrets -o yaml

# Decode a specific secret
kubectl get secret email-rag-secrets -o jsonpath='{.data.secret-key}' | base64 -d

# Update a secret
kubectl create secret generic email-rag-secrets \
  --from-literal=openai-api-key='sk-...' \
  --dry-run=client -o yaml | kubectl apply -f -

# Restart pods after secret update
kubectl rollout restart deployment email-rag-backend
kubectl rollout restart deployment email-rag-celery
```

## 📈 Scaling Commands

```bash
# Manual scale
kubectl scale deployment email-rag-backend --replicas=5
kubectl scale deployment email-rag-celery --replicas=10
kubectl scale deployment email-rag-frontend --replicas=3

# Check autoscaling
kubectl get hpa -w

# Force scale-in (for testing)
kubectl patch hpa email-rag-backend -p '{"spec":{"minReplicas":1}}'
```

## 🗑️ Cleanup Commands

```bash
# Delete using automated script
./deploy-k8s.sh
# Choose option 6

# OR delete manually:
helm uninstall email-rag-frontend
helm uninstall email-rag-celery
helm uninstall email-rag-backend
kubectl delete -f k8s-dependencies.yaml
kubectl delete -f k8s-pvcs.yaml
kubectl delete -f k8s-secrets.yaml

# Force delete stuck resources
kubectl delete pod <pod-name> --force --grace-period=0
```

## 📦 Backup Commands

```bash
# Backup database
kubectl exec -it postgres-0 -- pg_dump -U pstrag pstrag_db > backup-$(date +%Y%m%d).sql

# Restore database
cat backup-20260114.sql | kubectl exec -i postgres-0 -- psql -U pstrag pstrag_db

# Backup PVC (using Velero if installed)
velero backup create email-rag-$(date +%Y%m%d) \
  --include-resources pvc,pv \
  --selector app=email-rag

# List backups
velero backup get
```

## 🔍 Troubleshooting Scenarios

### Pod stuck in Pending
```bash
kubectl describe pod <pod-name>
# Check: Node affinity, PVC mounting, resource limits
kubectl get nodes --show-labels
kubectl get pvc
```

### Pod CrashLoopBackOff
```bash
kubectl logs <pod-name> --previous
kubectl describe pod <pod-name>
# Check: Environment variables, secrets, database connectivity
```

### Ingress not working
```bash
kubectl describe ingress email-rag-frontend
kubectl get ingress
# Check: Ingress controller logs
kubectl logs -n ingress-nginx -l app.kubernetes.io/component=controller
```

### Database connection errors
```bash
# Test from backend pod
kubectl exec -it <backend-pod> -- bash
psql $DATABASE_URL
# Or
python -c "import asyncio; from app.db import test_connection; asyncio.run(test_connection())"
```

### High memory usage
```bash
kubectl top pods -l app=email-rag
kubectl describe pod <pod-name>
# Adjust resources in values files
```

## 📝 Important Files

- `k8s-values.yaml` - Backend deployment configuration
- `k8s-values-celery-worker.yaml` - Celery worker configuration
- `k8s-values-frontend.yaml` - Frontend deployment configuration
- `k8s-dependencies.yaml` - PostgreSQL, Redis, RabbitMQ
- `k8s-pvcs.yaml` - Persistent volume claims
- `k8s-secrets.example.yaml` - Secret template
- `deploy-k8s.sh` - Automated deployment script
- `KUBERNETES_DEPLOYMENT.md` - Full deployment guide

## 🎯 Key Configuration Points

### Update these before deployment:
1. **Domain names** in ingress configurations
2. **Secrets** in `k8s-secrets.yaml`
3. **Image tags** in values files
4. **Storage class** if not using `nfs-csi`
5. **CORS origins** in backend values
6. **Node selectors** if your nodes are different

## 🌐 Access URLs

After deployment with ingress:
- Frontend: `https://email-rag.iamsaif.ai`
- Backend API: `https://email-rag.iamsaif.ai/api/v1/docs`
- Backend Health: `https://email-rag.iamsaif.ai/health`

Local testing (port-forward):
- Frontend: `http://localhost:8080`
- Backend: `http://localhost:8000/docs`
- RabbitMQ: `http://localhost:15672`

## 💡 Best Practices

1. **Always test in dev/staging first**
2. **Use separate namespaces for environments**
3. **Enable resource limits and requests**
4. **Monitor logs and metrics**
5. **Set up alerts for critical components**
6. **Regular backups of data**
7. **Use sealed-secrets or external-secrets in production**
8. **Keep base images updated**
9. **Document any custom changes**
10. **Test rollback procedures**
