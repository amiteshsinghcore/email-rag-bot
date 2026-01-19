#!/bin/bash
# ===========================================
# Email RAG Bot - Kubernetes Deployment Script
# ===========================================
# This script automates the deployment process

set -e  # Exit on error

# Configuration
NAMESPACE="default"
HELM_CHART_PATH="../common-helmchart"  # Update to your helm chart path
REGISTRY="amiteshhsingh"
VERSION="v1.0.0"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=========================================${NC}"
echo -e "${GREEN}Email RAG Bot - K8s Deployment${NC}"
echo -e "${GREEN}=========================================${NC}\n"

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check prerequisites
echo -e "${YELLOW}Checking prerequisites...${NC}"
for cmd in kubectl helm docker; do
    if ! command_exists $cmd; then
        echo -e "${RED}Error: $cmd is not installed${NC}"
        exit 1
    fi
done
echo -e "${GREEN}✓ All prerequisites met${NC}\n"

# Function to wait for deployment
wait_for_deployment() {
    local name=$1
    local label=$2
    echo -e "${YELLOW}Waiting for $name to be ready...${NC}"
    kubectl wait --for=condition=ready pod -l "$label" --timeout=300s -n $NAMESPACE
    echo -e "${GREEN}✓ $name is ready${NC}\n"
}

# Ask user what to deploy
echo "What would you like to do?"
echo "1) Full deployment (dependencies + all services)"
echo "2) Deploy only dependencies (PostgreSQL, Redis, RabbitMQ)"
echo "3) Deploy only application services (Backend, Celery, Frontend)"
echo "4) Update existing deployment"
echo "5) Rollback deployment"
echo "6) Delete all resources"
read -p "Enter choice [1-6]: " choice

