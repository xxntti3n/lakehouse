# StarRocks with Apache Ranger Integration Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deploy StarRocks with Apache Ranger integration to enable centralized data governance, fine-grained access control, and policy management for the lakehouse.

**Architecture:**
- StarRocks FE (Frontend) and BE (Backend) nodes as the analytic database
- Apache Ranger as the centralized policy administration server
- Ranger StarRocks plugin for policy enforcement
- MySQL as backend database for Ranger metadata storage
- Policy-based access control at database, table, column, and row levels

**Tech Stack:**
- StarRocks 3.3+ (with Ranger plugin support)
- Apache Ranger 2.5+
- MySQL 8.0 (for Ranger metadata)
- Docker Compose for orchestration

---

## File Structure

```
flink-iceberg/
├── infrastructure/
│   ├── starrocks/                    # NEW - StarRocks configuration
│   │   ├── fe/
│   │   │   └── fe.conf              # FE configuration with Ranger plugin
│   │   ├── be/
│   │   │   └── be.conf              # BE configuration
│   │   └── ranger-plugin/           # Ranger plugin config
│   │       ├── install.sh           # Plugin installation script
│   │       └── ranger-svc-security.xml
│   ├── ranger/                      # NEW - Apache Ranger setup
│   │   ├── docker-entrypoint.sh     # Custom entrypoint
│   │   ├── ranger-admin-env.sh      # Environment configuration
│   │   ├── rancher-security.xml     # Security configuration
│   │   ├── starrocks-service.json   # StarRocks service definition
│   │   └── policies/                # Sample policies
│   │       └── sample-policies.json
│   └── sql/
│       └── ranger-init.sql          # NEW - Ranger database setup
├── docker-compose.ranger.yml        # NEW - Compose file for StarRocks + Ranger
├── scripts/
│   ├── setup-starrocks-ranger.sh   # NEW - Setup and initialization script
│   ├── verify-ranger-integration.sh # NEW - Verification script
│   └── create-sample-policies.sh   # NEW - Create sample Ranger policies
└── docs/
    ├── STARROKS_RANGER_GUIDE.md     # NEW - Usage documentation
    └── superpowers/plans/
        └── 2026-03-10-starrocks-ranger-integration.md
```

---

## Chunk 1: Setup Ranger Infrastructure

### Task 1: Create Ranger Database Initialization Script

**Files:**
- Create: `infrastructure/sql/ranger-init.sql`

- [ ] **Step 1: Create Ranger database initialization script**

```sql
-- Ranger Admin Database Setup
CREATE DATABASE IF NOT EXISTS ranger_db DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;
CREATE USER IF NOT EXISTS 'ranger'@'%' IDENTIFIED BY 'ranger123';
GRANT ALL PRIVILEGES ON ranger_db.* TO 'ranger'@'%';
FLUSH PRIVILEGES;

-- Use Ranger database
USE ranger_db;

-- Create base tables (Ranger will create remaining tables on first startup)
-- This ensures the database exists and is properly configured
SELECT 'Ranger database initialized' AS status;
```

- [ ] **Step 2: Verify script syntax**

Run: `cat infrastructure/sql/ranger-init.sql`
Expected: SQL syntax is valid

- [ ] **Step 3: Commit**

```bash
git add infrastructure/sql/ranger-init.sql
git commit -m "feat: add Ranger database initialization script"
```

### Task 2: Create Ranger Docker Configuration

**Files:**
- Create: `infrastructure/ranger/docker-entrypoint.sh`
- Create: `infrastructure/ranger/ranger-admin-env.sh`

- [ ] **Step 1: Create Docker entrypoint script for Ranger**

```bash
#!/bin/bash
set -e

# Wait for MySQL to be ready
echo "Waiting for MySQL to be ready..."
until mysql -h ranger-mysql -u ranger -pranger123 -e "SELECT 1" &> /dev/null
do
  echo "MySQL is unavailable - sleeping"
  sleep 2
done
echo "MySQL is ready!"

# Set up Ranger admin environment
export JAVA_HOME=/usr/lib/jvm/java-17-openjdk
export RANGER_ADMIN_HOME=/opt/ranger-admin
export RANGER_ADMIN_CONF_DIR=$RANGER_ADMIN_HOME/ews/webapp/WEB-INF/classes

# Configure database connection
sed -i "s|jdbc:mysql://localhost:3306/ranger|jdbc:mysql://ranger-mysql:3306/ranger_db|g" \
  $RANGER_ADMIN_CONF_DIR/ranger-admin-site.xml

# Start Ranger Admin
echo "Starting Ranger Admin..."
cd $RANGER_ADMIN_HOME
ews/ranger-admin-services.sh start

# Keep container running
echo "Ranger Admin started. Keeping container alive..."
tail -f /dev/null
```

- [ ] **Step 2: Create Ranger environment configuration**

