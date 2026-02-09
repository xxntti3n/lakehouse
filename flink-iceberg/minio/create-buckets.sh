#!/bin/sh

###############################################################################
# MinIO Bucket Creation Script
# Creates buckets for Iceberg warehouse and Flink checkpoints
###############################################################################

set -e

# Wait for MinIO to be ready
sleep 5

# Configure MinIO client
mc alias set minio http://minio:9000 minio minio123

# Create buckets
echo "Creating MinIO buckets..."

# Warehouse bucket (for Iceberg tables)
mc mb minio/warehouse --ignore-existing

# Flink checkpoints bucket
mc mb minio/flink-checkpoints --ignore-existing

# Set public policy (for development only!)
mc anonymous set download minio/warehouse
mc anonymous set download minio/flink-checkpoints

echo "✓ Buckets created successfully!"
echo ""
echo "Available buckets:"
mc ls minio/
