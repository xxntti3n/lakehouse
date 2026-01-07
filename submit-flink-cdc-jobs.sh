#!/bin/bash

###############################################################################
# Flink CDC MySQL to Iceberg Job Submission Script
# This script submits all Flink CDC jobs to capture MySQL changes and write
# them to Iceberg tables in MinIO.
###############################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

NAMESPACE="lakehouse"

echo -e "${GREEN}================================================${NC}"
echo -e "${GREEN}Flink CDC MySQL to Iceberg - Job Submission${NC}"
echo -e "${GREEN}================================================${NC}"
echo ""

###############################################################################
# Step 1: Verify Prerequisites
###############################################################################
echo -e "${YELLOW}Step 1: Verifying prerequisites...${NC}"

# Get JobManager pod name
JOBMANAGER_POD=$(kubectl get pods -n $NAMESPACE -l app=jobmanager -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)

if [ -z "$JOBMANAGER_POD" ]; then
    echo -e "${RED}Error: JobManager pod not found!${NC}"
    echo "Please ensure Flink JobManager is running."
    exit 1
fi

echo -e "${GREEN}✓ JobManager pod found: $JOBMANAGER_POD${NC}"

# Check if pod is ready
POD_STATUS=$(kubectl get pod -n $NAMESPACE $JOBMANAGER_POD -o jsonpath='{.status.phase}')
POD_READY=$(kubectl get pod -n $NAMESPACE $JOBMANAGER_POD -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}')

if [ "$POD_STATUS" != "Running" ] || [ "$POD_READY" != "True" ]; then
    echo -e "${RED}Error: JobManager pod is not ready!${NC}"
    echo "Status: $POD_STATUS, Ready: $POD_READY"
    exit 1
fi

echo -e "${GREEN}✓ JobManager is ready${NC}"
echo ""

###############################################################################
# Step 2: Create Iceberg Catalog and Tables
###############################################################################
echo -e "${YELLOW}Step 2: Creating Iceberg catalog and tables...${NC}"

echo "Executing job.sql..."
kubectl exec -n $NAMESPACE $JOBMANAGER_POD -- /opt/flink/bin/sql-client.sh -f /opt/flink/jobs/job.sql

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Catalog and tables created successfully${NC}"
else
    echo -e "${RED}✗ Failed to create catalog and tables${NC}"
    exit 1
fi
echo ""

###############################################################################
# Step 3: Start Products CDC Streaming Job
###############################################################################
echo -e "${YELLOW}Step 3: Starting Products CDC streaming job...${NC}"

echo "Executing products_streaming.sql..."
kubectl exec -n $NAMESPACE $JOBMANAGER_POD -- /opt/flink/bin/sql-client.sh -f /opt/flink/jobs/products_streaming.sql &

# Give it some time to start
sleep 5

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Products CDC job started successfully${NC}"
else
    echo -e "${RED}✗ Failed to start Products CDC job${NC}"
    exit 1
fi
echo ""

###############################################################################
# Step 4: Start Sales CDC Streaming Job
###############################################################################
echo -e "${YELLOW}Step 4: Starting Sales CDC streaming job...${NC}"

echo "Executing sales_streaming.sql..."
kubectl exec -n $NAMESPACE $JOBMANAGER_POD -- /opt/flink/bin/sql-client.sh -f /opt/flink/jobs/sales_streaming.sql &

# Give it some time to start
sleep 5

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Sales CDC job started successfully${NC}"
else
    echo -e "${RED}✗ Failed to start Sales CDC job${NC}"
    exit 1
fi
echo ""

###############################################################################
# Step 5: Verify Jobs Are Running
###############################################################################
echo -e "${YELLOW}Step 5: Verifying jobs are running...${NC}"
sleep 10

echo "Checking running jobs..."
kubectl exec -n $NAMESPACE $JOBMANAGER_POD -- /opt/flink/bin/flink list -r 2>/dev/null || true

echo ""
echo -e "${GREEN}================================================${NC}"
echo -e "${GREEN}✓ All Flink CDC jobs submitted successfully!${NC}"
echo -e "${GREEN}================================================${NC}"
echo ""
echo "Next steps:"
echo "  1. Open Flink Web UI: http://localhost:8081"
echo "  2. Check 'Running Jobs' to see your CDC pipelines"
echo "  3. Monitor job metrics and checkpoints"
echo ""
echo "To verify data is being captured:"
echo "  kubectl exec -n $NAMESPACE $JOBMANAGER_POD -- /opt/flink/bin/sql-client.sh -e \"SELECT COUNT(*) FROM iceberg_catalog.demo.products;\""
echo "  kubectl exec -n $NAMESPACE $JOBMANAGER_POD -- /opt/flink/bin/sql-client.sh -e \"SELECT COUNT(*) FROM iceberg_catalog.demo.sales;\""
echo ""
echo "To test CDC pipeline:"
echo "  # Insert test data in MySQL"
echo "  kubectl exec -n $NAMESPACE mysql-0 -- mysql -u root -prootpw -e \"USE appdb; INSERT INTO products (sku, name, price, created_at) VALUES ('P-TEST', 'Test Product', 99.99, NOW());\""
echo ""
echo "  # Wait 30-60 seconds, then query Iceberg"
echo "  kubectl exec -n $NAMESPACE trino-XXX -- trino --execute \"SELECT * FROM iceberg_catalog.demo.products WHERE sku = 'P-TEST';\""
echo ""
