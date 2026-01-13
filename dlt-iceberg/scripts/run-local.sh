#!/bin/bash

# Helper script to run the pipeline locally
# This script activates the virtual environment and runs the pipeline

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}=== DLT-Iceberg Local Runner ===${NC}"
echo ""

# Script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
PIPELINE_DIR="$PROJECT_ROOT/pipeline"

# Check if virtual environment exists
VENV_PATH="$PROJECT_ROOT/.venv"

if [ ! -d "$VENV_PATH" ]; then
    echo -e "${YELLOW}Virtual environment not found. Creating...${NC}"
    python3 -m venv "$VENV_PATH"
    source "$VENV_PATH/bin/activate"
    pip install -r "$PIPELINE_DIR/requirements.txt"
    echo -e "${GREEN}✓ Virtual environment created${NC}"
else
    source "$VENV_PATH/bin/activate"
fi

echo ""
echo -e "${GREEN}Using Python: $(which python)${NC}"
echo -e "${GREEN}Working directory: $PIPELINE_DIR${NC}"
echo ""

# Check if PostgreSQL and MinIO are configured
echo -e "${YELLOW}Checking environment variables...${NC}"

# Set defaults if not set
export POSTGRES_HOST=${POSTGRES_HOST:-localhost}
export POSTGRES_PORT=${POSTGRES_PORT:-5432}
export POSTGRES_DB=${POSTGRES_DB:-dlt_data}
export POSTGRES_USER=${POSTGRES_USER:-replication_user}
export POSTGRES_PASSWORD=${POSTGRES_PASSWORD:-replication123}

export MINIO_ENDPOINT=${MINIO_ENDPOINT:-http://localhost:9000}
export ICEBERG_BUCKET=${ICEBERG_BUCKET:-iceberg-data}
export MINIO_ACCESS_KEY=${MINIO_ACCESS_KEY:-minioadmin}
export MINIO_SECRET_KEY=${MINIO_SECRET_KEY:-minioadmin123}

export SLOT_NAME=${SLOT_NAME:-dlt_replication_slot}
export PUB_NAME=${PUB_NAME:-dlt_publication}

echo "PostgreSQL: $POSTGRES_USER@$POSTGRES_HOST:$POSTGRES_PORT/$POSTGRES_DB"
echo "MinIO: $MINIO_ENDPOINT/$ICEBERG_BUCKET"
echo ""

echo -e "${GREEN}Starting pipeline...${NC}"
echo ""

# Run the pipeline
cd "$PIPELINE_DIR"
python pg_to_iceberg_pipeline.py