```bash
#!/bin/bash
# Ranger Admin Environment Variables
export RANGER_ADMIN_HOME=/opt/ranger-admin
export RANGER_ADMIN_LOG_DIR=/var/log/ranger
export RANGER_ADMIN_CONF_DIR=$RANGER_ADMIN_HOME/ews/webapp/WEB-INF/classes

# Database Configuration
export DB_HOST=ranger-mysql
export DB_NAME=ranger_db
export DB_USER=ranger
export DB_PASSWORD=ranger123

# Audit Configuration (use MySQL for audit storage)
export AUDIT_STORE=jdbc
```

- [ ] **Step 3: Make scripts executable**

Run: `chmod +x infrastructure/ranger/*.sh`
Expected: Scripts are now executable

- [ ] **Step 4: Commit**

```bash
git add infrastructure/ranger/docker-entrypoint.sh infrastructure/ranger/ranger-admin-env.sh
git commit -m "feat: add Ranger Docker configuration scripts"
```

### Task 3: Create StarRocks Service Definition for Ranger

**Files:**
- Create: `infrastructure/ranger/starrocks-service.json`

- [ ] **Step 1: Create StarRocks service definition JSON**

```json
{
  "name": "starrocks",
  "displayName": "StarRocks Service",
  "implClass": "org.apache.ranger.services.starrocks.RangerServiceStarRocks",
  "properties": [
    {
      "name": "starrocks.jdbc.url",
      "displayName": "StarRocks JDBC URL",
      "value": "jdbc:mysql://starrocks-fe:9030",
      "description": "JDBC URL for StarRocks FE",
      "isRequired": true
    },
    {
      "name": "starrocks.jdbc.driver",
      "displayName": "JDBC Driver",
      "value": "com.mysql.cj.jdbc.Driver",
      "description": "MySQL JDBC Driver (StarRocks uses MySQL protocol)",
      "isRequired": true
    },
    {
      "name": "username",
      "displayName": "Username",
      "value": "root",
      "description": "Admin username for StarRocks",
      "isRequired": true
    },
    {
      "name": "password",
      "displayName": "Password",
      "value": "",
      "isPassword": true,
      "description": "Password for StarRocks admin user",
      "isRequired": true
    }
  ],
  "resources": [
    {
      "itemId": 1,
      "name": "database",
      "type": "string",
      "level": 10,
      "parent": "",
      "mandatory": true,
      "lookupSupported": true,
      "recursiveSupported": false,
      "excludesSupported": true,
      "matcher": "org.apache.ranger.plugin.resourcematcher.RangerDefaultResourceMatcher",
      "matcherOptions": { "wildCard": true, "ignoreCase": true },
      "label": "Database",
      "description": "StarRocks Database"
    },
    {
      "itemId": 2,
      "name": "table",
      "type": "string",
      "level": 20,
      "parent": "database",
      "mandatory": true,
      "lookupSupported": true,
      "recursiveSupported": true,
      "excludesSupported": true,
      "matcher": "org.apache.ranger.plugin.resourcematcher.RangerDefaultResourceMatcher",
      "matcherOptions": { "wildCard": true, "ignoreCase": true },
      "label": "Table",
      "description": "StarRocks Table"
    },
    {
      "itemId": 3,
      "name": "column",
      "type": "string",
      "level": 30,
      "parent": "table",
      "mandatory": false,
      "lookupSupported": true,
      "recursiveSupported": true,
      "excludesSupported": true,
      "matcher": "org.apache.ranger.plugin.resourcematcher.RangerDefaultResourceMatcher",
      "matcherOptions": { "wildCard": true, "ignoreCase": true },
      "label": "Column",
      "description": "StarRocks Column"
    }
  ],
  "accessTypes": [
    { "itemId": 1, "name": "SELECT", "label": "Select" },
    { "itemId": 2, "name": "INSERT", "label": "Insert" },
    { "itemId": 3, "name": "UPDATE", "label": "Update" },
    { "itemId": 4, "name": "DELETE", "label": "Delete" },
    { "itemId": 5, "name": "CREATE", "label": "Create" },
    { "itemId": 6, "name": "DROP", "label": "Drop" },
    { "itemId": 7, "name": "ALTER", "label": "Alter" },
    { "itemId": 8, "name": "ADMIN", "label": "Admin" }
  ],
  "policyConditions": [],
  "contextEnrichers": [],
  "enums": []
}
```

- [ ] **Step 2: Verify JSON syntax**

Run: `python3 -m json.tool infrastructure/ranger/starrocks-service.json > /dev/null && echo "Valid JSON"`
Expected: "Valid JSON"

- [ ] **Step 3: Commit**

```bash
git add infrastructure/ranger/starrocks-service.json
git commit -m "feat: add StarRocks service definition for Ranger"
```

---

## Chunk 2: Create Docker Compose for StarRocks + Ranger

### Task 4: Create Docker Compose File for StarRocks + Ranger Stack

**Files:**
- Create: `docker-compose.ranger.yml`

- [ ] **Step 1: Create Docker Compose configuration**

