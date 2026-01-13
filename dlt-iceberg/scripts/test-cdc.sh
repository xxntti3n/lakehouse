#!/bin/bash

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}=== Testing DLT-Iceberg CDC Pipeline ===${NC}\n"

# Check if kubectl is available
if ! command -v kubectl &> /dev/null; then
    echo "kubectl not found. This script requires Kubernetes."
    exit 1
fi

echo -e "${GREEN}Step 1: Verify all pods are running${NC}"
kubectl get pods -n dlt-iceberg

echo ""
echo -e "${GREEN}Step 2: Connect to PostgreSQL and make changes${NC}"

# Create a test script
cat << 'EOF' | kubectl exec -i postgres-0 -n dlt-iceberg -- psql -U postgres -d dlt_data
-- Insert a new user
INSERT INTO users (username, email) VALUES ('test_cdc_user', 'testcdc@example.com');

-- Update the user
UPDATE users SET email = 'updated@example.com' WHERE username = 'test_cdc_user';

-- Insert an order for this user
INSERT INTO orders (user_id, amount, status) VALUES ((SELECT id FROM users WHERE username = 'test_cdc_user'), 999.99, 'processing');

-- Update the order
UPDATE orders SET status = 'completed' WHERE user_id = (SELECT id FROM users WHERE username = 'test_cdc_user');

-- Delete the user (cascade to orders if FK is set up)
-- DELETE FROM users WHERE username = 'test_cdc_user';

SELECT 'Changes made successfully!' AS result;
EOF

echo ""
echo -e "${GREEN}Step 3: Wait for CDC to process changes...${NC}"
sleep 10

echo ""
echo -e "${GREEN}Step 4: Check DLT pipeline logs for CDC activity${NC}"
echo "Recent logs from DLT pipeline:"
kubectl logs -l app=dlt-pipeline -n dlt-iceberg --tail=50

echo ""
echo -e "${GREEN}Step 5: Verify Iceberg tables in MinIO${NC}"
echo "Checking for Parquet files in MinIO..."

# List MinIO buckets and files
kubectl exec -i minio-0 -n dlt-iceberg -- mc ls local/iceberg-data/ || echo "MinIO CLI not configured, but data should be present."

echo ""
echo -e "${GREEN}Step 6: Sample queries to verify data${NC}"
cat << 'EOF'

To verify the data was captured in Iceberg, you can:

1. Check DLT pipeline state:
   kubectl exec -it <dlt-pipeline-pod> -n dlt-iceberg -- dlt pipeline pg_to_iceberg_cdc show

2. View Iceberg metadata:
   kubectl exec -it <dlt-pipeline-pod> -n dlt-iceberg -- python -c "
   from dlt.common.libs.pyiceberg import get_iceberg_tables
   import dlt
   pipeline = dlt.pipeline('pg_to_iceberg_cdc')
   tables = get_iceberg_tables(pipeline)
   print('Iceberg tables:', list(tables.keys()))
   "

3. Access MinIO console:
   kubectl port-forward svc/minio -n dlt-iceberg 9001:9001
   Open browser to http://localhost:9001
   Login: minioadmin / minioadmin123

EOF

echo -e "${GREEN}Test completed!${NC}"
echo "Review the logs above to verify CDC captured all changes."
