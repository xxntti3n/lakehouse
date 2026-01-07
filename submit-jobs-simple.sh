#!/bin/bash

###############################################################################
# Simplified Flink CDC Job Submission Script
# Run each job submission independently to avoid timeout issues
###############################################################################

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

NAMESPACE="lakehouse"

echo -e "${GREEN}================================================${NC}"
echo -e "${GREEN}Submitting Flink CDC Jobs${NC}"
echo -e "${GREEN}================================================${NC}"
echo ""

# Get JobManager pod
JOBMANAGER_POD=$(kubectl get pods -n $NAMESPACE -l app=jobmanager -o jsonpath='{.items[0].metadata.name}')
echo "Using JobManager: $JOBMANAGER_POD"
echo ""

###############################################################################
# Step 1: Create Catalog and Tables
###############################################################################
echo -e "${YELLOW}[1/3] Creating Iceberg catalog and tables...${NC}"
kubectl exec -n $NAMESPACE $JOBMANAGER_POD -- /opt/flink/bin/sql-client.sh \
  -f /opt/flink/jobs/job.sql --timeout 300000 || {
  echo "Note: Catalog creation may have succeeded despite timeout"
  echo "Verify with: kubectl exec -n $NAMESPACE $JOBMANAGER_POD -- /opt/flink/bin/sql-client.sh -e 'SHOW CATALOGS;'"
}
echo ""

###############################################################################
# Step 2: Start Products CDC Job
###############################################################################
echo -e "${YELLOW}[2/3] Starting Products CDC job...${NC}"
kubectl exec -n $NAMESPACE $JOBMANAGER_POD -- /opt/flink/bin/sql-client.sh \
  -f /opt/flink/jobs/products_streaming.sql --timeout 300000 &
PID1=$!
echo "Products job started (PID: $PID1)"
echo ""

###############################################################################
# Step 3: Start Sales CDC Job
###############################################################################
echo -e "${YELLOW}[3/3] Starting Sales CDC job...${NC}"
kubectl exec -n $NAMESPACE $JOBMANAGER_POD -- /opt/flink/bin/sql-client.sh \
  -f /opt/flink/jobs/sales_streaming.sql --timeout 300000 &
PID2=$!
echo "Sales job started (PID: $PID2)"
echo ""

###############################################################################
# Wait and Verify
###############################################################################
echo "Waiting 30 seconds for jobs to start..."
sleep 30

echo ""
echo -e "${GREEN}================================================${NC}"
echo -e "${GREEN}Job submission complete!${NC}"
echo -e "${GREEN}================================================${NC}"
echo ""
echo "Check Flink Web UI: http://localhost:8081"
echo ""
echo "Verify jobs are running:"
echo "  kubectl exec -n $NAMESPACE $JOBMANAGER_POD -- /opt/flink/bin/flink list -r"
echo ""
echo "View JobManager logs:"
echo "  kubectl logs -n $NAMESPACE $JOBMANAGER_POD --tail 100 -f"
echo ""
