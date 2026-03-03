#!/usr/bin/env bash
# Build pipeline image with legacy Docker builder to avoid Colima/containerd
# "lease does not exist: not found" errors during layer export.
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"
echo "Pruning build cache (optional)..."
docker builder prune -f 2>/dev/null || true
echo "Building with legacy builder (DOCKER_BUILDKIT=0)..."
export DOCKER_BUILDKIT=0
export COMPOSE_DOCKER_CLI_BUILD=0
docker-compose build --no-cache
echo "Done. Start stack with: docker-compose up -d"
