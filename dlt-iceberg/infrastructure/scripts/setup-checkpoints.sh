#!/bin/bash
# Setup checkpoint buckets for Debezium DLT connector

echo "Setting up checkpoint buckets in MinIO..."

# Wait for MinIO to be ready
sleep 5

# Create checkpoint bucket
docker exec minio-storage mc alias set local http://localhost:9000 minio minio123 2>/dev/null

echo "Creating checkpoint bucket..."
docker exec minio-storage mc mb local/dlt-checkpoints --ignore-existing 2>/dev/null

echo "Creating warehouse bucket (DLT/Iceberg destination)..."
docker exec minio-storage mc mb local/dlt-warehouse --ignore-existing 2>/dev/null

echo "Creating offset storage path..."
docker exec minio-storage mc mkdir -p local/dlt-checkpoints/offsets 2>/dev/null

echo "Creating schema history path..."
docker exec minio-storage mc mkdir -p local/dlt-checkpoints/schema_history 2>/dev/null

echo "✅ Checkpoint bucket setup complete!"
echo ""
echo "Buckets:"
docker exec minio-storage mc ls local/

echo ""
echo "Checkpoint bucket contents:"
docker exec minio-storage mc tree local/dlt-checkpoints/
