#!/bin/bash

###############################################################################
# Submit Flink SQL Job: Direct MySQL CDC (Sales + Products Join)
# This version uses Flink MySQL CDC connector directly (no Kafka/Debezium)
###############################################################################

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Configuration
FLINK_JOBMANAGER="jobmanager:8081"
SQL_SCRIPT="/opt/flink/jobs/sales-products-join-direct-cdc.sql"
SQL_CLIENT="/opt/flink/bin/sql-client.sh"

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}Flink Direct MySQL CDC Job Submission${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""
echo "This script submits a Flink SQL job that:"
echo "  1. Reads MySQL binlog directly (CDC)"
echo "  2. Joins sales with products"
echo "  3. Writes enriched data to Iceberg"
echo ""

# Wait for Flink JobManager
echo -e "${YELLOW}[1/4] Waiting for Flink JobManager...${NC}"
until curl -s http://${FLINK_JOBMANAGER}/overview >/dev/null 2>&1; do
    echo "  JobManager not ready... sleeping"
    sleep 3
done
echo -e "${GREEN}  ✓ Flink JobManager is ready!${NC}"

# Wait for MySQL
echo -e "${YELLOW}[2/4] Waiting for MySQL...${NC}"
until mysql -hmysql -P3306 -uroot -prootpw -e "SELECT 1" >/dev/null 2>&1; do
    echo "  MySQL not ready... sleeping"
    sleep 3
done
echo -e "${GREEN}  ✓ MySQL is ready!${NC}"

# Wait for MinIO (Iceberg REST Catalog)
echo -e "${YELLOW}[3/4] Waiting for MinIO/Iceberg...${NC}"
until curl -s http://minio:9001 >/dev/null 2>&1; do
    echo "  MinIO not ready... sleeping"
    sleep 3
done
echo -e "${GREEN}  ✓ MinIO is ready!${NC}"

# Submit job
echo -e "${YELLOW}[4/4] Submitting Flink SQL job...${NC}"
echo ""
echo "SQL Script: ${SQL_SCRIPT}"
echo ""

# Execute SQL script
${SQL_CLIENT} embedded \
    -f ${SQL_SCRIPT} \
    -j /opt/flink/lib/flink-sql-connector-mysql-cdc-*.jar \
    -j /opt/flink/lib/iceberg-flink-runtime-*.jar

echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}✓ Job submitted and running!${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo -e "${BLUE}Monitoring & Access:${NC}"
echo "  Flink Web UI:      http://localhost:8081"
echo "  MinIO Console:     http://localhost:9001 (minio/minio123)"
echo "  Trino CLI:         docker exec -it trino trino"
echo ""
echo -e "${BLUE}Test the Pipeline:${NC}"
echo "  1. Insert data to MySQL:"
echo "     docker exec -it mysql mysql -uroot -prootpw appdb"
echo "     INSERT INTO sales (product_id, qty, price) VALUES (1, 5, 49.99);"
echo ""
echo "  2. Query Iceberg via Trino:"
echo "     docker exec -it trino trino"
echo "     SELECT * FROM iceberg.appdb.enriched_sales ORDER BY sale_timestamp DESC;"
echo ""
echo -e "${BLUE}View Logs:${NC}"
echo "  docker-compose logs -f jobmanager"
echo "  docker-compose logs -f taskmanager"
echo ""
