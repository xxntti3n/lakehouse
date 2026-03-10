#!/bin/bash
# Delete and recreate MinIO buckets (dlt-warehouse, dlt-checkpoints) for a clean Iceberg run.
# Requires MinIO to be running (e.g. docker compose up -d minio).
# Usage: from project root, ./scripts/reset-minio-buckets.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

# Resolve MinIO container and network (works if minio is running)
CONTAINER="${MINIO_CONTAINER:-minio-storage}"
if ! docker inspect "$CONTAINER" &>/dev/null; then
  echo "MinIO container '$CONTAINER' not found. Start MinIO first: docker compose up -d minio"
  exit 1
fi
NETWORK="$(docker inspect "$CONTAINER" --format '{{range $k, $v := .NetworkSettings.Networks}}{{$k}}{{end}}' | head -1)"
if [ -z "$NETWORK" ]; then
  echo "Could not get network for $CONTAINER"
  exit 1
fi

echo "Using MinIO container: $CONTAINER, network: $NETWORK"
echo "Deleting and recreating buckets..."

# Use mc in a one-off container on the same network (minio/mc has no shell, run mc directly)
docker run --rm --network "$NETWORK" \
  -e MC_HOST_minio="http://minio:9000:minio:minio123" \
  minio/mc:latest mc rm -r --force minio/dlt-warehouse/ || true
docker run --rm --network "$NETWORK" \
  -e MC_HOST_minio="http://minio:9000:minio:minio123" \
  minio/mc:latest mc rm -r --force minio/dlt-checkpoints/ || true
# (above: || true so missing buckets don't fail the script)
docker run --rm --network "$NETWORK" \
  -e MC_HOST_minio="http://minio:9000:minio:minio123" \
  minio/mc:latest mc mb minio/dlt-warehouse --ignore-existing
docker run --rm --network "$NETWORK" \
  -e MC_HOST_minio="http://minio:9000:minio:minio123" \
  minio/mc:latest mc mb minio/dlt-checkpoints --ignore-existing
docker run --rm --network "$NETWORK" \
  -e MC_HOST_minio="http://minio:9000:minio:minio123" \
  minio/mc:latest mc ls minio/

echo "✅ Buckets reset. Next: run CDC (and optionally StarRocks setup) to repopulate Iceberg."
