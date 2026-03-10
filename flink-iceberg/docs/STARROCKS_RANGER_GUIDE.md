# StarRocks + Apache Ranger Integration Guide

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Quick Start](#quick-start)
4. [Accessing Services](#accessing-services)
5. [Creating Policies in Ranger](#creating-policies-in-ranger)
6. [Policy Examples](#policy-examples)
7. [Managing Users](#managing-users)
8. [Monitoring and Auditing](#monitoring-and-auditing)
9. [Troubleshooting](#troubleshooting)
10. [Stopping Services](#stopping-services)

---

## Overview

This guide covers the StarRocks + Apache Ranger integration, which provides centralized data governance and fine-grained access control for your StarRocks data warehouse.

### What is StarRocks?

StarRocks is a high-performance analytical database designed for sub-second queries on large datasets. It provides:
- Fast SQL query processing
- Massively Parallel Processing (MPP) architecture
- Real-time analytics capabilities
- MySQL protocol compatibility

### What is Apache Ranger?

Apache Ranger is a centralized security management platform that provides:
- Fine-grained access control (database, table, column-level)
- Centralized policy management
- Audit logging and compliance reporting
- Dynamic policy enforcement
- Data masking and row-level filtering

### Integration Benefits

Combining StarRocks with Apache Ranger gives you:
- **Centralized Governance**: Manage all data access policies from one UI
- **Fine-Grained Control**: Control access at database, table, and column levels
- **Audit Trail**: Track all data access attempts
- **Data Protection**: Mask sensitive data like PII
- **Compliance**: Meet regulatory requirements with detailed audit logs

---

## Architecture

### System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Applications                            │
│                  (BI Tools, Custom Apps)                       │
└─────────────────────────────────────────────────────────────────┘
                                 │
                                 │ MySQL Protocol
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                    StarRocks Frontend (FE)                      │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              Ranger Plugin (Authorization)               │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                                 │
                                 │ Policy Checks
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Apache Ranger Admin                         │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              Policy Management Engine                     │   │
│  │  - Access Control Policies                               │   │
│  │  - Data Masking Policies                                 │   │
│  │  - Row-Level Filters                                     │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                                 │
                                 │ Policy Storage
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                    MySQL (Ranger Metadata)                      │
│              - Policy Definitions                               │
│              - User/Group Mappings                              │
│              - Audit Logs                                       │
└─────────────────────────────────────────────────────────────────┘
```

### Component Details

| Component | Port | Description |
|-----------|------|-------------|
| **StarRocks FE** | 9030 | Frontend server handling queries and Ranger plugin |
| **StarRocks BE** | 8040 | Backend server for data processing |
| **Ranger Admin** | 6080 | Web UI for policy management |
| **Ranger MySQL** | 3307 | Metadata storage for Ranger policies |

### Request Flow

1. User/Bi tool connects to StarRocks FE (port 9030)
2. StarRocks FE receives SQL query
3. Ranger plugin intercepts the request
4. Plugin sends policy check request to Ranger Admin
5. Ranger Admin evaluates policies against user/group
6. Decision returned: ALLOW or DENY
7. StarRocks executes or denies the query
8. Audit log entry created

---

## Quick Start

### Prerequisites

Ensure you have the following installed:
- Docker (20.10+)
- Docker Compose (2.0+)
- curl (for API calls)
- At least 8GB RAM available

### Step 1: Start Services

Run the setup script to start all services:

```bash
cd /Users/xxntti3n/Desktop/nttien/lakehouse/flink-iceberg

# Start StarRocks + Ranger stack
./scripts/setup-starrocks-ranger.sh
```

This script will:
1. Check prerequisites (Docker, Docker Compose, curl)
2. Create necessary directories
3. Start all containers
4. Wait for services to be healthy
5. Configure StarRocks cluster

**Expected output:**
```
[INFO] === StarRocks + Apache Ranger Setup ===
[INFO] Checking prerequisites...
[INFO] Prerequisites check passed
[INFO] Creating directory structure...
[INFO] Starting StarRocks + Ranger services...
...
[INFO] Services are ready!
```

### Step 2: Verify Services

Check that all services are running:

```bash
# Check container status
docker-compose -f docker-compose.ranger.yml ps

# Run verification script
./scripts/verify-ranger-integration.sh
```

**Expected output:**
```
========================================================================
StarRocks + Apache Ranger Integration Verification
========================================================================

[INFO] Test 1: Checking Ranger Admin accessibility...
[PASS] Ranger Admin is accessible at http://localhost:6080

[INFO] Test 2: Checking StarRocks FE accessibility...
[PASS] StarRocks FE is accessible

...
```

### Step 3: Create Sample Policies

Create initial policies to test the integration:

```bash
./scripts/create-sample-policies.sh
```

This creates:
- **Analytics - Read Only**: Read access for analytics users
- **Admin - Full Access**: Full access for admin users
- **PII - Mask Sensitive Columns**: Mask email, phone, SSN columns

### Step 4: Access Ranger Admin UI

Open your browser and navigate to:
```
http://localhost:6080
```

Login with default credentials:
- Username: `admin`
- Password: `rangerR0cks!`

---

## Accessing Services

### Service URLs and Credentials

| Service | URL | Username | Password | Description |
|---------|-----|----------|----------|-------------|
| **Ranger Admin UI** | http://localhost:6080 | `admin` | `rangerR0cks!` | Policy management |
| **StarRocks FE** | jdbc:mysql://localhost:9030 | `root` | (empty) | Query port |
| **StarRocks UI** | http://localhost:8030 | - | - | StarRocks dashboard |
| **Ranger MySQL** | jdbc:mysql://localhost:3307 | `ranger` | `ranger123` | Policy metadata |

### Connecting to StarRocks

#### Using MySQL Client

```bash
# Connect to StarRocks FE
mysql -h 127.0.0.1 -P 9030 -u root

# Create a test database
CREATE DATABASE analytics;
USE analytics;

# Create a test table
CREATE TABLE customers (
    id INT,
    name VARCHAR(100),
    email VARCHAR(100),
    ssn VARCHAR(11),
    created_at DATETIME
) DUPLICATE KEY(id) DISTRIBUTED BY HASH(id) BUCKETS 1;

# Insert test data
INSERT INTO customers VALUES
(1, 'John Doe', 'john@example.com', '123-45-6789', NOW()),
(2, 'Jane Smith', 'jane@example.com', '987-65-4321', NOW());
```

#### Using JDBC

```java
String url = "jdbc:mysql://localhost:9030/analytics";
String user = "root";
String password = "";

Connection conn = DriverManager.getConnection(url, user, password);
```

#### Using Python

```python
import mysql.connector

conn = mysql.connector.connect(
    host='localhost',
    port=9030,
    user='root',
    database='analytics'
)

cursor = conn.cursor()
cursor.execute("SELECT * FROM customers")
```

### Accessing Ranger Admin UI

1. Open browser: http://localhost:6080
2. Login with admin credentials
3. Navigate to **Service Manager** → **starrocks**
4. View and manage policies

---

## Creating Policies in Ranger

### Step-by-Step Policy Creation

#### 1. Create a StarRocks Service (if not exists)

1. Log into Ranger Admin UI
2. Click **Service Manager** in the top menu
3. Click the **+** button next to "StarRocks"
4. Fill in the service details:

   | Field | Value |
   |-------|-------|
   | Service Name | `starrocks` |
   | Display Name | `StarRocks Data Warehouse` |
   | Description | `Production StarRocks cluster` |
   | JDBC URL | `jdbc:mysql://starrocks-fe:9030` |
   | Username | `root` |
   | Password | (leave empty) |

5. Click **Test Connection** to verify
6. Click **Add** to create the service

#### 2. Create a Database-Level Policy

1. Navigate to **Service Manager** → **starrocks**
2. Click **Policy-based Access** → **Resource-based Policies**
3. Click **Add New Policy**

4. Configure the policy:

   **Basic Settings:**
   - **Policy Name**: `Analytics Read Access`
   - **Database**: `analytics`
   - **Table**: `*` (all tables)
   - **Column**: `*` (all columns)

   **Permissions:**
   - Check **SELECT**
   - Uncheck all other permissions

   **Allow Conditions:**
   - **Select User**: `analytics_user`, `analyst`
   - **Select Group**: Leave empty

5. Click **Add** to create the policy

#### 3. Create a Table-Level Policy

1. Follow the same steps as above
2. Configure with specific settings:

   **Basic Settings:**
   - **Policy Name**: `Sales Admin Access`
   - **Database**: `sales`
   - **Table**: `orders` (specific table)
   - **Column**: `*` (all columns)

   **Permissions:**
   - Check **SELECT**, **INSERT**, **UPDATE**

   **Allow Conditions:**
   - **Select User**: `sales_admin`
   - **Select Group**: `sales_team`

#### 4. Create a Column-Level Policy (Data Masking)

1. Create a new policy with these settings:

   **Basic Settings:**
   - **Policy Name**: `Mask PII Data`
   - **Database**: `sales`
   - **Table**: `customers`
   - **Column**: `email`, `phone`, `ssn` (comma-separated)

   **Permissions:**
   - Check **SELECT**

   **Data Masking:**
   - **Masking Type**: `MASK` (shows last 4 characters)
   - **Masking Condition**: Leave empty (applies to all users)

2. Click **Add** to create the masking policy

### Policy Types Explained

| Policy Type | Description | Use Case |
|-------------|-------------|----------|
| **Resource-based** | Controls access to specific databases, tables, columns | Standard access control |
| **Row-level filter** | Filters rows based on conditions | Multi-tenant data isolation |
| **Data masking** | Masks sensitive column values | PII protection, compliance |

### Policy Evaluation Order

Ranger evaluates policies in the following order:

1. **Deny policies** (explicit deny)
2. **Allow policies** (explicit allow)
3. **Default deny** (if no policy matches)

**Example:**
- If a user has `DENY` on table `sales.orders`, they cannot access it
- Even if they have `ALLOW` on database `sales`, the table-level deny takes precedence

---

## Policy Examples

### Example 1: Read-Only Access for Analysts

**Scenario:** Analysts need read-only access to the analytics database.

**Policy Configuration:**

```json
{
  "service": "starrocks",
  "name": "Analysts - Read Only Analytics",
  "policyType": 0,
  "description": "Read-only access for business analysts",
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
      "users": ["analyst_1", "analyst_2", "analyst_3"],
      "groups": ["analytics_team"]
    }
  ]
}
```

**Creating via API:**

```bash
curl -u admin:rangerR0cks! \
  -X POST \
  -H "Content-Type: application/json" \
  -d @/path/to/policy.json \
  http://localhost:6080/service/plugins/policies
```

### Example 2: Full Access for Administrators

**Scenario:** Admins need full control over the admin database.

**Policy Configuration:**

```json
{
  "service": "starrocks",
  "name": "Admins - Full Access",
  "policyType": 0,
  "description": "Full administrative access",
  "isAuditEnabled": true,
  "resources": {
    "database": {"values": ["*"]},
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
      "users": ["admin_user", "dba_admin"],
      "groups": ["admin_group", "dba_team"]
    }
  ]
}
```

### Example 3: Column Masking for PII

**Scenario:** Mask sensitive customer information for all users except admins.

**Policy Configuration:**

```json
{
  "service": "starrocks",
  "name": "PII - Mask Customer Data",
  "policyType": 0,
  "description": "Mask PII columns for non-admin users",
  "isAuditEnabled": true,
  "resources": {
    "database": {"values": ["sales", "marketing"]},
    "table": {"values": ["customers", "leads"]},
    "column": {"values": ["email", "phone", "ssn", "credit_card"]}
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
          "conditionExpr": "user != 'admin_user'"
        }
      ]
    }
  ]
}
```

**Masking Types:**

| Type | Example Output | Description |
|------|----------------|-------------|
| `MASK` | `XXXX-XXXX-6789` | Shows last 4 characters |
| `MASK_NULL` | `NULL` | Replaces with NULL |
| `MASK_SHOW_FIRST_4` | `1234-XXXX-XXXX` | Shows first 4 characters |
| `MASK_HASH` | `a3f2b1c4d5e6` | Hashed value |
| `CUSTOM` | Custom logic | Using regex or UDF |

### Example 4: Row-Level Security

**Scenario:** Users should only see data from their own region.

**Policy Configuration:**

```json
{
  "service": "starrocks",
  "name": "Regional Data Isolation",
  "policyType": 0,
  "description": "Users can only see their region's data",
  "isAuditEnabled": true,
  "resources": {
    "database": {"values": ["sales"]},
    "table": {"values": ["orders"]},
    "column": {"values": ["*"]}
  },
  "policyItems": [
    {
      "accesses": [
        {"type": "SELECT", "isAllowed": true}
      ],
      "users": ["*"],
      "groups": []
    }
  ],
  "rowFilterInfo": {
    "filterExpr": "region = CAST(REQ_USER AS VARCHAR)"
  }
}
```

### Example 5: Time-Based Access

**Scenario:** Allow access only during business hours (9 AM - 5 PM).

**Policy Configuration:**

```json
{
  "service": "starrocks",
  "name": "Business Hours Only",
  "policyType": 0,
  "description": "Restrict access to business hours",
  "isAuditEnabled": true,
  "resources": {
    "database": {"values": ["sales"]},
    "table": {"values": ["*"]},
    "column": {"values": ["*"]}
  },
  "policyItems": [
    {
      "accesses": [
        {"type": "SELECT", "isAllowed": true}
      ],
      "users": ["contractor_1", "contractor_2"],
      "groups": [],
      "conditions": [
        {
          "type": "expression",
          "expression": "HOUR(NOW()) >= 9 AND HOUR(NOW()) < 17"
        }
      ]
    }
  ]
}
```

---

## Managing Users

### Creating Users in StarRocks

StarRocks doesn't have built-in user management; it relies on Ranger for authentication. Here's how to manage users:

#### Method 1: Using MySQL Protocol

```sql
-- Create a new user
CREATE USER 'analyst_1'@'%' IDENTIFIED BY 'password123';

-- Grant basic privileges (Ranger will enforce fine-grained access)
GRANT SELECT_PRIV ON *.*.* TO 'analyst_1'@'%';

-- Create a user with no password (for testing only)
CREATE USER 'test_user'@'%';
```

#### Method 2: Using LDAP/AD Integration

For production, integrate with LDAP/AD:

1. Configure Ranger Admin for LDAP authentication
2. Map LDAP groups to Ranger policies
3. Users authenticate with corporate credentials

### User Groups

Groups make policy management easier:

```sql
-- Note: StarRocks doesn't have native groups
-- Groups are managed in Ranger Admin UI

# In Ranger Admin:
1. Navigate to Settings → Group Mapping
2. Create group: "analysts", "admins", "sales_team"
3. Add users to groups
4. Reference groups in policies instead of individual users
```

### Testing User Access

```bash
# Connect as a specific user
mysql -h 127.0.0.1 -P 9030 -u analyst_1 -panalyst_pass

# Test access
SELECT * FROM analytics.customers;

# If denied, you'll see:
# ERROR 1064 (HY000): Access denied; no policy found
```

---

## Monitoring and Auditing

### Viewing Audit Logs

#### Via Ranger Admin UI

1. Log into Ranger Admin: http://localhost:6080
2. Navigate to **Audit** → **Plugins**
3. Filter by:
   - Service: `starrocks`
   - User: specific username
   - Resource: database/table
   - Date range
4. View detailed audit records

#### Via CLI

```bash
# View recent audit logs
docker exec ranger-admin tail -f /var/log/ranger/audit/ranger-audit.log

# Search for specific user
docker exec ranger-admin grep "user=analyst_1" /var/log/ranger/audit/ranger-audit.log

# Search for denied access
docker exec ranger-admin grep "Access denied" /var/log/ranger/audit/ranger-audit.log
```

### Audit Log Format

Each audit log entry contains:

```json
{
  "access": "SELECT",
  "accessResult": "DENIED",
  "aclEnforcer": "ranger-acl",
  "action": "SELECT",
  "agentHost": "starrocks-fe",
  "clientIp": "192.168.1.100",
  "createTime": "2026-03-10T14:30:00.000Z",
  "dataSourceType": "starrocks",
  "database": "analytics",
  "policyId": 123,
  "reason": "No policy found for user=analyst_1 on resource=analytics.orders",
  "requestData": "SELECT * FROM analytics.orders",
  "resourcePath": "analytics/orders/*",
  "resourceType": "table",
  "sessionId": "abc123",
  "user": "analyst_1"
}
```

### Monitoring Metrics

#### StarRocks Metrics

```bash
# Check query statistics
docker exec starrocks-fe mysql -h localhost -P 9030 -u root << 'EOF'
SELECT
    user,
    COUNT(*) as query_count,
    AVG(query_time) as avg_time
FROM information_schema.queries
GROUP BY user;
EOF
```

#### Ranger Metrics

Access via: http://localhost:6080/login.jsp

Navigate to **Monitoring** to view:
- Policy cache hit/miss rates
- Average authorization time
- Denied vs. allowed request ratios

### Setting Up Alerts

Configure alerts for security events:

1. In Ranger Admin, navigate to **Settings** → **Alerts**
2. Create alert rules for:
   - Multiple denied access attempts
   - Access from unusual IPs
   - Bulk data export attempts
   - Privilege escalation attempts

---

## Troubleshooting

### Common Issues and Solutions

#### Issue 1: Services Won't Start

**Symptoms:**
```bash
# Docker containers keep restarting
docker-compose -f docker-compose.ranger.yml ps
# Shows: Restarting (1) X seconds ago
```

**Solutions:**

```bash
# Check container logs
docker-compose -f docker-compose.ranger.yml logs ranger-admin
docker-compose -f docker-compose.ranger.yml logs starrocks-fe

# Common fixes:
# 1. Port conflicts - ensure ports 6080, 9030 are available
lsof -i :6080
lsof -i :9030

# 2. Insufficient resources - check Docker memory
docker system df
docker stats

# 3. Clean restart
docker-compose -f docker-compose.ranger.yml down -v
docker-compose -f docker-compose.ranger.yml up -d
```

#### Issue 2: Cannot Connect to StarRocks

**Symptoms:**
```
ERROR 2003 (HY000): Can't connect to MySQL server on 'localhost:9030'
```

**Solutions:**

```bash
# Check if FE is running
docker ps | grep starrocks-fe

# Check FE logs
docker logs starrocks-fe --tail 50

# Verify backend is added
docker exec starrocks-fe mysql -h localhost -P 9030 -u root << 'EOF'
SHOW BACKENDS;
EOF

# Add backend if missing
docker exec starrocks-fe mysql -h localhost -P 9030 -u root << 'EOF'
ALTER SYSTEM ADD BACKEND "starrocks-be:9050";
EOF
```

#### Issue 3: Policies Not Enforcing

**Symptoms:**
- Users can access data they shouldn't
- Deny policies not working

**Solutions:**

```bash
# 1. Verify plugin is installed
docker exec starrocks-fe ls -la /opt/starrocks/fe/ranger-plugin/

# 2. Check plugin configuration
docker exec starrocks-fe cat /opt/starrocks/ranger-plugin/conf/ranger-svc-security.xml

# 3. Verify policy cache
docker exec starrocks-fe ls -la /opt/starrocks/fe/ranger-plugin/policycache/

# 4. Restart FE to reload plugin
docker restart starrocks-fe

# 5. Check service in Ranger
curl -u admin:rangerR0cks! \
  http://localhost:6080/service/plugins/services/starrocks
```

#### Issue 4: Ranger Admin Login Fails

**Symptoms:**
- Cannot login to Ranger Admin UI
- Default credentials not working

**Solutions:**

```bash
# Reset admin password in MySQL
docker exec ranger-mysql mysql -u ranger -pranger123 ranger_db << 'EOF'
UPDATE x_user SET password='rangerR0cks!' WHERE login_id='admin';
EOF

# Restart Ranger Admin
docker restart ranger-admin

# Wait for startup
sleep 30
```

#### Issue 5: Performance Issues

**Symptoms:**
- Slow queries
- High latency

**Solutions:**

```bash
# Check system resources
docker stats

# Optimize Ranger policy cache
# Edit: infrastructure/starrocks/ranger-plugin/ranger-svc-security.xml
# Increase: ranger.plugin.starrocks.policy.cache.size

# Restart services
docker-compose -f docker-compose.ranger.yml restart

# Monitor query performance
docker exec starrocks-fe mysql -h localhost -P 9030 -u root << 'EOF'
SELECT query_id, user, database, query_time
FROM information_schema.queries
ORDER BY query_time DESC
LIMIT 10;
EOF
```

### Debug Mode

Enable debug logging for troubleshooting:

```bash
# Enable Ranger plugin debug logging
docker exec starrocks-fe sed -i \
  's/ranger.plugin.starrocks.policy.pollIntervalMs=30000/ranger.plugin.starrocks.policy.pollIntervalMs=5000/g' \
  /opt/starrocks/ranger-plugin/conf/ranger-svc-security.xml

docker restart starrocks-fe

# View detailed logs
docker exec starrocks-fe tail -f /opt/starrocks/fe/log/fe.out
```

### Getting Help

If issues persist:

1. Collect logs:
```bash
mkdir -p /tmp/ranger-debug
docker logs ranger-admin > /tmp/ranger-debug/ranger-admin.log
docker logs starrocks-fe > /tmp/ranger-debug/starrocks-fe.log
docker logs starrocks-be > /tmp/ranger-debug/starrocks-be.log
docker logs ranger-mysql > /tmp/ranger-debug/ranger-mysql.log
```

2. Run verification:
```bash
./scripts/verify-ranger-integration.sh > /tmp/ranger-debug/verify.log
```

3. Check system status:
```bash
docker-compose -f docker-compose.ranger.yml ps > /tmp/ranger-debug/status.log
```

---

## Stopping Services

### Graceful Shutdown

Stop all services gracefully:

```bash
# Stop all services
docker-compose -f docker-compose.ranger.yml down

# Output:
# Stopping starrocks-be         ... done
# Stopping starrocks-fe         ... done
# Stopping ranger-admin         ... done
# Stopping ranger-mysql         ... done
```

### Stop and Remove Data

Remove all data (including policies and databases):

```bash
# WARNING: This deletes all data
docker-compose -f docker-compose.ranger.yml down -v

# Output:
# Stopping starrocks-be         ... done
# Stopping starrocks-fe         ... done
# Stopping ranger-admin         ... done
# Stopping ranger-mysql         ... done
# Removing volume ...
# Removing volume ...
```

### Stop Individual Services

Stop specific services:

```bash
# Stop only StarRocks
docker-compose -f docker-compose.ranger.yml stop starrocks-fe starrocks-be

# Stop only Ranger
docker-compose -f docker-compose.ranger.yml stop ranger-admin

# Restart specific service
docker-compose -f docker-compose.ranger.yml restart starrocks-fe
```

### Backup Before Stopping

Export policies before shutdown:

```bash
# Export all policies via API
curl -u admin:rangerR0cks! \
  http://localhost:6080/service/plugins/policies \
  > /tmp/ranger-policies-backup.json

# Export database
docker exec ranger-mysql mysqldump -u ranger -pranger123 ranger_db \
  > /tmp/ranger-metadata-backup.sql
```

### Clean Restart

For a complete clean restart:

```bash
# 1. Stop everything
docker-compose -f docker-compose.ranger.yml down -v

# 2. Remove any leftover containers
docker rm -f $(docker ps -a -q -f name=ranger -f name=starrocks) 2>/dev/null || true

# 3. Remove images (optional)
docker rmi apacheranger/ranger:2.5.0 starrocks/fe-ubuntu:3.3.5 starrocks/be-ubuntu:3.3.5

# 4. Restart
./scripts/setup-starrocks-ranger.sh
```

---

## Additional Resources

### Official Documentation

- [StarRocks Documentation](https://docs.starrocks.io/)
- [Apache Ranger Documentation](https://ranger.apache.org/documentation.html)
- [Ranger REST API](https://ranger.apache.org/apidocs/index.html)

### Configuration Files

- **StarRocks FE**: `/infrastructure/starrocks/fe/fe.conf`
- **Ranger Plugin**: `/infrastructure/starrocks/ranger-plugin/ranger-svc-security.xml`
- **Docker Compose**: `/docker-compose.ranger.yml`

### Scripts

- **Setup**: `/scripts/setup-starrocks-ranger.sh`
- **Policies**: `/scripts/create-sample-policies.sh`
- **Verification**: `/scripts/verify-ranger-integration.sh`

### Best Practices

1. **Always use groups** instead of individual users in policies
2. **Enable audit logging** for compliance
3. **Test policies** in development before production
4. **Use data masking** for PII instead of complete denial
5. **Monitor performance** impact of authorization checks
6. **Backup policies** regularly via API
7. **Review audit logs** weekly for suspicious activity
8. **Implement least privilege** - only grant necessary access

---

## Appendix

### Port Reference

| Port | Service | Protocol | Description |
|------|---------|----------|-------------|
| 6080 | Ranger Admin | HTTP | Policy management UI |
| 9030 | StarRocks FE | MySQL | Query port |
| 8030 | StarRocks FE | HTTP | Web UI |
| 9020 | StarRocks FE | Thrift | FE internal communication |
| 8040 | StarRocks BE | HTTP | Web server |
| 9060 | StarRocks BE | Thrift | BE internal communication |
| 9050 | StarRocks BE | Thrift | Backend heartbeat |
| 3307 | Ranger MySQL | MySQL | Policy metadata storage |

### Default Credentials Summary

| Service | Username | Password |
|---------|----------|----------|
| Ranger Admin | `admin` | `rangerR0cks!` |
| StarRocks FE | `root` | (empty) |
| Ranger MySQL | `ranger` | `ranger123` |
| Ranger MySQL (root) | `root` | `rootpw` |

### Quick Commands Reference

```bash
# Start services
./scripts/setup-starrocks-ranger.sh

# Create sample policies
./scripts/create-sample-policies.sh

# Verify integration
./scripts/verify-ranger-integration.sh

# Connect to StarRocks
mysql -h 127.0.0.1 -P 9030 -u root

# View logs
docker logs ranger-admin --tail 100 -f
docker logs starrocks-fe --tail 100 -f

# Check service status
docker-compose -f docker-compose.ranger.yml ps

# Stop services
docker-compose -f docker-compose.ranger.yml down
```

---

**Document Version:** 1.0
**Last Updated:** 2026-03-10
**Maintained By:** Data Governance Team
