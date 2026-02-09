#!/bin/bash

###############################################################################
# Submit Flink SQL Job: Sales + Products Join CDC Pipeline
# This script submits the Flink SQL job to the running Flink cluster
###############################################################################

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Configuration
FLINK_JOBMANAGER="jobmanager:8081"
SQL_SCRIPT="/opt/flink/jobs/sales-products-join.sql"
SQL_CLIENT="/opt/flink/bin/sql-client.sh"

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}Flink SQL Job Submission Script${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""

# Wait for Flink JobManager to be ready
echo -e "${YELLOW}Waiting for Flink JobManager...${NC}"
until curl -s http://${FLINK_JOBMANAGER}/overview >/dev/null 2>&1; do
    echo "JobManager not ready yet... sleeping"
    sleep 3
done

echo -e "${GREEN}✓ Flink JobManager is ready!${NC}"
echo ""

# Wait for MySQL
echo -e "${YELLOW}Waiting for MySQL to be ready...${NC}"
until mysql -hmysql -P3306 -uroot -prootpw -e "SELECT 1" >/dev/null 2>&1; do
    echo "MySQL not ready yet... sleeping"
    sleep 3
done

echo -e "${GREEN}✓ MySQL is ready!${NC}"
echo ""

# Wait for MinIO (Iceberg REST Catalog)
echo -e "${YELLOW}Waiting for MinIO/Iceberg catalog...${NC}"
until curl -s http://minio:9001 >/dev/null 2>&1; do
    echo "MinIO not ready yet... sleeping"
    sleep 3
done

echo -e "${GREEN}✓ MinIO is ready!${NC}"
echo ""

# Show job script info
echo -e "${BLUE}Job Details:${NC}"
echo "  JobManager: http://${FLINK_JOBMANAGER}"
echo "  SQL Script: ${SQL_SCRIPT}"
echo ""

# Submit the SQL job
echo -e "${YELLOW}Submitting Flink SQL job...${NC}"
echo ""

# Execute SQL script using Flink SQL Client
${SQL_CLIENT} embedded \
    -f ${SQL_SCRIPT} \
    -j /opt/flink/lib/flink-sql-connector-kafka-*.jar \
    -j /opt/flink/lib/flink-sql-connector-mysql-cdc-*.jar \
    -j /opt/flink/lib/iceberg-flink-runtime-*.jar

echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}✓ Job submitted successfully!${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo "Monitoring URLs:"
echo "  Flink Web UI:    http://localhost:8081"
echo "  MinIO Console:   http://localhost:9001"
echo "  Trino:           jdbc:trino://localhost:8080/iceberg/appdb"
echo ""
echo "Check running jobs:"
echo "  curl http://localhost:8081/jobs"
echo ""
echo "View job logs:"
echo "  docker-compose logs -f jobmanager"
echo "  docker-compose logs -f taskmanager"
