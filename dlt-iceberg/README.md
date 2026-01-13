# DLT-Iceberg CDC Pipeline

Complete Kubernetes deployment for Change Data Capture (CDC) from PostgreSQL to Apache Iceberg using DLT.

## Architecture Overview

This deployment creates a complete data lakehouse stack with the following components:

```
PostgreSQL (Source)
    ↓ (WAL Replication Slot)
DLT Pipeline
    ↓ (CDC with Metadata Enrichment)
Apache Iceberg Tables
    ↓ (Stored as Parquet)
MinIO (Object Storage)
```

### Components

1. **PostgreSQL** - Source database with replication slot for CDC
2. **DLT Pipeline** - Extracts changes, adds metadata, writes to Iceberg
3. **Apache Iceberg** - Table format with ACID transactions and schema evolution
4. **MinIO** - S3-compatible object storage for Iceberg data

### Features

- ✅ **Real-time CDC**: Captures INSERT, UPDATE, DELETE operations via PostgreSQL replication
- ✅ **Metadata Enrichment**: Adds `extracted_at` and `deleted_at` fields to all records
- ✅ **Iceberg Partitioning**: Automatic partitioning by time and bucket strategies
- ✅ **Schema Evolution**: Automatic handling of schema changes in PostgreSQL
- ✅ **Soft Deletes**: Tracks deleted records with `deleted_at` timestamp
- ✅ **Kubernetes-Native**: Deployed on K8s with proper health checks and resource limits

## Quick Start

### Prerequisites

- Kubernetes cluster (kind, minikube, or cloud provider)
- kubectl configured
- docker CLI

### Deployment

1. **Deploy the stack**:

```bash
cd scripts
./deploy.sh
```

This script will:
- Build the DLT pipeline Docker image
- Create a kind cluster (if using kind)
- Deploy PostgreSQL, MinIO, and DLT pipeline
- Wait for all services to be ready

2. **Verify deployment**:

```bash
# Check all pods
kubectl get pods -n dlt-iceberg

# View DLT pipeline logs
kubectl logs -l app=dlt-pipeline -n dlt-iceberg -f
```

3. **Test CDC**:

```bash
# Connect to PostgreSQL
kubectl exec -it postgres-0 -n dlt-iceberg -- psql -U postgres -d dlt_data

# Make some changes
INSERT INTO users (username, email) VALUES ('test_user', 'test@example.com');
UPDATE users SET email = 'newemail@example.com' WHERE username = 'test_user';
DELETE FROM users WHERE username = 'test_user';

# Exit PostgreSQL
\q
```

4. **Check DLT logs for CDC capture**:

```bash
kubectl logs -l app=dlt-pipeline -n dlt-iceberg -f
```

## Project Structure

```
dlt-iceberg/
├── k8s/                          # Kubernetes manifests
│   ├── namespace.yaml
│   ├── postgres-deployment.yaml
│   ├── minio-deployment.yaml
│   ├── dlt-pipeline-deployment.yaml
│   └── kustomization.yaml
├── docker/
│   └── Dockerfile.dlt-pipeline   # DLT pipeline container
├── pipeline/
│   ├── pg_to_iceberg_pipeline.py # Main CDC pipeline code
│   ├── requirements.txt
│   └── .dlt/
│       ├── config.toml           # DLT configuration
│       └── secrets.toml          # DLT secrets (local dev only)
├── scripts/
│   ├── deploy.sh                 # Deployment automation
│   ├── cleanup.sh                # Cleanup script
│   └── kind-config.yaml          # kind cluster config
└── README.md
```

## Pipeline Details

### Metadata Fields

The pipeline automatically adds the following metadata fields to every record:

- **`extracted_at`**: ISO timestamp when the record was extracted from PostgreSQL
- **`deleted_at`**: ISO timestamp if the record was deleted (NULL for active records)
- **`_dlt_table_name`**: Source table name in PostgreSQL
- **`_dlt_change_type`**: Type of change (insert/update/delete)

### Iceberg Partitioning

Different tables use different partitioning strategies:

#### `users` table
- **Year partition**: On `created_at` column
- **Bucket partition**: 16 buckets on `username` column

#### `orders` table
- **Month partition**: On `order_date` column
- **Identity partition**: On `status` column

#### Custom tables
- Default: Identity partition on primary key

### PostgreSQL Replication

The pipeline uses PostgreSQL's logical replication feature:

- **Replication Slot**: `dlt_replication_slot`
- **Publication**: `dlt_publication`
- **Replication User**: `replication_user` (with REPLICATION privilege)

## Configuration

### Environment Variables

The DLT pipeline uses these environment variables (configured in `k8s/dlt-pipeline-deployment.yaml`):

