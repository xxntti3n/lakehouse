#!/bin/bash

# Verification script for DLT-Iceberg deployment
# Checks that all required files and configurations are in place

echo "=== DLT-Iceberg Deployment Verification ==="
echo ""

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

success_count=0
fail_count=0

check_file() {
    if [ -f "$1" ]; then
        echo -e "${GREEN}✓${NC} $1"
        ((success_count++))
    else
        echo -e "${RED}✗${NC} $1 (missing)"
        ((fail_count++))
    fi
}

check_dir() {
    if [ -d "$1" ]; then
        echo -e "${GREEN}✓${NC} $1/"
        ((success_count++))
    else
        echo -e "${RED}✗${NC} $1/ (missing)"
        ((fail_count++))
    fi
}

echo "Checking directory structure..."
check_dir "k8s"
check_dir "docker"
check_dir "pipeline"
check_dir "scripts"
check_dir "docs"
check_dir "config"

echo ""
echo "Checking Kubernetes manifests..."
check_file "k8s/namespace.yaml"
check_file "k8s/postgres-deployment.yaml"
check_file "k8s/minio-deployment.yaml"
check_file "k8s/dlt-pipeline-deployment.yaml"
check_file "k8s/kustomization.yaml"

echo ""
echo "Checking Docker configuration..."
check_file "docker/Dockerfile.dlt-pipeline"
check_file "docker-compose.yml"

echo ""
echo "Checking Pipeline code..."
check_file "pipeline/pg_to_iceberg_pipeline.py"
check_file "pipeline/requirements.txt"

echo ""
echo "Checking Scripts..."
check_file "scripts/deploy.sh"
check_file "scripts/cleanup.sh"
check_file "scripts/test-cdc.sh"
check_file "scripts/kind-config.yaml"
check_file "scripts/init-postgres.sql"

echo ""
echo "Checking Documentation..."
check_file "README.md"
check_file "DEPLOYMENT_SUMMARY.md"
check_file "docs/ARCHITECTURE.md"
check_file "docs/QUICKSTART.md"

echo ""
echo "Checking script permissions..."
if [ -x "scripts/deploy.sh" ]; then
    echo -e "${GREEN}✓${NC} scripts/deploy.sh is executable"
    ((success_count++))
else
    echo -e "${RED}✗${NC} scripts/deploy.sh is not executable"
    ((fail_count++))
fi

if [ -x "scripts/cleanup.sh" ]; then
    echo -e "${GREEN}✓${NC} scripts/cleanup.sh is executable"
    ((success_count++))
else
    echo -e "${RED}✗${NC} scripts/cleanup.sh is not executable"
    ((fail_count++))
fi

if [ -x "scripts/test-cdc.sh" ]; then
    echo -e "${GREEN}✓${NC} scripts/test-cdc.sh is executable"
    ((success_count++))
else
    echo -e "${RED}✗${NC} scripts/test-cdc.sh is not executable"
    ((fail_count++))
fi

echo ""
echo "=== Summary ==="
echo -e "${GREEN}Successes: $success_count${NC}"
echo -e "${RED}Failures: $fail_count${NC}"

if [ $fail_count -eq 0 ]; then
    echo ""
    echo -e "${GREEN}All checks passed! Deployment is ready.${NC}"
    echo ""
    echo "To deploy:"
    echo "  cd /Users/tien.nguyen6/Desktop/Cake/nttien/lakehouse/dlt-iceberg/scripts"
    echo "  ./deploy.sh"
    echo ""
    exit 0
else
    echo ""
    echo -e "${RED}Some checks failed. Please review the missing files above.${NC}"
    exit 1
fi
