#!/usr/bin/env bash
# Stop all running Docker containers that are NOT part of this project (lakehouse/dlt-iceberg).
# Containers from docker-compose in this directory have project name "dlt-iceberg".
set -e
KEEP_PROJECT="${DOCKER_COMPOSE_PROJECT:-dlt-iceberg}"
STOPPED=0
for id in $(docker ps -q); do
  proj=$(docker inspect --format '{{index .Config.Labels "com.docker.compose.project"}}' "$id" 2>/dev/null || echo "")
  if [ "$proj" != "$KEEP_PROJECT" ]; then
    name=$(docker inspect --format '{{.Name}}' "$id" 2>/dev/null | sed 's/^\///')
    echo "Stopping (not $KEEP_PROJECT): $name"
    docker stop "$id" >/dev/null 2>&1 && STOPPED=$((STOPPED + 1))
  fi
done
echo "Stopped $STOPPED container(s) not in project $KEEP_PROJECT."
