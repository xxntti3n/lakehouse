# Quick Start Guide - DLT-Iceberg CDC Pipeline

This guide will help you get the PostgreSQL to Iceberg CDC pipeline running in 5 minutes.

## Prerequisites

- Docker installed
- Kubernetes cluster (kind recommended for local testing)
- kubectl configured

## Option 1: Deploy to Kubernetes (Recommended for testing)

### Step 1: Deploy the Stack

```bash
cd /Users/tien.nguyen6/Desktop/Cake/nttien/lakehouse/dlt-iceberg/scripts
./deploy.sh
```

This will:
- Build the DLT pipeline container
- Create a kind cluster
- Deploy PostgreSQL, MinIO, and DLT pipeline
- Configure all services

**Expected output**: All pods running
```
NAME                            READY   STATUS    RESTARTS   AGE
postgres-0                      1/1     Running   0          2m
minio-xxxxxx-xxxxx              1/1     Running   0          2m
dlt-pipeline-xxxxxxxxxx-xxxxx   1/1     Running   0          1m
```

### Step 2: Verify Deployment

```bash
# Check all pods are ready
kubectl get pods -n dlt-iceberg

# View DLT pipeline logs
kubectl logs -l app=dlt-pipeline -n dlt-iceberg -f
```

You should see logs indicating:
- PostgreSQL connection successful
- Replication slot initialized
- Listening for changes...

### Step 3: Test CDC

Run the test script to make changes in PostgreSQL:

```bash
cd /Users/tien.nguyen6/Desktop/Cake/nttien/lakehouse/dlt-iceberg/scripts
./test-cdc.sh
```

This will:
- INSERT a new user
- UPDATE the user's email
- INSERT an order
- UPDATE the order status

The DLT pipeline will capture these changes and write them to Iceberg.

### Step 4: Verify Data in Iceberg

Access MinIO to view the Iceberg tables:

```bash
# Port-forward MinIO console
kubectl port-forward svc/minio -n dlt-iceberg 9001:9001

# Open browser to http://localhost:9001
# Login: minioadmin / minioadmin123
# Navigate to: iceberg-data/iceberg_lakehouse/
```

You should see:
- `iceberg-data/iceberg_lakehouse/users/` - Users table data
- `iceberg-data/iceberg_lakehouse/orders/` - Orders table data

Each directory contains:
- `metadata/` - Iceberg metadata files
- `data/` - Parquet data files with partitioning

## Option 2: Local Development with Docker Compose

For local development without Kubernetes:

### Step 1: Start Services

```bash
cd /Users/tien.nguyen6/Desktop/Cake/nttien/lakehouse/dlt-iceberg
docker-compose up -d
```

### Step 2: Initialize Replication

```bash
# Run the pipeline
docker-compose exec dlt-pipeline python -c "
from dlt.sources.pg_replication import init_replication
import dlt

pipeline = dlt.pipeline(
    pipeline_name='source_pipeline',
    destination='postgres',
    dataset_name='dlt_data',
    credentials='postgresql://replication_user:replication123@postgres:5432/dlt_data'
)

init_replication(
    slot_name='dlt_replication_slot',
    pub_name='dlt_publication',
    credentials='postgresql://replication_user:replication123@postgres:5432/dlt_data',
    schema_name='public',
    table_names=None,
    reset=True
)
"
```

### Step 3: Start the Pipeline

```bash
docker-compose exec dlt-pipeline python pg_to_iceberg_pipeline.py
```

## Understanding the Data Flow

### 1. PostgreSQL Changes

```sql
-- Connect to PostgreSQL
kubectl exec -it postgres-0 -n dlt-iceberg -- psql -U postgres -d dlt_data

-- Make a change
INSERT INTO users (username, email) VALUES ('alice', 'alice@example.com');
```

### 2. CDC Capture

The DLT pipeline captures this change via the replication slot:

```
[INFO] Captured change: INSERT on users
  id: 4
  username: alice
  email: alice@example.com
```

### 3. Metadata Enrichment

The pipeline adds metadata fields:

```json
{
  "id": 4,
  "username": "alice",
  "email": "alice@example.com",
  "extracted_at": "2025-01-12T10:30:45.123456+00:00",
  "deleted_at": null,
  "_dlt_table_name": "users",
  "_dlt_change_type": "insert"
}
```

### 4. Iceberg Write

Data is written to Iceberg with partitioning:

```
iceberg-data/iceberg_lakehouse/users/data/
└── created_at_year=2025/
    └── username_bucket=12/
        └── part-00000.parquet  <- Contains alice's record
```

## Common Operations

### Add a New Table

```sql
-- In PostgreSQL
CREATE TABLE products (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255),
    price DECIMAL(10, 2),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Add to publication
ALTER PUBLICATION dlt_publication ADD TABLE products;
```

Then update `pipeline/pg_to_iceberg_pipeline.py` to add partitioning for the new table.

### View Pipeline State

```bash
# Enter the pipeline pod
kubectl exec -it <dlt-pipeline-pod> -n dlt-iceberg -- bash

# View pipeline state
dlt pipeline pg_to_iceberg_cdc show
dlt pipeline pg_to_iceberg_cdc state
```

### Reset the Pipeline

```sql
-- Drop replication slot
SELECT pg_drop_replication_slot('dlt_replication_slot');

-- Drop publication
DROP PUBLICATION dlt_publication;
```

Then restart the DLT pipeline pod.

## Troubleshooting

### Issue: "Replication slot already exists"

**Solution**: The pipeline handles this automatically. If you need to reset:

```sql
-- In PostgreSQL
SELECT pg_drop_replication_slot('dlt_replication_slot');
```

### Issue: Pipeline not capturing changes

**Check 1**: Is the publication created?
```sql
SELECT pubname FROM pg_publication WHERE pubname = 'dlt_publication';
```

**Check 2**: Is the table in the publication?
```sql
SELECT * FROM pg_publication_tables WHERE pubname = 'dlt_publication';
```

**Check 3**: View DLT logs
```bash
kubectl logs -l app=dlt-pipeline -n dlt-iceberg -f
```

### Issue: Permission denied on MinIO

**Solution**: Verify credentials and bucket exists:

```bash
# Check MinIO is accessible
kubectl exec -it minio-0 -n dlt-iceberg -- mc alias set local http://localhost:9000 minioadmin minioadmin123

# List buckets
kubectl exec -it minio-0 -n dlt-iceberg -- mc ls local/
```

## Next Steps

1. **Customize partitioning**: Edit `pipeline/pg_to_iceberg_pipeline.py` to add your own tables
2. **Add more tables**: Create tables in PostgreSQL and add them to the publication
3. **Scale up**: Increase DLT pipeline replicas for higher throughput
4. **Production hardening**:
   - Use proper secrets (Sealed Secrets, Vault)
   - Enable TLS/SSL
   - Configure monitoring and alerting
   - Set up network policies

## Cleanup

```bash
cd /Users/tien.nguyen6/Desktop/Cake/nttien/lakehouse/dlt-iceberg/scripts
./cleanup.sh
```

## Additional Resources

- [Full README](../README.md) - Complete documentation
- [Architecture](../docs/ARCHITECTURE.md) - Deep dive into the pipeline
- [DLT Documentation](https://dlthub.com/) - DLT framework docs
- [Iceberg Documentation](https://iceberg.apache.org/docs/latest/) - Apache Iceberg docs