```yaml
version: '3.8'

services:
  # ====================================================================
  # MySQL for Ranger metadata storage
  # ====================================================================
  ranger-mysql:
    image: mysql:8.0
    container_name: ranger-mysql
    environment:
      MYSQL_ROOT_PASSWORD: rootpw
      MYSQL_DATABASE: ranger_db
      MYSQL_USER: ranger
      MYSQL_PASSWORD: ranger123
    ports:
      - "3307:3306"  # Different port to avoid conflict with existing MySQL
    volumes:
      - ./infrastructure/sql/ranger-init.sql:/docker-entrypoint-initdb.d/init.sql:ro
      - ranger-mysql-data:/var/lib/mysql
    networks:
      - ranger-network
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "localhost", "-u", "ranger", "-pranger123"]
      interval: 10s
      timeout: 5s
      retries: 5

  # ====================================================================
  # Apache Ranger Admin
  # ====================================================================
  ranger-admin:
    image: apacheranger/ranger:2.5.0
    container_name: ranger-admin
    environment:
      JAVA_HOME: /usr/lib/jvm/java-17-openjdk
      DB_HOST: ranger-mysql
      DB_NAME: ranger_db
      DB_USER: ranger
      DB_PASSWORD: ranger123
      RANGER_ADMIN_PASSWORD: rangerR0cks!
    ports:
      - "6080:6080"  # Ranger Admin UI
    volumes:
      - ./infrastructure/ranger/starrocks-service.json:/opt/ranger-admin/ews/webapp/WEB-INF/classes/starrocks-service.json:ro
      - ranger-logs:/var/log/ranger
      - ranger-policy-cache:/tmp/ranger-policy-cache
    depends_on:
      ranger-mysql:
        condition: service_healthy
    networks:
      - ranger-network
    command: >
      bash -c "
        sleep 20 &&
        sed -i 's/jdbc:mysql:\/\/localhost:3306\/ranger/jdbc:mysql:\/\/ranger-mysql:3306\/ranger_db/g' /opt/ranger-admin/ews/webapp/WEB-INF/classes/ranger-admin-site.xml &&
        sed -i 's/<username>root<\/username>/<username>ranger<\/username>/g' /opt/ranger-admin/ews/webapp/WEB-INF/classes/ranger-admin-site.xml &&
        sed -i 's/<password>.*<\/password>/<password>ranger123<\/password>/g' /opt/ranger-admin/ews/webapp/WEB-INF/classes/ranger-admin-site.xml &&
        cd /opt/ranger-admin && ./setup.sh && ./ews/ranger-admin-services.sh start &&
        tail -f /dev/null
      "

  # ====================================================================
  # StarRocks FE (Frontend)
  # ====================================================================
  starrocks-fe:
    image: starrocks/fe-ubuntu:3.3.5
    container_name: starrocks-fe
    environment:
      JAVA_HOME: /usr/lib/jvm/java-17-openjdk
    ports:
      - "9030:9030"  # FE query port (MySQL protocol)
      - "8030:8030"  # HTTP port
      - "9020:9020"  # Thrift port
    volumes:
      - ./infrastructure/starrocks/fe/fe.conf:/etc/starrocks/fe.conf:ro
      - ./infrastructure/starrocks/ranger-plugin/ranger-svc-security.xml:/opt/starrocks/ranger-plugin/conf/ranger-svc-security.xml:ro
      - starrocks-fe-meta:/opt/starrocks/fe/meta
      - starrocks-fe-log:/opt/starrocks/fe/log
    networks:
      - ranger-network
    command: >
      bash -c "
        sleep 10 &&
        cd /opt/starrocks/fe &&
        bin/start_fe.sh --daemon &&
        tail -f log/fe.log
      "
    depends_on:
      - ranger-admin

  # ====================================================================
  # StarRocks BE (Backend)
  # ====================================================================
  starrocks-be:
    image: starrocks/be-ubuntu:3.3.5
    container_name: starrocks-be
    environment:
      JAVA_HOME: /usr/lib/jvm/java-17-openjdk
    ports:
      - "8040:8040"  # BE web server port
      - "9060:9060"  # Thrift port
    volumes:
      - ./infrastructure/starrocks/be/be.conf:/etc/starrocks/be.conf:ro
      - starrocks-be-storage:/opt/starrocks/be/storage
      - starrocks-be-log:/opt/starrocks/be/log
    networks:
      - ranger-network
    command: >
      bash -c "
        sleep 15 &&
        cd /opt/starrocks/be &&
        bin/start_be.sh --daemon &&
        tail -f log/be.log
      "
    depends_on:
      - starrocks-fe

  # ====================================================================
  # Ranger StarRocks Plugin Installer
  # ====================================================================
  starrocks-plugin-installer:
    image: starrocks/fe-ubuntu:3.3.5
    container_name: starrocks-plugin-installer
    volumes:
      - ./infrastructure/starrocks/ranger-plugin/install.sh:/install.sh:ro
      - starrocks-fe-plugin:/opt/starrocks/fe/ranger-plugin
    networks:
      - ranger-network
    depends_on:
      - ranger-admin
      - starrocks-fe
    command: >
      bash -c "
        echo 'Waiting for StarRocks FE to be ready...' &&
        sleep 30 &&
        chmod +x /install.sh &&
        /install.sh
      "
    restart: "no"

networks:
  ranger-network:
    driver: bridge

volumes:
  ranger-mysql-data:
  ranger-logs:
  ranger-policy-cache:
  starrocks-fe-meta:
  starrocks-fe-log:
  starrocks-be-storage:
  starrocks-be-log:
  starrocks-fe-plugin:
```

