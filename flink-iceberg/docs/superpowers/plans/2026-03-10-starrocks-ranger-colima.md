# StarRocks + Apache Ranger on Colima Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deploy StarRocks with Apache Ranger authorization on Colima for local development.

**Architecture:** Multi-service Docker Compose setup with shared network. MySQL stores Ranger metadata, Ranger Admin manages policies, StarRocks FE/BE run database with Ranger plugin for authorization.

**Tech Stack:** Colima, Docker Compose, MySQL 8.0, Apache Ranger 2.5.0, StarRocks 3.3

---

## Chunk 1: Colima Setup and Network Configuration

### Task 1: Start Colima VM

**Files:** None

- [ ] **Step 1: Verify Colima is installed**

Run: `which colima`
Expected: Path to colima binary

- [ ] **Step 2: Start Colima with default configuration**

Run: `colima start --cpu 4 --memory 8 --disk 60`
Expected: Colima VM starts successfully

- [ ] **Step 3: Verify Colima status**

Run: `colima status`
Expected: Status shows "running"

- [ ] **Step 4: Verify Docker is accessible from Colima**

Run: `docker ps`
Expected: Empty list (no containers running)

### Task 2: Create Network Compose File

**Files:**
- Create: `infrastructure/docker-compose.network.yml`

- [ ] **Step 1: Create docker-compose.network.yml**

```yaml
name: lakehouse

networks:
  lakehouse_network:
    driver: bridge
    name: lakehouse_network
```

- [ ] **Step 2: Create the shared network**

Run: `cd /Users/xxntti3n/Desktop/nttien/lakehouse/flink-iceberg/infrastructure && docker-compose -f docker-compose.network.yml up -d`
Expected: Network "lakehouse_network" created

- [ ] **Step 3: Verify network exists**

Run: `docker network ls | grep lakehouse_network`
Expected: lakehouse_network listed

- [ ] **Step 4: Commit network configuration**

```bash
git add infrastructure/docker-compose.network.yml
git commit -m "feat: add shared Docker network for lakehouse services"
```

---

## Chunk 2: MySQL Database for Ranger

### Task 3: Create MySQL Compose File

**Files:**
- Create: `infrastructure/docker-compose.mysql.yml`

- [ ] **Step 1: Create docker-compose.mysql.yml**

```yaml
name: lakehouse

networks:
  lakehouse_network:
    name: lakehouse_network
    external: true

services:
  ranger-mysql:
    image: mysql:8.0
    container_name: ranger-mysql
    networks:
      - lakehouse_network
    environment:
      MYSQL_ROOT_PASSWORD: root123
      MYSQL_DATABASE: ranger_db
      MYSQL_USER: ranger
      MYSQL_PASSWORD: ranger123
    ports:
      - "3306:3306"
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "localhost", "-u", "ranger", "-pranger123"]
      interval: 5s
      timeout: 5s
      retries: 10
      start_period: 10s
```

- [ ] **Step 2: Start MySQL container**

Run: `docker-compose -f docker-compose.mysql.yml up -d`
Expected: Container "ranger-mysql" started

- [ ] **Step 3: Wait for MySQL to be healthy**

Run: `docker-compose -f docker-compose.mysql.yml ps`
Expected: ranger-mysql status shows "healthy"

- [ ] **Step 4: Verify MySQL connection**

Run: `docker exec ranger-mysql mysql -uranger -pranger123 -e "SELECT 1"`
Expected: Output shows "1"

- [ ] **Step 5: Commit MySQL configuration**

```bash
git add infrastructure/docker-compose.mysql.yml
git commit -m "feat: add MySQL service for Ranger metadata"
```

---

## Chunk 3: Apache Ranger Admin

### Task 4: Update Ranger Dockerfile

**Files:**
- Modify: `infrastructure/ranger/Dockerfile`

- [ ] **Step 1: Review existing Dockerfile**

Run: `cat infrastructure/ranger/Dockerfile`
Expected: File exists with Ranger 2.5.0 configuration

- [ ] **Step 2: Verify entrypoint script exists**

Run: `ls -la infrastructure/ranger/docker-entrypoint.sh`
Expected: File exists and is executable

- [ ] **Step 3: No changes needed - existing Dockerfile is correct**

Expected: Dockerfile already configured correctly

### Task 5: Create Ranger Compose File

