#!/usr/bin/env bash
# Start minimal stack: MySQL + MinIO + CDC + data-generator (~1GB RAM).
# No Nessie, no StarRocks, no DuckDB UI.
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"
echo "Starting minimal stack (mysql, minio, cdc, data-generator)..."
docker-compose up -d --build
echo "Done. Optional: add Nessie (--profile catalog), StarRocks (--profile analytics), UI (--profile duckdb)."