case $choice in
    1)
        echo -e "\n${GREEN}Starting full deployment...${NC}\n"
        
        # Step 1: Create secrets
        echo -e "${YELLOW}Step 1: Creating secrets...${NC}"
        if [ ! -f "k8s-secrets.yaml" ]; then
            echo -e "${RED}Error: k8s-secrets.yaml not found!${NC}"
            echo "Please copy k8s-secrets.example.yaml to k8s-secrets.yaml and update with your values"
            exit 1
        fi
        kubectl apply -f k8s-secrets.yaml -n $NAMESPACE
        echo -e "${GREEN}✓ Secrets created${NC}\n"
        
        # Step 2: Create PVCs
        echo -e "${YELLOW}Step 2: Creating Persistent Volume Claims...${NC}"
        kubectl apply -f k8s-pvcs.yaml -n $NAMESPACE
        echo -e "${GREEN}✓ PVCs created${NC}\n"
        
        # Step 3: Deploy dependencies
        echo -e "${YELLOW}Step 3: Deploying dependencies...${NC}"
        kubectl apply -f k8s-dependencies.yaml -n $NAMESPACE
        
        wait_for_deployment "PostgreSQL" "app=postgres"
        wait_for_deployment "Redis" "app=redis"
        wait_for_deployment "RabbitMQ" "app=rabbitmq"
        
        # Step 4: Deploy backend
        echo -e "${YELLOW}Step 4: Deploying backend API...${NC}"
        helm install email-rag-backend $HELM_CHART_PATH \
            -f k8s-values.yaml \
            --namespace $NAMESPACE
        
        wait_for_deployment "Backend" "app=email-rag,component=backend"
        
        # Step 5: Deploy Celery workers
        echo -e "${YELLOW}Step 5: Deploying Celery workers...${NC}"
        helm install email-rag-celery $HELM_CHART_PATH \
            -f k8s-values-celery-worker.yaml \
            --namespace $NAMESPACE
        
        wait_for_deployment "Celery Workers" "app=email-rag,component=celery-worker"
        
        # Step 6: Deploy frontend
        echo -e "${YELLOW}Step 6: Deploying frontend...${NC}"
        helm install email-rag-frontend $HELM_CHART_PATH \
            -f k8s-values-frontend.yaml \
            --namespace $NAMESPACE
        
        wait_for_deployment "Frontend" "app=email-rag,component=frontend"
        
        echo -e "\n${GREEN}=========================================${NC}"
        echo -e "${GREEN}Deployment completed successfully!${NC}"
        echo -e "${GREEN}=========================================${NC}\n"
        
        echo "To access the application:"
        echo "1. Frontend: kubectl port-forward svc/email-rag-frontend 8080:80 -n $NAMESPACE"
        echo "2. Backend API: kubectl port-forward svc/email-rag-backend 8000:8000 -n $NAMESPACE"
        echo "3. Check ingress: kubectl get ingress -n $NAMESPACE"
        ;;
        
    2)
        echo -e "\n${GREEN}Deploying dependencies only...${NC}\n"
        kubectl apply -f k8s-secrets.yaml -n $NAMESPACE
        kubectl apply -f k8s-pvcs.yaml -n $NAMESPACE
        kubectl apply -f k8s-dependencies.yaml -n $NAMESPACE
        
        wait_for_deployment "PostgreSQL" "app=postgres"
        wait_for_deployment "Redis" "app=redis"
        wait_for_deployment "RabbitMQ" "app=rabbitmq"
        
        echo -e "${GREEN}Dependencies deployed successfully!${NC}"
        ;;
        
    3)
        echo -e "\n${GREEN}Deploying application services...${NC}\n"
        
        helm install email-rag-backend $HELM_CHART_PATH -f k8s-values.yaml -n $NAMESPACE
        wait_for_deployment "Backend" "app=email-rag,component=backend"
        
        helm install email-rag-celery $HELM_CHART_PATH -f k8s-values-celery-worker.yaml -n $NAMESPACE
        wait_for_deployment "Celery Workers" "app=email-rag,component=celery-worker"
        
        helm install email-rag-frontend $HELM_CHART_PATH -f k8s-values-frontend.yaml -n $NAMESPACE
        wait_for_deployment "Frontend" "app=email-rag,component=frontend"
        
        echo -e "${GREEN}Application services deployed successfully!${NC}"
        ;;
        
    4)
        echo -e "\n${GREEN}Updating deployments...${NC}\n"
        echo "Which component to update?"
        echo "1) Backend"
        echo "2) Celery Workers"
        echo "3) Frontend"
        echo "4) All"
        read -p "Enter choice [1-4]: " update_choice
        
        case $update_choice in
            1) helm upgrade email-rag-backend $HELM_CHART_PATH -f k8s-values.yaml -n $NAMESPACE ;;
            2) helm upgrade email-rag-celery $HELM_CHART_PATH -f k8s-values-celery-worker.yaml -n $NAMESPACE ;;
            3) helm upgrade email-rag-frontend $HELM_CHART_PATH -f k8s-values-frontend.yaml -n $NAMESPACE ;;
            4)
                helm upgrade email-rag-backend $HELM_CHART_PATH -f k8s-values.yaml -n $NAMESPACE
                helm upgrade email-rag-celery $HELM_CHART_PATH -f k8s-values-celery-worker.yaml -n $NAMESPACE
                helm upgrade email-rag-frontend $HELM_CHART_PATH -f k8s-values-frontend.yaml -n $NAMESPACE
                ;;
            *) echo -e "${RED}Invalid choice${NC}"; exit 1 ;;
        esac
        
        echo -e "${GREEN}Update completed!${NC}"
        ;;
        
    5)
        echo -e "\n${YELLOW}Rollback deployment...${NC}\n"
        echo "Which component to rollback?"
        echo "1) Backend"
        echo "2) Celery Workers"
        echo "3) Frontend"
        read -p "Enter choice [1-3]: " rollback_choice
        
        case $rollback_choice in
            1) helm rollback email-rag-backend 0 -n $NAMESPACE ;;
            2) helm rollback email-rag-celery 0 -n $NAMESPACE ;;
            3) helm rollback email-rag-frontend 0 -n $NAMESPACE ;;
            *) echo -e "${RED}Invalid choice${NC}"; exit 1 ;;
        esac
        
        echo -e "${GREEN}Rollback completed!${NC}"
        ;;
        
    6)
        echo -e "\n${RED}WARNING: This will delete all Email RAG resources!${NC}"
        read -p "Are you sure? (yes/no): " confirm
        if [ "$confirm" == "yes" ]; then
            helm uninstall email-rag-frontend -n $NAMESPACE || true
            helm uninstall email-rag-celery -n $NAMESPACE || true
            helm uninstall email-rag-backend -n $NAMESPACE || true
            kubectl delete -f k8s-dependencies.yaml -n $NAMESPACE || true
            kubectl delete -f k8s-pvcs.yaml -n $NAMESPACE || true
            kubectl delete -f k8s-secrets.yaml -n $NAMESPACE || true
            echo -e "${GREEN}All resources deleted${NC}"
        else
            echo "Cancelled"
        fi
        ;;
        
    *)
        echo -e "${RED}Invalid choice${NC}"
        exit 1
        ;;
esac

echo -e "\n${GREEN}=========================================${NC}"
echo -e "${GREEN}Operation completed${NC}"
echo -e "${GREEN}=========================================${NC}\n"

# Show status
echo "Current status:"
kubectl get pods -l app=email-rag -n $NAMESPACE
echo ""
kubectl get svc -l app=email-rag -n $NAMESPACE
echo ""
kubectl get ingress -n $NAMESPACE