| Variable | Description | Default |
|----------|-------------|---------|
| `POSTGRES_HOST` | PostgreSQL hostname | postgres |
| `POSTGRES_PORT` | PostgreSQL port | 5432 |
| `POSTGRES_DB` | Database name | dlt_data |
| `POSTGRES_USER` | Replication user | replication_user |
| `POSTGRES_PASSWORD` | Replication password | replication123 |
| `MINIO_ENDPOINT` | MinIO/S3 endpoint | http://minio:9000 |
| `ICEBERG_BUCKET` | S3 bucket for Iceberg data | iceberg-data |
| `SLOT_NAME` | Replication slot name | dlt_replication_slot |
| `PUB_NAME` | Publication name | dlt_publication |

### Accessing Services

#### PostgreSQL
```bash
# Port-forward to access from local machine
kubectl port-forward postgres-0 -n dlt-iceberg 5432:5432

# Connect
psql -h localhost -U postgres -d dlt_data
```

#### MinIO Console
```bash
# Port-forward
kubectl port-forward svc/minio -n dlt-iceberg 9001:9001

# Access at http://localhost:9001
# Credentials: minioadmin / minioadmin123
```

#### DLT Pipeline Logs
```bash
# Follow logs
kubectl logs -l app=dlt-pipeline -n dlt-iceberg -f

# View specific pod logs
kubectl logs <pod-name> -n dlt-iceberg
```

## Monitoring and Troubleshooting

### Check Pod Status
```bash
kubectl get pods -n dlt-iceberg
kubectl describe pod <pod-name> -n dlt-iceberg
```

### View DLT Pipeline State
```bash
# Enter the pipeline container
kubectl exec -it <dlt-pipeline-pod> -n dlt-iceberg -- bash

# Check DLT state
dlt pipeline pg_to_iceberg_cdc show
dlt pipeline pg_to_iceberg_cdc state
```

### Common Issues

**Issue**: Pipeline fails to connect to PostgreSQL
- **Solution**: Ensure PostgreSQL is ready and replication user has correct privileges

**Issue**: Replication slot already exists
- **Solution**: The pipeline handles this automatically, or manually reset:
  ```sql
  SELECT pg_drop_replication_slot('dlt_replication_slot');
  ```

**Issue**: Permission denied on MinIO
- **Solution**: Verify bucket exists and credentials are correct

## Development

### Local Testing

To test the pipeline locally without Kubernetes:

1. Start PostgreSQL and MinIO using Docker Compose
2. Install dependencies:
   ```bash
   pip install -r pipeline/requirements.txt
   ```
3. Run the pipeline:
   ```bash
   export POSTGRES_HOST=localhost
   export MINIO_ENDPOINT=http://localhost:9000
   python pipeline/pg_to_iceberg_pipeline.py
   ```

### Adding Custom Tables

To add a new table to the CDC pipeline:

1. Create the table in PostgreSQL:
   ```sql
   CREATE TABLE my_table (
       id SERIAL PRIMARY KEY,
       name VARCHAR(255)
   );
   ```

2. Add the table to the publication:
   ```sql
   ALTER PUBLICATION dlt_publication ADD TABLE my_table;
   ```

3. Configure partitioning in `pipeline/pg_to_iceberg_pipeline.py`:
   ```python
   if table_name == "my_table":
       resource = iceberg_adapter(
           iceberg_resource,
           partition=[
               iceberg_partition.identity("name"),
           ],
       )
   ```

4. Restart the DLT pipeline pod

## Cleanup

To remove all resources:

```bash
cd scripts
./cleanup.sh
```

This will:
- Delete all Kubernetes resources
- Delete the kind cluster (if using kind)

## Security Considerations

⚠️ **Important**: This deployment uses default passwords and secrets for demonstration. For production:

1. Use proper secret management (e.g., Sealed Secrets, Vault)
2. Change all default passwords
3. Enable TLS/SSL for all connections
4. Configure network policies
5. Use RBAC for Kubernetes access control
6. Enable PostgreSQL SSL connections
7. Use proper MinIO encryption

## Performance Tuning

### PostgreSQL Replication

- Adjust `wal_level` to `logical`
- Tune `max_wal_senders` and `max_replication_slots`
- Monitor replication slot lag

### DLT Pipeline

- Adjust `batch_size` in config
- Tune `max_parallel_load_items`
- Monitor memory usage

### Iceberg Partitioning

- Choose partition strategies based on query patterns
- Avoid too many small partitions
- Consider using `bucket` for high-cardinality columns

## References

- [DLT Documentation](https://dlthub.com/)
- [Apache Iceberg Documentation](https://iceberg.apache.org/docs/latest/)
- [PostgreSQL Logical Replication](https://www.postgresql.org/docs/current/logicaldecoding.html)
- [DLT PostgreSQL Replication Source](https://dlthub.com/docs/dlt-ecosystem/verified-sources/pg_replication)

## License

This deployment is provided as-is for demonstration and testing purposes.