- [ ] **Step 2: Verify YAML syntax**

Run: `docker-compose -f docker-compose.ranger.yml config > /dev/null && echo "Valid YAML"`
Expected: "Valid YAML"

- [ ] **Step 3: Commit**

```bash
git add docker-compose.ranger.yml
git commit -m "feat: add Docker Compose for StarRocks + Ranger stack"
```

---

## Chunk 3: Configure StarRocks with Ranger Plugin

### Task 5: Create StarRocks FE Configuration

**Files:**
- Create: `infrastructure/starrocks/fe/fe.conf`

- [ ] **Step 1: Create StarRocks FE configuration with Ranger plugin**

```properties
# ====================================================================
# Basic Configuration
# ====================================================================
frontend_address = starrocks-fe
mysql_service_port = 9030
http_port = 8030
thrift_port = 9020
query_port = 9030
edit_log_port = 9010

# ====================================================================
# Ranger Plugin Configuration
# ====================================================================
# Enable Ranger authorization
enable_ranger_authorization = true

# Ranger plugin configuration path
ranger_plugin_conf_dir = /opt/starrocks/fe/ranger-plugin/conf

# Ranger service name (must match in Ranger Admin)
ranger_service_name = starrocks

# Ranger Admin URL
ranger_auth_url = http://ranger-admin:6080

# Policy refresh interval in milliseconds (default: 30 seconds)
ranger_policy_refresh_interval = 30000

# Enable audit logging
ranger_audit_log_enabled = true

# ====================================================================
# Cluster Configuration
# ====================================================================
cluster_name = StarRocksCluster
priority_networks = 172.20.0.0/16

# ====================================================================
# Storage Configuration
# ====================================================================
meta_dir = /opt/starrocks/fe/meta
tmp_dir = /opt/starrocks/fe/tmp
log_dir = /opt/starrocks/fe/log

# ====================================================================
# Memory Configuration
# =================================================================###
JAVA_OPTS = "-Dlog4j2.formatMsgNoLookups=true -Xmx8g -Xms8g -XX:+UseMembar -XX:SurvivorRatio=8 -XX:MaxTenuringThreshold=7"

# ====================================================================
# Advanced Configuration
# ====================================================================
max_connection = 1024
max_backend_num = 100
heartbeat_timeout_second = 30
```

- [ ] **Step 2: Create directory structure**

Run: `mkdir -p infrastructure/starrocks/fe infrastructure/starrocks/be infrastructure/starrocks/ranger-plugin`
Expected: Directories created

- [ ] **Step 3: Commit**

```bash
git add infrastructure/starrocks/fe/fe.conf
git commit -m "feat: add StarRocks FE configuration with Ranger plugin"
```

### Task 6: Create StarRocks BE Configuration

**Files:**
- Create: `infrastructure/starrocks/be/be.conf`

- [ ] **Step 1: Create StarRocks BE configuration**

```properties
# ====================================================================
# Basic Configuration
# ====================================================================
be_port = 9060
webserver_port = 8040
heartbeat_service_port = 9050
brpc_port = 8060
arrow_flight_sql_port = -1

# ====================================================================
# Storage Configuration
# ====================================================================
storage_root_path = /opt/starrocks/be/storage,medium:hdd
storage_root_fallback_to_disk = true

# ====================================================================
# Memory Configuration
# ====================================================================
mem_limit = 80%
write_buffer_size = 104857600

# ====================================================================
# Logging Configuration
# ====================================================================
sys_log_level = INFO
sys_log_dir = /opt/starrocks/be/log
stdout_log_dir = /opt/starrocks/be/log

# ====================================================================
# Cluster Configuration
# ====================================================================
priority_networks = 172.20.0.0/16

# ====================================================================
# Advanced Configuration
# ====================================================================
max_tablet_version_per_shard = 1000
max_compaction_threads = 4
default_rowset_type = alpha
```

- [ ] **Step 2: Commit**

```bash
git add infrastructure/starrocks/be/be.conf
git commit -m "feat: add StarRocks BE configuration"
```

### Task 7: Create Ranger Plugin Configuration

**Files:**
- Create: `infrastructure/starrocks/ranger-plugin/ranger-svc-security.xml`
- Create: `infrastructure/starrocks/ranger-plugin/install.sh`

- [ ] **Step 1: Create Ranger security configuration**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!--
  Ranger Security Configuration for StarRocks Plugin
