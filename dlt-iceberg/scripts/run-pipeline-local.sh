#!/bin/bash

# Set environment variables for local testing
export POSTGRES_HOST=localhost
export POSTGRES_PORT=5432
export POSTGRES_DB=dlt_data
export POSTGRES_USER=replication_user
export POSTGRES_PASSWORD=replication123

export MINIO_ENDPOINT=http://localhost:9000
export ICEBERG_BUCKET=iceberg-data
export MINIO_ACCESS_KEY=minioadmin
export MINIO_SECRET_KEY=minioadmin123

export SLOT_NAME=dlt_replication_slot
export PUB_NAME=dlt_publication

# Activate virtual environment and run pipeline
cd /Users/tien.nguyen6/Desktop/Cake/nttien/lakehouse/dlt-iceberg/pipeline
source .venv/bin/activate
python pg_to_iceberg_pipeline.py
