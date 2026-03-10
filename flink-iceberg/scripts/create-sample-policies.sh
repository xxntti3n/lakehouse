#!/bin/bash
set -e

# ====================================================================
# Create Sample Ranger Policies for StarRocks
# ====================================================================

RANGER_ADMIN_URL="http://localhost:6080"
RANGER_ADMIN_USER="admin"
RANGER_ADMIN_PASS="rangerR0cks!"
STARROCKS_SERVICE_NAME="starrocks"

# Colors
GREEN='\033[0;32m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

# ====================================================================
# Create StarRocks Service in Ranger
# ====================================================================
create_starrocks_service() {
    log_info "Creating StarRocks service in Ranger..."

    # First, check if service exists
    EXISTING=$(curl -s -u "$RANGER_ADMIN_USER:$RANGER_ADMIN_PASS" \
        "$RANGER_ADMIN_URL/service/plugins/services/starrocks" \
        | grep -o "\"name\":\"starrocks\"" || echo "")

    if [ -n "$EXISTING" ]; then
        log_info "StarRocks service already exists"
        return
    fi

    # Create service
    curl -s -u "$RANGER_ADMIN_USER:$RANGER_ADMIN_PASS" \
        -X POST \
        -H "Content-Type: application/json" \
        -d '{
            "name": "starrocks",
            "type": "starrocks",
            "description": "StarRocks data warehouse",
            "configs": {
                "starrocks.jdbc.url": "jdbc:mysql://starrocks-fe:9030",
                "starrocks.jdbc.driver": "com.mysql.cj.jdbc.Driver",
                "username": "root",
                "password": ""
            }
        }' \
        "$RANGER_ADMIN_URL/service/plugins/services"

    log_info "StarRocks service created"
}

# ====================================================================
# Create Sample Policies
# ====================================================================
create_sample_policies() {
    log_info "Creating sample policies..."

    # Policy 1: Read-only access to analytics database
    curl -s -u "$RANGER_ADMIN_USER:$RANGER_ADMIN_PASS" \
        -X POST \
        -H "Content-Type: application/json" \
        -d '{
            "service": "starrocks",
            "name": "Analytics - Read Only",
            "policyType": 0,
            "description": "Read-only access to analytics database",
            "isAuditEnabled": true,
            "resources": {
                "database": {"values": ["analytics"]},
                "table": {"values": ["*"]},
                "column": {"values": ["*"]}
            },
            "policyItems": [
                {
                    "accesses": [
                        {"type": "SELECT", "isAllowed": true}
                    ],
                    "users": ["analytics_user", "analyst"],
                    "groups": []
                }
            ]
        }' \
        "$RANGER_ADMIN_URL/service/plugins/policies"

    log_info "Created: Analytics - Read Only policy"

    # Policy 2: Full access to admin database for admins
    curl -s -u "$RANGER_ADMIN_USER:$RANGER_ADMIN_PASS" \
        -X POST \
        -H "Content-Type: application/json" \
        -d '{
            "service": "starrocks",
            "name": "Admin - Full Access",
            "policyType": 0,
            "description": "Full access to admin database",
            "isAuditEnabled": true,
            "resources": {
                "database": {"values": ["admin"]},
                "table": {"values": ["*"]},
                "column": {"values": ["*"]}
            },
            "policyItems": [
                {
                    "accesses": [
                        {"type": "SELECT", "isAllowed": true},
                        {"type": "INSERT", "isAllowed": true},
                        {"type": "UPDATE", "isAllowed": true},
                        {"type": "DELETE", "isAllowed": true},
                        {"type": "CREATE", "isAllowed": true},
                        {"type": "DROP", "isAllowed": true},
                        {"type": "ALTER", "isAllowed": true}
                    ],
                    "users": ["admin_user"],
                    "groups": ["admin_group"]
                }
            ]
        }' \
        "$RANGER_ADMIN_URL/service/plugins/policies"

    log_info "Created: Admin - Full Access policy"

    # Policy 3: Column-level masking for PII data
    curl -s -u "$RANGER_ADMIN_USER:$RANGER_ADMIN_PASS" \
        -X POST \
        -H "Content-Type: application/json" \
        -d '{
            "service": "starrocks",
            "name": "PII - Mask Sensitive Columns",
            "policyType": 0,
            "description": "Mask sensitive columns in customers table",
            "isAuditEnabled": true,
            "resources": {
                "database": {"values": ["sales"]},
                "table": {"values": ["customers"]},
                "column": {"values": ["email", "phone", "ssn"]}
            },
            "policyItems": [
                {
                    "accesses": [
                        {"type": "SELECT", "isAllowed": true}
                    ],
                    "users": ["*"],
                    "groups": [],
                    "dataMaskPolicyItems": [
                        {
                            "dataMaskType": "MASK",
                            "conditionExpr": ""
                        }
                    ]
                }
            ],
            "rowFilterInfo": {
                "filterExpr": ""
            }
        }' \
        "$RANGER_ADMIN_URL/service/plugins/policies"

    log_info "Created: PII - Mask Sensitive Columns policy"

    log_info "Sample policies created successfully"
}

# ====================================================================
# Main
# ====================================================================
main() {
    log_info "=== Creating Sample Ranger Policies ==="
    echo ""

    create_starrocks_service
    create_sample_policies

    echo ""
    log_info "Sample policies created!"
    log_info "Log into Ranger Admin to view and modify policies"
}

main "$@"