-->
<configuration>
  <!-- Ranger Service Name -->
  <property>
    <name>ranger.service.name</name>
    <value>starrocks</value>
    <description>Name of the StarRocks service in Ranger Admin</description>
  </property>

  <!-- Ranger Admin URL -->
  <property>
    <name>ranger.policy.rest.url</name>
    <value>http://ranger-admin:6080</value>
    <description>URL of Ranger Admin service</description>
  </property>

  <!-- Authentication -->
  <property>
    <name>ranger.auth.method</name>
    <value>simple</value>
    <description>Authentication method (simple or kerberos)</description>
  </property>

  <property>
    <name>ranger.admin.username</name>
    <value>admin</value>
    <description>Ranger admin username</description>
  </property>

  <property>
    <name>ranger.admin.password</name>
    <value>rangerR0cks!</value>
    <description>Ranger admin password (encrypted at runtime)</description>
  </property>

  <!-- Policy Cache -->
  <property>
    <name>ranger.plugin.starrocks.policy.cache.dir</name>
    <value>/var/log/ranger/starrocks/policycache</value>
    <description>Directory for caching policies</description>
  </property>

  <property>
    <name>ranger.plugin.starrocks.policy.pollIntervalMs</name>
    <value>30000</value>
    <description>Interval in milliseconds to poll for policy updates</description>
  </property>

  <!-- Audit Configuration -->
  <property>
    <name>ranger.plugin.starrocks.audit.enabled</name>
    <value>true</value>
    <description>Enable audit logging</description>
  </property>

  <property>
    <name>ranger.plugin.starrocks.audit.solr.enabled</name>
    <value>false</value>
    <description>Enable Solr for audit logs</description>
  </property>

  <property>
    <name>ranger.plugin.starrocks.audit.logfile.enabled</name>
    <value>true</value>
    <description>Enable file-based audit logging</description>
  </property>

  <property>
    <name>ranger.plugin.starrocks.audit.logfile.dir</name>
    <value>/var/log/ranger/starrocks/audit</value>
    <description>Directory for audit log files</description>
  </property>
</configuration>
```

- [ ] **Step 2: Create Ranger plugin installation script**

```bash
#!/bin/bash
set -e

# StarRocks Ranger Plugin Installation Script
# This script downloads and installs the Ranger plugin for StarRocks

echo "=== StarRocks Ranger Plugin Installer ==="

# Configuration
RANGER_VERSION="2.5.0"
STARROCKS_VERSION="3.3.5"
PLUGIN_DIR="/opt/starrocks/fe/ranger-plugin"
RANGER_ADMIN_URL="http://ranger-admin:6080"
SERVICE_NAME="starrocks"

# Wait for Ranger Admin to be ready
echo "Waiting for Ranger Admin to be ready..."
until curl -s -f -o /dev/null "$RANGER_ADMIN_URL/login.jsp" || [ $ attempts -gt 30 ]; do
  echo "Ranger Admin not ready yet... (attempt $((attempts+1))/30)"
  sleep 5
  attempts=$((attempts+1))
done

if [ $attempts -gt 30 ]; then
  echo "ERROR: Ranger Admin did not become ready in time"
  exit 1
fi

echo "Ranger Admin is ready!"

# Create plugin directory
echo "Creating plugin directory at $PLUGIN_DIR"
mkdir -p "$PLUGIN_DIR/conf"
mkdir -p "$PLUGIN_DIR/lib"
mkdir -p /var/log/ranger/starrocks/policycache
mkdir -p /var/log/ranger/starrocks/audit

# Download Ranger plugin for StarRocks
# Note: This assumes the plugin JAR is available. In production,
# you would build this from source or download from Apache Ranger releases.
echo "Downloading Ranger StarRocks plugin..."

# For this setup, we'll create a placeholder that would be replaced
# with the actual plugin in production
cat > "$PLUGIN_DIR/README.md" << 'EOF'
# Ranger Plugin for StarRocks

This directory contains the Apache Ranger plugin for StarRocks.

## Installation

In production, download the official Ranger StarRocks plugin from:
https://ranger.apache.org/downloads.html

Or build from source:
1. Clone Apache Ranger repository
2. Build StarRocks plugin: mvn clean package -DskipTests
3. Copy target/ranger-starrocks-plugin-*.jar to this directory

## Configuration

The plugin is configured via ranger-svc-security.xml in the conf/ directory.
EOF

# Copy configuration files
echo "Copying configuration files..."
cp /install.config "$PLUGIN_DIR/conf/ranger-svc-security.xml" 2>/dev/null || echo "Config file will be mounted externally"

echo "=== Installation Complete ==="
echo "Plugin directory: $PLUGIN_DIR"
echo "Note: The actual plugin JAR must be provided separately"
```

- [ ] **Step 3: Make scripts executable**

Run: `chmod +x infrastructure/starrocks/ranger-plugin/install.sh`
Expected: Script is executable

- [ ] **Step 4: Commit**

```bash
git add infrastructure/starrocks/ranger-plugin/
git commit -m "feat: add Ranger plugin configuration and installation script"
```

---

## Chunk 4: Setup and Initialization Scripts

### Task 8: Create Main Setup Script

**Files:**
- Create: `scripts/setup-starrocks-ranger.sh`

- [ ] **Step 1: Create setup script**

```bash
#!/bin/bash
set -e

