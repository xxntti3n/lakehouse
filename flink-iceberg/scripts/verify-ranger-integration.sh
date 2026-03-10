#!/bin/bash
set -e

# ====================================================================
# Verify StarRocks + Apache Ranger Integration
# ====================================================================

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

pass_count=0
fail_count=0

log_pass() {
    echo -e "${GREEN}[PASS]${NC} $1"
    ((pass_count++))
}

log_fail() {
    echo -e "${RED}[FAIL]${NC} $1"
    ((fail_count++))
}

log_info() {
    echo -e "${YELLOW}[INFO]${NC} $1"
}

echo "========================================================================"
echo "StarRocks + Apache Ranger Integration Verification"
echo "========================================================================"
echo ""

# ====================================================================
# Test 1: Check Ranger Admin is accessible
# ====================================================================
log_info "Test 1: Checking Ranger Admin accessibility..."
if curl -s -f http://localhost:6080/login.jsp > /dev/null; then
    log_pass "Ranger Admin is accessible at http://localhost:6080"
else
    log_fail "Ranger Admin is not accessible"
fi
echo ""

# ====================================================================
# Test 2: Check StarRocks FE is accessible
# ====================================================================
log_info "Test 2: Checking StarRocks FE accessibility..."
if docker exec starrocks-fe mysql -h localhost -P 9030 -u root -e "SELECT 1" &> /dev/null; then
    log_pass "StarRocks FE is accessible"
else
    log_fail "StarRocks FE is not accessible"
fi
echo ""

# ====================================================================
# Test 3: Check StarRocks BE is connected
# ====================================================================
log_info "Test 3: Checking StarRocks BE connectivity..."
BACKEND_COUNT=$(docker exec starrocks-fe mysql -h localhost -P 9030 -u root -N -e \
    "SELECT COUNT(*) FROM information_schema.backends WHERE Alive = true;" 2>/dev/null || echo "0")

if [ "$BACKEND_COUNT" -gt 0 ]; then
    log_pass "StarRocks BE is connected ($BACKEND_COUNT backend alive)"
else
    log_fail "StarRocks BE is not connected"
fi
echo ""

# ====================================================================
# Test 4: Check Ranger plugin configuration exists
# ====================================================================
log_info "Test 4: Checking Ranger plugin configuration..."
if docker exec starrocks-fe test -f /opt/starrocks/ranger-plugin/conf/ranger-svc-security.xml 2>/dev/null; then
    log_pass "Ranger plugin configuration exists"
else
    log_fail "Ranger plugin configuration not found"
fi
echo ""

# ====================================================================
# Test 5: Create test database and table
# ====================================================================
log_info "Test 5: Creating test database and table..."
docker exec starrocks-fe mysql -h localhost -P 9030 -u root << 'EOF' 2>/dev/null
CREATE DATABASE IF NOT EXISTS test_ranger_db;
USE test_ranger_db;
CREATE TABLE IF NOT EXISTS test_table (
    id INT,
    name VARCHAR(100),
    sensitive_data VARCHAR(100)
) DUPLICATE KEY(id) DISTRIBUTED BY HASH(id) BUCKETS 1;
INSERT INTO test_table VALUES (1, 'Test User', 'Secret Data');
EOF

if [ $? -eq 0 ]; then
    log_pass "Test database and table created"
else
    log_fail "Failed to create test database/table"
fi
echo ""

# ====================================================================
# Test 6: Verify StarRocks service exists in Ranger
# ====================================================================
log_info "Test 6: Checking StarRocks service in Ranger..."
SERVICE_CHECK=$(curl -s -u admin:rangerR0cks! \
    http://localhost:6080/service/plugins/services/starrocks 2>/dev/null | grep -o "\"name\":\"starrocks\"" || echo "")

if [ -n "$SERVICE_CHECK" ]; then
    log_pass "StarRocks service exists in Ranger"
else
    log_fail "StarRocks service not found in Ranger"
fi
echo ""

# ====================================================================
# Test 7: Check audit logs
# ====================================================================
log_info "Test 7: Checking audit log generation..."
# Query StarRocks to generate audit
docker exec starrocks-fe mysql -h localhost -P 9030 -u root -e \
    "SELECT * FROM test_ranger_db.test_table;" &> /dev/null || true

# Check if audit directory exists
if docker exec ranger-admin test -d /var/log/ranger/starrocks/audit 2>/dev/null || \
   docker exec ranger-admin test -d /var/log/ranger/audit 2>/dev/null; then
    log_pass "Audit log directory exists"
else
    log_fail "Audit log directory not found"
fi
echo ""

# ====================================================================
# Summary
# ====================================================================
echo "========================================================================"
echo "Verification Summary"
echo "========================================================================"
echo ""
echo -e "${GREEN}Passed:${NC} $pass_count"
echo -e "${RED}Failed:${NC} $fail_count"
echo ""

if [ $fail_count -eq 0 ]; then
    echo -e "${GREEN}All tests passed!${NC}"
    exit 0
else
    echo -e "${RED}Some tests failed. Check the output above.${NC}"
    exit 1
fi
