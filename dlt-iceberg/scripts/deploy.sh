#!/bin/bash

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo -e "${GREEN}=== DLT-Iceberg Deployment Script ===${NC}"
echo ""

# Function to print status
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if kubectl is installed
if ! command -v kubectl &> /dev/null; then
    print_error "kubectl is not installed. Please install kubectl first."
    exit 1
fi

# Check if docker is installed
if ! command -v docker &> /dev/null; then
    print_error "docker is not installed. Please install docker first."
    exit 1
fi

print_status "Step 1: Building DLT Pipeline Docker image..."
cd "$PROJECT_ROOT"
docker build -f docker/Dockerfile.dlt-pipeline -t dlt-iceberg-pipeline:latest .

if [ $? -eq 0 ]; then
    print_status "✓ Docker image built successfully"
else
    print_error "✗ Failed to build Docker image"
    exit 1
fi

echo ""
print_status "Step 2: Creating kind cluster (if using kind)..."

# Check if kind exists
if command -v kind &> /dev/null; then
    print_status "kind detected. Creating kind cluster..."

    # Check if cluster already exists
    if kind get clusters | grep -q "dlt-iceberg"; then
        print_warning "Cluster 'dlt-iceberg' already exists. Skipping creation."
    else
        kind create cluster --name dlt-iceberg --config "$PROJECT_ROOT/scripts/kind-config.yaml"
        print_status "✓ kind cluster created"
    fi
else
    print_warning "kind not found. Using existing Kubernetes context."
fi

echo ""
print_status "Step 3: Loading Docker image into cluster..."

if command -v kind &> /dev/null; then
    kind load docker-image dlt-iceberg-pipeline:latest --name dlt-iceberg
    print_status "✓ Docker image loaded into kind cluster"
else
    print_warning "Not using kind. Make sure to push image to your registry."
fi

echo ""
print_status "Step 4: Deploying to Kubernetes..."

# Apply all manifests
kubectl apply -k "$PROJECT_ROOT/k8s"

if [ $? -eq 0 ]; then
    print_status "✓ Kubernetes resources deployed"
else
    print_error "✗ Failed to deploy Kubernetes resources"
    exit 1
fi

echo ""
print_status "Step 5: Waiting for deployments to be ready..."

# Wait for PostgreSQL
print_status "Waiting for PostgreSQL..."
kubectl wait --for=condition=ready pod -l app=postgres -n dlt-iceberg --timeout=300s

# Wait for MinIO
print_status "Waiting for MinIO..."
kubectl wait --for=condition=ready pod -l app=minio -n dlt-iceberg --timeout=300s

# Wait for DLT Pipeline
print_status "Waiting for DLT Pipeline..."
kubectl wait --for=condition=ready pod -l app=dlt-pipeline -n dlt-iceberg --timeout=300s

echo ""
print_status "✓ All deployments are ready!"
echo ""
print_status "=== Deployment Summary ==="
echo ""
echo "PostgreSQL:"
echo "  Service: postgres.dlt-iceberg.svc.cluster.local:5432"
echo "  Database: dlt_data"
echo "  User: postgres"
echo "  Replication User: replication_user"
echo ""
echo "MinIO:"
echo "  Service: minio.dlt-iceberg.svc.cluster.local:9000"
echo "  Console: minio.dlt-iceberg.svc.cluster.local:9001"
echo "  Access Key: minioadmin"
echo "  Secret Key: minioadmin123"
echo ""
echo "DLT Pipeline:"
echo "  Pod: Check logs with: kubectl logs -l app=dlt-pipeline -n dlt-iceberg -f"
echo ""
echo -e "${GREEN}=== Deployment Complete! ===${NC}"
