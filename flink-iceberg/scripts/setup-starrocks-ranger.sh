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

    if ! command -v curl &> /dev/null; then
        log_error "curl is not installed"
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

    cd "$PROJECT_ROOT" || { log_error "Failed to cd to $PROJECT_ROOT"; exit 1; }

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
wait_for_service() {
    local service_name="$1"
    local check_command="$2"
    local timeout="${3:-60}"
    local sleep_interval="${4:-3}"

    log_info "Waiting for $service_name..."
    local elapsed=0
    until eval "$check_command" &> /dev/null; do
        if [ "$elapsed" -ge "$timeout" ]; then
            log_error "Timeout waiting for $service_name after ${timeout}s"
            exit 1
        fi
        sleep "$sleep_interval"
        elapsed=$((elapsed + sleep_interval))
    done
    log_info "$service_name is ready"
}

wait_for_services() {
    log_info "Waiting for services to be ready..."

    wait_for_service "Ranger MySQL" \
        "docker exec ranger-mysql mysqladmin ping -h localhost -u ranger -pranger123" \
        60 2

    wait_for_service "Ranger Admin" \
        "curl -s -f http://localhost:6080/login.jsp" \
        60 3

    wait_for_service "StarRocks FE" \
        "docker exec starrocks-fe mysql -h localhost -P 9030 -u root -e 'SELECT 1'" \
        60 3
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

    log_info "Waiting for services to stabilize..."
    sleep 10

    wait_for_services
    configure_starrocks_cluster
    print_urls
}

main "$@"
