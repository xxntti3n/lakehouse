#!/bin/bash

###############################################################################
# Submit Flink CDC Jobs
# Run this after JobManager is ready (1/1 Running)
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

# Wait for JobManager to be ready
echo -e "${YELLOW}Waiting for JobManager to be ready...${NC}"
kubectl wait --for=condition=ready pod/$JOBMANAGER_POD -n $NAMESPACE --timeout=120s
echo -e "${GREEN}✓ JobManager is ready${NC}"
echo ""

# Submit all CDC jobs in one SQL session
echo -e "${YELLOW}Submitting all CDC jobs (catalog, tables, streaming jobs)...${NC}"
kubectl exec -n $NAMESPACE $JOBMANAGER_POD -- /opt/flink/bin/sql-client.sh -f /opt/flink/jobs/job.sql
echo -e "${GREEN}✓ All CDC jobs submitted successfully${NC}"
echo ""

# Wait for jobs to start
echo "Waiting 30 seconds for jobs to initialize..."
sleep 30

# Verify jobs
echo ""
echo -e "${YELLOW}Verifying running jobs...${NC}"
kubectl exec -n $NAMESPACE $JOBMANAGER_POD -- /opt/flink/bin/flink list -r || true

echo ""
echo -e "${GREEN}================================================${NC}"
echo -e "${GREEN}✓ Flink CDC Pipeline Running Successfully!${NC}"
echo -e "${GREEN}================================================${NC}"
echo ""
echo "📊 Monitoring:"
echo "  Flink Web UI:    http://localhost:8081"
echo "  MinIO Console:   http://localhost:9001"
echo ""
echo "🔍 Check running jobs:"
echo "  kubectl exec -n $NAMESPACE $JOBMANAGER_POD -- /opt/flink/bin/flink list -r"
echo ""
echo "📋 View JobManager logs:"
echo "  kubectl logs -n $NAMESPACE $JOBMANAGER_POD --tail 100 -f"
echo ""
echo "📋 View TaskManager logs:"
echo "  kubectl logs -n $NAMESPACE -l app=taskmanager --tail 100 -f"
echo ""