**Files:**
- Create: `infrastructure/docker-compose.ranger.yml`

- [ ] **Step 1: Create docker-compose.ranger.yml**

```yaml
name: lakehouse

networks:
  lakehouse_network:
    name: lakehouse_network
    external: true

services:
  ranger-admin:
    build:
      context: ./ranger
      dockerfile: Dockerfile
    container_name: ranger-admin
    networks:
      - lakehouse_network
    ports:
      - "6080:6080"
    environment:
      DB_HOST: ranger-mysql
      DB_NAME: ranger_db
      DB_USER: ranger
      DB_PASSWORD: ranger123
    depends_on:
      ranger-mysql:
        condition: service_healthy
    volumes:
      - ./ranger/starrocks-service.json:/opt/ranger-admin/starrocks-service.json:ro
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:6080/login.jsp"]
      interval: 10s
      timeout: 5s
      retries: 20
      start_period: 60s
```

- [ ] **Step 2: Start Ranger Admin container**

Run: `docker-compose -f docker-compose.ranger.yml up -d`
Expected: Container "ranger-admin" starts building

- [ ] **Step 3: Wait for Ranger build and startup**

Run: `docker-compose -f docker-compose.ranger.yml logs -f ranger-admin`
Expected: Wait for "Ranger Admin started!" message (may take 2-3 minutes)

- [ ] **Step 4: Verify Ranger is healthy**

Run: `docker-compose -f docker-compose.ranger.yml ps`
Expected: ranger-admin status shows "healthy"

- [ ] **Step 5: Test Ranger UI accessibility**

Run: `curl -I http://localhost:6080/login.jsp`
Expected: HTTP 200 response

- [ ] **Step 6: Commit Ranger configuration**

```bash
git add infrastructure/docker-compose.ranger.yml
git commit -m "feat: add Ranger Admin service"
```

---

## Chunk 4: StarRocks Frontend

### Task 6: Update StarRocks FE Configuration

**Files:**
- Modify: `infrastructure/starrocks/fe/fe.conf`

- [ ] **Step 1: Review existing fe.conf**

Run: `cat infrastructure/starrocks/fe/fe.conf`
Expected: File exists with basic configuration

- [ ] **Step 2: Verify Ranger plugin configuration exists**

Run: `grep "PLUGIN" infrastructure/starrocks/fe/fe.conf`
Expected: PLUGIN_ENABLE and PLUGIN_DIR are configured

- [ ] **Step 3: No changes needed - existing configuration is correct**

Expected: Configuration already has Ranger plugin settings

### Task 7: Create StarRocks Compose File (Part 1: FE)

**Files:**
- Create: `infrastructure/docker-compose.starrocks.yml`

- [ ] **Step 1: Create docker-compose.starrocks.yml with FE service**

```yaml
name: lakehouse

networks:
  lakehouse_network:
    name: lakehouse_network
    external: true

services:
  starrocks-fe:
    image: starrocks/fe:3.3-latest
    container_name: starrocks-fe
    networks:
      - lakehouse_network
    ports:
      - "8030:8030"  # HTTP
      - "9030:9030"  # MySQL protocol
      - "9020:9020"  # Thrift
    volumes:
      - ./starrocks/fe/fe.conf:/opt/starrocks/conf/fe.conf:ro
      - ./starrocks/ranger-plugin:/opt/starrocks/fe/ranger-plugin:ro
    environment:
      HOST_TYPE: FQDN
    command: >
      bash -c "
        echo 'Waiting for Ranger Admin...' &&
        until curl -f http://ranger-admin:6080/login.jsp; do
          echo 'Ranger not ready, sleeping...'
          sleep 5
        done &&
        echo 'Ranger is ready, starting StarRocks FE...' &&
        /opt/starrocks/bin/start_fe.sh --daemon
      "
    healthcheck:
      test: ["CMD", "mysql", "-h", "127.0.0.1", "-P", "9030", "-u", "root", "-e", "SELECT 1"]
      interval: 10s
      timeout: 5s
      retries: 10
      start_period: 60s
```

- [ ] **Step 2: Start StarRocks FE container**

Run: `docker-compose -f docker-compose.starrocks.yml up -d starrocks-fe`
Expected: Container "starrocks-fe" starts

- [ ] **Step 3: Wait for FE to be healthy**