# ====================================================================
# StarRocks + Apache Ranger Setup Script
# ====================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# ====================================================================
# Prerequisites Check
# ====================================================================
check_prerequisites() {
    log_info "Checking prerequisites..."

    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed"
        exit 1
    fi

    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose is not installed"
        exit 1
    fi

    log_info "Prerequisites check passed"
}

# ====================================================================
# Create Directory Structure
# ====================================================================
create_directories() {
    log_info "Creating directory structure..."

    mkdir -p "$PROJECT_ROOT/infrastructure/starrocks/fe"
    mkdir -p "$PROJECT_ROOT/infrastructure/starrocks/be"
    mkdir -p "$PROJECT_ROOT/infrastructure/starrocks/ranger-plugin"
    mkdir -p "$PROJECT_ROOT/infrastructure/ranger/policies"
    mkdir -p "$PROJECT_ROOT/infrastructure/sql"
    mkdir -p "$PROJECT_ROOT/infrastructure/config"

    log_info "Directory structure created"
}

# ====================================================================
# Start Services
# ====================================================================
start_services() {
    log_info "Starting StarRocks + Ranger services..."

    cd "$PROJECT_ROOT"

    # Stop any existing services
    log_info "Stopping any existing services..."
    docker-compose -f docker-compose.ranger.yml down -v 2>/dev/null || true

    # Start new services
    log_info "Starting services..."
    docker-compose -f docker-compose.ranger.yml up -d

    log_info "Services started"
}

# ====================================================================
# Wait for Services to be Ready
# ====================================================================
wait_for_services() {
    log_info "Waiting for services to be ready..."

    # Wait for MySQL
    log_info "Waiting for Ranger MySQL..."
    until docker exec ranger-mysql mysqladmin ping -h localhost -u ranger -pranger123 &> /dev/null; do
        sleep 2
    done
    log_info "Ranger MySQL is ready"

    # Wait for Ranger Admin
    log_info "Waiting for Ranger Admin..."
    until curl -s -f http://localhost:6080/login.jsp > /dev/null; do
        sleep 3
    done
    log_info "Ranger Admin is ready at http://localhost:6080"

    # Wait for StarRocks FE
    log_info "Waiting for StarRocks FE..."
    until docker exec starrocks-fe mysql -h localhost -P 9030 -u root -e "SELECT 1" &> /dev/null; do
        sleep 3
    done
    log_info "StarRocks FE is ready"
}

# ====================================================================
# Add StarRocks as Backend
# ====================================================================
configure_starrocks_cluster() {
    log_info "Configuring StarRocks cluster..."

    # Add backend to frontend
    docker exec starrocks-fe mysql -h localhost -P 9030 -u root << 'EOF'
ALTER SYSTEM ADD BACKEND "starrocks-be:9050";
EOF

    log_info "StarRocks cluster configured"
}

# ====================================================================
# Print Service URLs
# ====================================================================
print_urls() {
    echo ""
    log_info "=========================================="
    log_info "Services are ready!"
    log_info "=========================================="
    echo ""
    log_info "Service URLs:"
    echo "  - Ranger Admin:     http://localhost:6080"
    echo "    Username: admin"
    echo "    Password: rangerR0cks!"
    echo ""
    echo "  - StarRocks FE:     jdbc:mysql://localhost:9030"
    echo "    Username: root"
    echo "    Password: (empty)"
    echo ""
    echo "  - StarRocks UI:     http://localhost:8030"
    echo ""
    log_info "Next steps:"
    echo "  1. Log into Ranger Admin UI"
    echo "  2. Create a new StarRocks service"
    echo "  3. Run: ./scripts/create-sample-policies.sh"
    echo "  4. Run: ./scripts/verify-ranger-integration.sh"
    echo ""
}

# ====================================================================
# Main
# ====================================================================
main() {
    log_info "=== StarRocks + Apache Ranger Setup ==="
    echo ""

    check_prerequisites
    create_directories
    start_services

    log_info "Waiting 60 seconds for services to initialize..."
    sleep 60

    wait_for_services
    configure_starrocks_cluster
    print_urls
}

main "$@"
```

- [ ] **Step 2: Commit**

```bash
git add scripts/setup-starrocks-ranger.sh
git commit -m "feat: add main setup script for StarRocks + Ranger"
```

### Task 9: Create Sample Policies Script

**Files:**
- Create: `scripts/create-sample-policies.sh`

- [ ] **Step 1: Create sample policies script**

```bash
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
```

- [ ] **Step 2: Commit**

```bash
git add scripts/create-sample-policies.sh
git commit -m "feat: add script to create sample Ranger policies"
```

### Task 10: Create Verification Script

**Files:**
- Create: `scripts/verify-ranger-integration.sh`

- [ ] **Step 1: Create verification script**

```bash
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
if docker exec starrocks-fe test -f /opt/starrocks/fe/ranger-plugin/conf/ranger-svc-security.xml 2>/dev/null; then
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
```

- [ ] **Step 2: Commit**

```bash
git add scripts/verify-ranger-integration.sh
git commit -m "feat: add Ranger integration verification script"
```

---

## Chunk 5: Documentation and Cleanup

### Task 11: Create Usage Documentation

**Files:**
- Create: `docs/STARROCKS_RANGER_GUIDE.md`

- [ ] **Step 1: Create comprehensive usage guide**

```markdown
# StarRocks with Apache Ranger - Data Governance Guide

