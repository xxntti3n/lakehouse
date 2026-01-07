#!/bin/bash

###############################################################################
# MySQL Data Generator for CDC Pipeline Testing
# Inserts test records into MySQL products table every 2 minutes
###############################################################################

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

NAMESPACE="lakehouse"
MYSQL_HOST="mysql"
MYSQL_PORT="3306"
MYSQL_USER="root"
MYSQL_PASSWORD="rootpw"
DATABASE="appdb"

# Counter for generating unique records
COUNTER=1

echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}MySQL Data Generator for CDC Testing${NC}"
echo -e "${BLUE}================================================${NC}"
echo ""
echo "This will insert test records into MySQL every 2 minutes"
echo "Press Ctrl+C to stop"
echo ""

while true; do
    TIMESTAMP=$(date +%Y%m%d%H%M%S)

    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] Batch #${COUNTER} - Inserting records...${NC}"

    # Insert 5 random product records
    kubectl exec -n ${NAMESPACE} ${MYSQL_HOST}-0 -- mysql -u${MYSQL_USER} -p${MYSQL_PASSWORD} -e "
        USE ${DATABASE};
        INSERT INTO products (sku, name, price, created_at) VALUES
        ('AUTO-${TIMESTAMP}-001', 'Auto Generated Product ${COUNTER}.1', ROUND(RAND() * 1000, 2), NOW()),
        ('AUTO-${TIMESTAMP}-002', 'Auto Generated Product ${COUNTER}.2', ROUND(RAND() * 1000, 2), NOW()),
        ('AUTO-${TIMESTAMP}-003', 'Auto Generated Product ${COUNTER}.3', ROUND(RAND() * 1000, 2), NOW()),
        ('AUTO-${TIMESTAMP}-004', 'Auto Generated Product ${COUNTER}.4', ROUND(RAND() * 1000, 2), NOW()),
        ('AUTO-${TIMESTAMP}-005', 'Auto Generated Product ${COUNTER}.5', ROUND(RAND() * 1000, 2), NOW());
    " 2>&1 | grep -v "Warning" || true

    # Verify the insert
    TOTAL_COUNT=$(kubectl exec -n ${NAMESPACE} ${MYSQL_HOST}-0 -- mysql -u${MYSQL_USER} -p${MYSQL_PASSWORD} -e "
        USE ${DATABASE};
        SELECT COUNT(*) FROM products;
    " 2>&1 | grep -v "Warning" | tail -1)

    echo -e "${GREEN}✓ Batch #${COUNTER} completed. Total records in MySQL: ${TOTAL_COUNT}${NC}"
    echo ""

    COUNTER=$((COUNTER + 1))

    # Wait 2 minutes before next batch
    echo "Waiting 2 minutes until next batch..."
    echo "--------------------------------------------------"
    sleep 120
done
