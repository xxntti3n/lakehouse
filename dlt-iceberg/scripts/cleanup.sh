#!/bin/bash

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}=== DLT-Iceberg Cleanup Script ===${NC}"
echo ""

read -p "This will delete all DLT-Iceberg resources. Are you sure? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "Aborted."
    exit 0
fi

echo -e "${GREEN}Deleting Kubernetes resources...${NC}"
kubectl delete -k k8s/

echo -e "${GREEN}Deleting kind cluster (if using kind)...${NC}"
if command -v kind &> /dev/null; then
    if kind get clusters | grep -q "dlt-iceberg"; then
        kind delete cluster --name dlt-iceberg
    fi
fi

echo -e "${GREEN}Cleanup complete!${NC}"