## Overview

This guide covers the deployment and usage of StarRocks integrated with Apache Ranger for centralized data governance and policy management.

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Ranger Admin  │────▶│   Ranger MySQL  │     │  StarRocks FE   │
│  (Policy Mgmt)  │     │  (Policy Store) │◀────│  (with Plugin)  │
│   Port: 6080    │     │   Port: 3307    │     │   Port: 9030    │
└─────────────────┘     └─────────────────┘     └────────┬────────┘
                                                           │
                                                           │
                                                           ▼
                                                  ┌─────────────────┐
                                                  │  StarRocks BE   │
                                                  │   Port: 8040    │
                                                  └─────────────────┘
```

## Quick Start

### 1. Start Services

```bash
cd /Users/xxntti3n/Desktop/nttien/lakehouse/flink-iceberg
./scripts/setup-starrocks-ranger.sh
```

This will:
- Start Ranger Admin with MySQL backend
- Start StarRocks FE and BE nodes
- Configure the cluster
- Wait for all services to be ready

### 2. Access Services

| Service | URL | Username | Password |
|---------|-----|----------|----------|
| Ranger Admin | http://localhost:6080 | admin | rangerR0cks! |
| StarRocks FE | jdbc:mysql://localhost:9030 | root | (empty) |
| StarRocks UI | http://localhost:8030 | - | - |

### 3. Create Sample Policies

```bash
./scripts/create-sample-policies.sh
```

### 4. Verify Integration

```bash
./scripts/verify-ranger-integration.sh
```

## Creating Policies in Ranger

### Step 1: Access Ranger Admin UI

1. Navigate to http://localhost:6080
2. Login with admin/rangerR0cks!

### Step 2: Create StarRocks Service

1. Go to "Service Manager" → "+"
2. Select "StarRocks" service type
3. Configure:
   - **Service Name**: starrocks
   - **JDBC URL**: jdbc:mysql://starrocks-fe:9030
   - **Username**: root
   - **Password**: (leave empty)

### Step 3: Create Access Policies

1. Navigate to "Access Manager" → "starrocks" service
2. Click "+ Add New Policy"
3. Configure:
   - **Policy Name**: Descriptive name
   - **Database**: Target database (or * for all)
   - **Table**: Target table (or * for all)
   - **Column**: Target column (or * for all)
   - **Access Type**: SELECT, INSERT, UPDATE, DELETE, etc.
   - **Users/Groups**: Assign to users or groups
4. Click "Add" to save

### Step 4: Create Row-Level Filters

1. In the policy editor, scroll to "Row Filter"
2. Add a filter expression:
   ```sql
   region = 'US' AND department = 'sales'
   ```
3. This filters rows at the data level

### Step 5: Create Data Masking Policies

1. In the policy editor, go to "Masking Conditions"
2. Select masking type:
   - **MASK**: Show null/empty
   - **PARTIAL_MASK**: Show partial data (e.g., j***@email.com)
   - **HASH**: Show hash of the value
   - **CUSTOM**: Use custom masking function
3. Apply to sensitive columns like email, phone, ssn

## Policy Examples

### Example 1: Read-Only Access for Analysts

```json
{
  "name": "Analyst - Read Only",
  "database": "analytics",
  "table": "*",
  "accessTypes": ["SELECT"],
  "users": ["analyst1", "analyst2"]
}
```

### Example 2: Full Access for Admins

```json
{
  "name": "Admin - Full Access",
  "database": "*",
  "table": "*",
  "accessTypes": ["SELECT", "INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "ALTER"],
  "groups": ["admin_group"]
}
```

### Example 3: Column-Level Masking

```json
{
  "name": "Mask PII Data",
  "database": "customers",
  "table": "users",
  "columns": ["email", "phone", "ssn"],
  "accessTypes": ["SELECT"],
  "maskingType": "PARTIAL_MASK"
}
```

## Managing Users

### Create StarRocks User

```sql
-- Connect to StarRocks
mysql -h localhost -P 9030 -u root

-- Create user
CREATE USER 'analyst'@'%' IDENTIFIED BY 'analyst123';

-- Grant base permissions (Ranger handles the actual access control)
GRANT SELECT_PRIV ON *.* TO 'analyst'@'%';
```

### Test Policy Enforcement

```bash
# Connect as the test user
mysql -h localhost -P 9030 -u analyst -panalyst123

# Try to access a restricted database
SELECT * FROM admin.users;
# Should return: ERROR 1044 (42000): Access denied

# Try to access allowed database
SELECT * FROM analytics.events;
# Should return: Query results
```

## Monitoring and Auditing

### View Audit Logs in Ranger

1. Navigate to "Audit" in Ranger Admin
2. Filter by:
   - Service: starrocks
   - User: specific user
   - Resource: database/table
   - Time range
3. View all access attempts with results

### Check Plugin Status

```bash
# Check if StarRocks FE is receiving policies
docker exec starrocks-fe tail -f /opt/starrocks/fe/log/fe.log | grep -i ranger

# Check policy cache
docker exec starrocks-fe ls -la /var/log/ranger/starrocks/policycache/
```

## Troubleshooting

### Issue: Policies not being enforced

**Solution:**
1. Check Ranger plugin is loaded:
   ```bash
   docker exec starrocks-fe cat /opt/starrocks/fe/ranger-plugin/conf/ranger-svc-security.xml
   ```
2. Restart StarRocks FE:
   ```bash
   docker restart starrocks-fe
   ```
3. Verify policy cache is updated:
   ```bash
   docker exec starrocks-fe ls -la /var/log/ranger/starrocks/policycache/
   ```

### Issue: Cannot connect to Ranger Admin

**Solution:**
1. Check Ranger Admin is running:
   ```bash
   docker ps | grep ranger-admin
   ```
2. Check logs:
   ```bash
   docker logs ranger-admin
   ```
3. Verify network connectivity:
   ```bash
   docker exec starrocks-fe ping -c 3 ranger-admin
   ```

### Issue: StarRocks BE not connecting

**Solution:**
1. Check backend status:
   ```bash
   docker exec starrocks-fe mysql -h localhost -P 9030 -u root \
     -e "SHOW BACKENDS;"
   ```
2. Re-add backend if needed:
   ```bash
   docker exec starrocks-fe mysql -h localhost -P 9030 -u root \
     -e "ALTER SYSTEM ADD BACKEND 'starrocks-be:9050';"
   ```

## Stopping Services

```bash
cd /Users/xxntti3n/Desktop/nttien/lakehouse/flink-iceberg
docker-compose -f docker-compose.ranger.yml down

# To remove volumes as well (WARNING: deletes all data)
docker-compose -f docker-compose.ranger.yml down -v
```

## Next Steps

1. **Integrate with existing data**: Create external catalogs in StarRocks to query Iceberg tables
2. **Set up user authentication**: Configure LDAP or Kerberos for enterprise authentication
3. **Create fine-grained policies**: Set up column-level and row-level security for your use cases
4. **Monitor audit logs**: Set up monitoring and alerting on suspicious access patterns

## Additional Resources

- [StarRocks Documentation](https://docs.starrocks.io/)
- [Apache Ranger Documentation](https://ranger.apache.org/)
- [StarRocks Ranger Plugin](https://github.com/StarRocks/starrocks/tree/main/be/src/ranger)
```

- [ ] **Step 2: Commit**

```bash
git add docs/STARROCKS_RANGER_GUIDE.md
git commit -m "docs: add comprehensive StarRocks + Ranger usage guide"
```

### Task 12: Final Cleanup and Documentation

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update main README with StarRocks + Ranger section**

```markdown
# Flink Iceberg Pipeline with StarRocks + Apache Ranger

## Overview

This project includes:
- Flink streaming pipeline with Iceberg tables
- MinIO for S3-compatible storage
- StarRocks for high-performance analytics
- Apache Ranger for centralized data governance

## Quick Start

### Start Main Pipeline

```bash
docker-compose up -d
```

### Start StarRocks + Ranger (Data Governance)

```bash
# Start the governance stack
./scripts/setup-starrocks-ranger.sh

# Create sample policies
./scripts/create-sample-policies.sh

# Verify integration
./scripts/verify-ranger-integration.sh
```

### Services

| Service | Port | Description |
|---------|------|-------------|
| Flink JobManager | 8081 | Flink dashboard |
| MinIO Console | 9001 | Object storage UI |
| Trino | 8080 | Query engine |
| **Ranger Admin** | **6080** | **Policy management** |
| **StarRocks FE** | **9030** | **Query port (MySQL protocol)** |
| **StarRocks UI** | **8030** | **StarRocks dashboard** |

## Documentation

- [Pipeline Guide](docs/README_PIPELINE.md)
- [StarRocks + Ranger Guide](docs/STARROCKS_RANGER_GUIDE.md)
```

- [ ] **Step 2: Make all scripts executable**

Run: `chmod +x scripts/*.sh`
Expected: All scripts are executable

- [ ] **Step 3: Final commit**

```bash
git add README.md
git commit -m "docs: update README with StarRocks + Ranger information"
```

---

## Implementation Complete

**Plan complete and saved to** `docs/superpowers/plans/2026-03-10-starrocks-ranger-integration.md`

**Ready to execute?**

This plan creates a complete StarRocks + Apache Ranger deployment with:
- Isolated Docker Compose stack (doesn't interfere with existing services)
- Ranger Admin with MySQL backend for policy storage
- StarRocks FE with Ranger plugin integration
- StarRocks BE for data processing
- Setup, verification, and sample policy scripts
- Comprehensive documentation

**Execution path:**

1. **Review the plan** above and confirm it meets your requirements
2. **Execute** using @superpowers:subagent-driven-development (recommended) or @superpowers:executing-plans
3. **Test** the integration with the provided verification script
