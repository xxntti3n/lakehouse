#!/bin/bash
set -e
# Wait for FE to be ready to accept backend registration, then start BE.
# Backend is registered by starrocks-init service.
echo "Waiting 25s for FE to register this backend..."
sleep 25
echo "Starting StarRocks BE..."
exec /opt/starrocks/be/bin/start_be.sh
