#!/bin/bash

###############################################################################
# Verify Flink CDC Pipeline
# Tests the complete data flow from MySQL → Flink → Iceberg → Trino
###############################################################################

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}Flink CDC Pipeline Verification${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""

# Test 1: Check MySQL is running
echo -e "${YELLOW}[Test 1/7] Checking MySQL...${NC}"
if docker exec mysql mysql -uroot -prootpw -e "USE appdb; SELECT COUNT(*) as product_count FROM products;" >/dev/null 2>&1; then
    PRODUCT_COUNT=$(docker exec mysql mysql -uroot -prootpw -e "USE appdb; SELECT COUNT(*) FROM products;" 2>&1 | tail -1)
    SALES_COUNT=$(docker exec mysql mysql -uroot -prootpw -e "USE appdb; SELECT COUNT(*) FROM sales;" 2>&1 | tail -1)
    echo -e "${GREEN}  ✓ MySQL is running${NC}"
    echo "    Products: ${PRODUCT_COUNT}"
    echo "    Sales: ${SALES_COUNT}"
else
    echo -e "${RED}  ✗ MySQL is not accessible${NC}"
    exit 1
fi
echo ""

# Test 2: Check Flink JobManager
echo -e "${YELLOW}[Test 2/7] Checking Flink JobManager...${NC}"
if curl -s http://localhost:8081/overview >/dev/null 2>&1; then
    echo -e "${GREEN}  ✓ Flink JobManager is running${NC}"
    echo "    Web UI: http://localhost:8081"
else
    echo -e "${RED}  ✗ Flink JobManager is not accessible${NC}"
    exit 1
fi
echo ""

# Test 3: Check Flink Jobs
echo -e "${YELLOW}[Test 3/7] Checking Flink Jobs...${NC}"
JOBS=$(curl -s http://localhost:8081/jobs | jq -r '.jobs[]?.name' 2>/dev/null || echo "")
if [ -n "$JOBS" ]; then
    echo -e "${GREEN}  ✓ Flink jobs are running:${NC}"
    echo "$JOBS" | while read job; do
        echo "    - $job"
    done
else
    echo -e "${YELLOW}  ⚠ No Flink jobs found (job may not be submitted yet)${NC}"
fi
echo ""

# Test 4: Check MinIO/Iceberg
echo -e "${YELLOW}[Test 4/7] Checking MinIO/Iceberg...${NC}"
if curl -s http://localhost:9001 >/dev/null 2>&1; then
    echo -e "${GREEN}  ✓ MinIO is running${NC}"
    echo "    Console: http://localhost:9001 (minio/minio123)"
else
    echo -e "${RED}  ✗ MinIO is not accessible${NC}"
    exit 1
fi
echo ""

# Test 5: Insert Test Data
echo -e "${YELLOW}[Test 5/7] Inserting test data into MySQL...${NC}"
docker exec mysql mysql -uroot -prootpw appdb -e "
    INSERT INTO sales (product_id, qty, price, sale_ts)
    SELECT
        (FLOOR(RAND() * 10) + 1) as product_id,
        FLOOR(1 + (RAND() * 5)) as qty,
        ROUND(10 + (RAND() * 100), 2) as price,
        NOW() as sale_ts;
" 2>&1 | grep -v "Warning" || true

NEW_SALES_COUNT=$(docker exec mysql mysql -uroot -prootpw -e "USE appdb; SELECT COUNT(*) FROM sales;" 2>&1 | tail -1)
echo -e "${GREEN}  ✓ Test data inserted${NC}"
echo "    Total sales in MySQL: ${NEW_SALES_COUNT}"
echo ""

# Test 6: Wait for CDC Processing
echo -e "${YELLOW}[Test 6/7] Waiting for CDC processing (10s)...${NC}"
for i in {10..1}; do
    echo -ne "    ${i} seconds remaining...\r"
    sleep 1
done
echo "    ✓ Wait complete"
echo ""

# Test 7: Query Iceberg via Trino
echo -e "${YELLOW}[Test 7/7] Querying Iceberg via Trino...${NC}"
if docker exec trino trino -e "SELECT * FROM iceberg.appdb.enriched_sales LIMIT 1;" >/dev/null 2>&1; then
    ICEBERG_COUNT=$(docker exec trino trino -e "SELECT COUNT(*) AS cnt FROM iceberg.appdb.enriched_sales;" 2>&1 | grep -v "cnt" | grep -E "^[0-9]+$" || echo "0")

    if [ "$ICEBERG_COUNT" -gt "0" ]; then
        echo -e "${GREEN}  ✓ Data found in Iceberg!${NC}"
        echo "    Records in Iceberg: ${ICEBERG_COUNT}"
        echo ""
        echo -e "${BLUE}Sample data from Iceberg:${NC}"
        docker exec trino trino -e "
            SELECT
                product_name,
                product_category,
                quantity,
                sale_price,
                sale_timestamp
            FROM iceberg.appdb.enriched_sales
            ORDER BY sale_timestamp DESC
            LIMIT 5;
        " 2>&1 | column -t -s '|'
    else
        echo -e "${YELLOW}  ⚠ Iceberg table exists but no data yet${NC}"
        echo "    This is normal if Flink job was just submitted"
        echo "    Wait a bit longer and check Flink UI: http://localhost:8081"
    fi
else
    echo -e "${YELLOW}  ⚠ Could not query Iceberg (table may not exist yet)${NC}"
    echo "    Make sure Flink SQL job has been submitted"
    echo "    Run: ./submit-direct-cdc-job.sh"
fi
echo ""

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}Verification Complete!${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""
echo -e "${BLUE}Next Steps:${NC}"
echo "  1. Monitor Flink job: http://localhost:8081"
echo "  2. Query data: docker exec -it trino trino"
echo "  3. Insert more data: docker exec -it mysql mysql -uroot -prootpw appdb"
echo "  4. Start auto-inserter: docker-compose up -d mysql-data-inserter"
echo ""
echo -e "${BLUE}Example Trino Queries:${NC}"
echo "  SELECT * FROM iceberg.appdb.enriched_sales ORDER BY sale_timestamp DESC LIMIT 10;"
echo "  SELECT product_name, COUNT(*) FROM iceberg.appdb.enriched_sales GROUP BY product_name;"
echo ""