Run: `docker-compose -f docker-compose.starrocks.yml logs -f starrocks-fe`
Expected: Wait for FE to start (may take 1-2 minutes)

- [ ] **Step 4: Verify FE health**

Run: `docker-compose -f docker-compose.starrocks.yml ps`
Expected: starrocks-fe status shows "healthy"

- [ ] **Step 5: Test MySQL connection to FE**

Run: `docker exec starrocks-fe mysql -h127.0.0.1 -P9030 -uroot -e "SHOW FRONTENDS"`
Expected: Output shows FE information

- [ ] **Step 6: Commit FE configuration**

```bash
git add infrastructure/docker-compose.starrocks.yml
git commit -m "feat: add StarRocks FE service"
```

---

## Chunk 5: StarRocks Backend

### Task 8: Create StarRocks Compose File (Part 2: BE)

**Files:**
- Modify: `infrastructure/docker-compose.starrocks.yml`

- [ ] **Step 1: Add BE service to docker-compose.starrocks.yml**

Edit the file and add the BE service after the FE service:

```yaml
  starrocks-be:
    image: starrocks/be:3.3-latest
    container_name: starrocks-be
    networks:
      - lakehouse_network
    ports:
      - "8040:8040"  # HTTP
    volumes:
      - ./starrocks/be/be.conf:/opt/starrocks/conf/be.conf:ro
    environment:
      HOST_TYPE: FQDN
    depends_on:
      starrocks-fe:
        condition: service_healthy
    command: >
      bash -c "
        echo 'Adding FE to BE config...' &&
        /opt/starrocks/bin/add_backend.sh &&
        echo 'Starting StarRocks BE...' &&
        /opt/starrocks/bin/start_be.sh --daemon
      "
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8040/api/health"]
      interval: 10s
      timeout: 5s
      retries: 10
      start_period: 60s
```

- [ ] **Step 2: Start BE container**

Run: `docker-compose -f docker-compose.starrocks.yml up -d starrocks-be`
Expected: Container "starrocks-be" starts

- [ ] **Step 3: Wait for BE to be healthy**

Run: `docker-compose -f docker-compose.starrocks.yml logs -f starrocks-be`
Expected: BE starts successfully

- [ ] **Step 4: Add BE to FE cluster**

Run: `docker exec starrocks-fe mysql -h127.0.0.1 -P9030 -uroot -e "ALTER SYSTEM ADD BACKEND 'starrocks-be:9050'"`
Expected: Query OK, 0 rows affected

- [ ] **Step 5: Verify BE is registered**

Run: `docker exec starrocks-fe mysql -h127.0.0.1 -P9030 -uroot -e "SHOW BACKENDS"`
Expected: Output shows BE with Alive: true

- [ ] **Step 6: Commit BE configuration**

```bash
git add infrastructure/docker-compose.starrocks.yml
git commit -m "feat: add StarRocks BE service"
```

---

## Chunk 6: Orchestration Script

### Task 9: Create deploy.sh Script

**Files:**
- Create: `infrastructure/deploy.sh`

- [ ] **Step 1: Create deploy.sh with start command**

