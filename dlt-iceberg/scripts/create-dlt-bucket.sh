#!/bin/sh
# Create dlt-warehouse bucket in MinIO

set -e

echo "Waiting for MinIO to be ready..."
until mc alias set minio http://minio:9000 minio minio123 >/dev/null 2>&1; do
  echo "MinIO is unavailable - sleeping"
  sleep 1
done

echo "MinIO is ready!"
echo "Creating bucket: dlt-warehouse"

# Create bucket if it doesn't exist
mc mb /data/dlt-warehouse --ignore-existing 2>/dev/null || true

# Set bucket policy to public read-write (needed for Iceberg metadata)
mc anonymous set public /data/dlt-warehouse 2>/dev/null || true

echo "✓ Bucket dlt-warehouse created successfully"
echo "Bucket info:"
mc ls /data/