```bash
#!/bin/bash
# StarRocks + Ranger deployment script for Colima

set -e

INFRA_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

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

# Check if Colima is running
check_colima() {
    if ! colima status &>/dev/null; then
        log_error "Colima is not running. Please start it with: colima start"
        exit 1
    fi
    log_info "Colima is running"
}

# Start network
start_network() {
    log_info "Starting Docker network..."
    cd "$INFRA_DIR"
    docker-compose -f docker-compose.network.yml up -d
}

# Start MySQL
start_mysql() {
    log_info "Starting MySQL..."
    cd "$INFRA_DIR"
    docker-compose -f docker-compose.mysql.yml up -d

    log_info "Waiting for MySQL to be healthy..."
    timeout=120
    while [ $timeout -gt 0 ]; do
        if docker-compose -f docker-compose.mysql.yml ps | grep -q "healthy"; then
            log_info "MySQL is healthy!"
            return 0
        fi
        sleep 2
        ((timeout-=2))
    done
    log_error "MySQL failed to become healthy"
    return 1
}

# Start Ranger
start_ranger() {
    log_info "Starting Ranger Admin..."
    cd "$INFRA_DIR"
    docker-compose -f docker-compose.ranger.yml up -d

    log_info "Waiting for Ranger Admin to be healthy (this may take 2-3 minutes)..."
    timeout=300
    while [ $timeout -gt 0 ]; do
        if docker-compose -f docker-compose.ranger.yml ps | grep -q "healthy"; then
            log_info "Ranger Admin is healthy!"
            return 0
        fi
        sleep 5
        ((timeout-=5))
    done
    log_error "Ranger Admin failed to become healthy"
    return 1
}

# Start StarRocks FE
start_starrocks_fe() {
    log_info "Starting StarRocks FE..."
    cd "$INFRA_DIR"
    docker-compose -f docker-compose.starrocks.yml up -d starrocks-fe

    log_info "Waiting for StarRocks FE to be healthy..."
    timeout=180
    while [ $timeout -gt 0 ]; do
        if docker-compose -f docker-compose.starrocks.yml ps starrocks-fe | grep -q "healthy"; then
            log_info "StarRocks FE is healthy!"
            return 0
        fi
        sleep 5
        ((timeout-=5))
    done
    log_error "StarRocks FE failed to become healthy"
    return 1
}

# Start StarRocks BE
start_starrocks_be() {
    log_info "Starting StarRocks BE..."
    cd "$INFRA_DIR"
    docker-compose -f docker-compose.starrocks.yml up -d starrocks-be

    log_info "Waiting for StarRocks BE to be healthy..."
    timeout=180
    while [ $timeout -gt 0 ]; do
        if docker-compose -f docker-compose.starrocks.yml ps starrocks-be | grep -q "healthy"; then
            log_info "StarRocks BE is healthy!"
            break
        fi
        sleep 5
        ((timeout-=5))
    done

    log_info "Adding BE to FE cluster..."
    docker exec starrocks-fe mysql -h127.0.0.1 -P9030 -uroot -e "ALTER SYSTEM ADD BACKEND 'starrocks-be:9050'" || log_warn "BE might already be added"
}

# Start all services
start_all() {
    check_colima
    start_network
    start_mysql
    start_ranger
    start_starrocks_fe
    start_starrocks_be

    log_info "========================================"
    log_info "All services started successfully!"
    log_info "========================================"
    log_info "Ranger Admin UI: http://localhost:6080 (admin/admin)"
    log_info "StarRocks FE: mysql -h 127.0.0.1 -P 9030 -u root"
    log_info "StarRocks UI: http://localhost:8030"
    log_info "========================================"
}

# Stop all services
stop_all() {
    log_info "Stopping all services..."
    cd "$INFRA_DIR"

    docker-compose -f docker-compose.starrocks.yml down
    docker-compose -f docker-compose.ranger.yml down
    docker-compose -f docker-compose.mysql.yml down
    docker-compose -f docker-compose.network.yml down

    log_info "All services stopped"
}

# Show status
show_status() {
    log_info "Service status:"
    echo ""

    cd "$INFRA_DIR"

    echo "Network:"
    docker network ls | grep lakehouse_network || echo "  Not running"
    echo ""

    echo "MySQL:"
    docker-compose -f docker-compose.mysql.yml ps 2>/dev/null || echo "  Not running"
    echo ""

    echo "Ranger Admin:"
    docker-compose -f docker-compose.ranger.yml ps 2>/dev/null || echo "  Not running"
    echo ""

    echo "StarRocks:"
    docker-compose -f docker-compose.starrocks.yml ps 2>/dev/null || echo "  Not running"
}

# Show logs
show_logs() {
    cd "$INFRA_DIR"
    docker-compose -f docker-compose.mysql.yml logs -f
}

# Restart all services
restart_all() {
    stop_all
    sleep 2
    start_all
}

# Main command handler
case "${1:-start}" in
    start)
        start_all
        ;;
    stop)
        stop_all
        ;;
    status)
        show_status
        ;;
    logs)
        show_logs
        ;;
    restart)
        restart_all
        ;;
    *)
        echo "Usage: $0 {start|stop|status|logs|restart}"
        exit 1
        ;;
esac
```

- [ ] **Step 2: Make deploy.sh executable**

Run: `chmod +x infrastructure/deploy.sh`
Expected: File is now executable

- [ ] **Step 3: Test status command**

Run: `infrastructure/deploy.sh status`
Expected: Shows current status of all services

- [ ] **Step 4: Commit deploy.sh**

```bash
git add infrastructure/deploy.sh
git commit -m "feat: add deployment orchestration script"
```

---

## Chunk 7: Verification and Documentation

### Task 10: Verify Full Deployment

**Files:** None

- [ ] **Step 1: Stop all services**

Run: `infrastructure/deploy.sh stop`
Expected: All services stopped

- [ ] **Step 2: Start all services with deploy.sh**

Run: `infrastructure/deploy.sh start`
Expected: All services start in order

- [ ] **Step 3: Verify all containers are running**

Run: `docker ps --format "table {{.Names}}\t{{.Status}}"`
Expected: All 4 containers running

- [ ] **Step 4: Test Ranger UI access**

Run: `curl -s -o /dev/null -w "%{http_code}" http://localhost:6080/login.jsp`
Expected: 200

- [ ] **Step 5: Test StarRocks MySQL connection**

Run: `docker exec starrocks-fe mysql -h127.0.0.1 -P9030 -uroot -e "SELECT VERSION()"`
Expected: StarRocks version output

- [ ] **Step 6: Verify BE is registered**

Run: `docker exec starrocks-fe mysql -h127.0.0.1 -P9030 -uroot -e "SHOW BACKENDS"`
Expected: BE shows Alive: true

### Task 11: Update README

**Files:**
- Create: `infrastructure/README.md`

- [ ] **Step 1: Create README.md**

```markdown
# Lakehouse Infrastructure

StarRocks with Apache Ranger authorization deployed on Colima.

## Prerequisites

- Colima: `brew install colima`
- Docker Compose v2

## Quick Start

1. Start Colima:
   ```bash
   colima start --cpu 4 --memory 8 --disk 60
   ```

2. Deploy all services:
   ```bash
   cd infrastructure
   ./deploy.sh start
   ```

3. Access services:
   - Ranger Admin: http://localhost:6080 (admin/admin)
   - StarRocks: `mysql -h 127.0.0.1 -P 9030 -u root`
   - StarRocks UI: http://localhost:8030

## Deploy Script Commands

- `./deploy.sh start` - Start all services in order
- `./deploy.sh stop` - Stop all services
- `./deploy.sh status` - Show service health
- `./deploy.sh logs` - Show logs from all services
- `./deploy.sh restart` - Restart all services

## Services

| Service | Port | Purpose |
|---------|------|---------|
| MySQL | 3306 | Ranger metadata store |
| Ranger Admin | 6080 | Policy management UI |
| StarRocks FE | 8030, 9030 | Query frontend |
| StarRocks BE | 8040 | Data backend |

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Colima VM (4CPU, 8GB, 60GB)              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │         Shared Network: lakehouse_network           │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │   │
│  │  │  MySQL   │──│  Ranger  │──│  StarRocks FE    │  │   │
│  │  │  :3306   │  │  :6080   │  │  :8030, :9030    │  │   │
│  │  └──────────┘  └──────────┘  │         │         │  │   │
│  │                               └─────────┼─────────┘  │   │
│  │                                         │             │   │
│  │                                   ┌─────┴─────┐      │   │
│  │                                   │StarRocks BE│      │   │
│  │                                   │  :8040     │      │   │
│  │                                   └───────────┘      │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## Troubleshooting

### Colima not running
```bash
colima status
colima start
```

### Container restart loops
```bash
./deploy.sh logs
docker logs <container-name>
```

### Port conflicts
Check if ports are already in use:
```bash
lsof -i :6080
lsof -i :9030
```

### Data persistence
This setup uses ephemeral storage. Data is lost when containers are removed.
```

- [ ] **Step 2: Commit README**

```bash
git add infrastructure/README.md
git commit -m "docs: add infrastructure README"
```

- [ ] **Step 3: Final verification complete**

Expected: All tasks completed successfully

---

## Summary

This plan deploys:
1. Colima VM with 4CPU, 8GB RAM, 60GB disk
2. Shared Docker network for service communication
3. MySQL 8.0 for Ranger metadata
4. Apache Ranger 2.5.0 Admin with StarRocks service definition
5. StarRocks 3.3 FE with Ranger plugin
6. StarRocks 3.3 BE connected to FE
7. Orchestration script for easy management

All services use ephemeral storage (data lost on container removal).
