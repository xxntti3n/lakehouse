# Architecture - DLT-Iceberg CDC Pipeline

## Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                         PostgreSQL                               │
│  ┌──────────────┐         ┌──────────────────────────────────┐  │
│  │ Source Tables│  WAL →  │ Replication Slot                 │  │
│  │              │ ───────►│ (dlt_replication_slot)           │  │
│  │ - users      │         │ - Changes captured via pgoutput  │  │
│  │ - orders     │         │ - Logical decoding               │  │
│  └──────────────┘         └──────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ Logical Replication Stream
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      DLT Pipeline Pod                            │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ 1. replication_resource()                                │  │
│  │    - Reads from replication slot                         │  │
│  │    - Yields change data items                            │  │
│  └──────────────────────────────────────────────────────────┘  │
│                              │                                  │
│                              ▼                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ 2. enrich_with_metadata()                                │  │
│  │    For each record:                                      │  │
│  │    - Add extracted_at timestamp                         │  │
│  │    - Add deleted_at (if delete)                          │  │
│  │    - Add _dlt_table_name                                 │  │
│  │    - Add _dlt_change_type                                │  │
│  └──────────────────────────────────────────────────────────┘  │
│                              │                                  │
│                              ▼                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ 3. iceberg_adapter()                                     │  │
│  │    - Configure partitioning                              │  │
│  │    - Apply Iceberg table hints                           │  │
│  └──────────────────────────────────────────────────────────┘  │
│                              │                                  │
│                              ▼                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ 4. Filesystem Destination (Iceberg)                      │  │
│  │    - Normalize to Arrow/Parquet                          │  │
│  │    - Write to Iceberg table                              │  │
│  │    - Ephemeral SQLite catalog                            │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ S3 Protocol
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                          MinIO                                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Bucket: iceberg-data                                      │  │
│  │                                                            │  │
│  │ iceberg-data/                                              │  │
│  │   └── iceberg_lakehouse/                                   │  │
│  │       └── users/                                           │  │
│  │           ├── metadata/                                    │  │
│  │           │   └── ... Iceberg metadata files             │  │
│  │           └── data/                                        │  │
│  │               └── ... Parquet data files                  │  │
│  │       └── orders/                                          │  │
│  │           ├── metadata/                                    │  │
│  │           └── data/                                        │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## Component Details

### 1. PostgreSQL (Source Database)

**Configuration**:
- Version: 16-alpine
- WAL Level: Logical (required for CDC)
- Replication Slot: `dlt_replication_slot`
- Publication: `dlt_publication`
- Replication User: `replication_user` with REPLICATION privilege

**Tables**:
```sql
-- Users table with temporal partitioning
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(255),
    email VARCHAR(255),
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

-- Orders table with date-based partitioning
CREATE TABLE orders (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    amount DECIMAL(10, 2),
    status VARCHAR(50),
    order_date DATE
);
```

**Replication Setup**:
```sql
-- Create replication user
CREATE ROLE replication_user WITH LOGIN REPLICATION PASSWORD 'replication123';

-- Grant permissions
GRANT CREATE ON DATABASE dlt_data TO replication_user;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO replication_user;

-- Create publication
CREATE PUBLICATION dlt_publication FOR TABLE users, orders;
```

### 2. DLT Pipeline

**Key Components**:

#### a. replication_resource()
```python
replication = replication_resource(
    slot_name="dlt_replication_slot",
    pub_name="dlt_publication",
    credentials="postgresql://replication_user:***@postgres:5432/dlt_data",
    target_batch_size=1000,
    flush_slot=True  # Remove processed messages
)
```

**How it works**:
- Connects to PostgreSQL replication slot
- Streams WAL log entries
- Yields data items with change information
- Each item includes: old values, new values, change type

#### b. Metadata Enrichment
```python
def enrich_with_metadata(data_item, table_name):
    return {
        **data_item,
        "extracted_at": datetime.now(timezone.utc).isoformat(),
        "deleted_at": datetime.now(timezone.utc).isoformat()
                       if change_type == "delete" else None,
        "_dlt_table_name": table_name,
        "_dlt_change_type": change_type,
    }
```

**Output example**:
```json
{
  "id": 1,
  "username": "john_doe",
  "email": "john@example.com",
  "extracted_at": "2025-01-12T10:30:45.123456+00:00",
  "deleted_at": null,
  "_dlt_table_name": "users",
  "_dlt_change_type": "insert"
}
```

#### c. Iceberg Partitioning

**Users Table**:
```python
partition=[
    iceberg_partition.year("created_at"),      # Partition by year
    iceberg_partition.bucket(16, "username"),  # 16 buckets
]
```

**Orders Table**:
```python
partition=[
    iceberg_partition.month("order_date"),    # Partition by month
    iceberg_partition.identity("status"),      # Exact value partition
]
```

**How partitioning affects storage**:
```
iceberg-data/iceberg_lakehouse/users/data/
├── created_at_year=2024/
│   ├── username_bucket=0/
│   │   └── part-00000.parquet
│   ├── username_bucket=1/
│   └── ...
└── created_at_year=2025/
    └── ...
```

#### d. Write Disposition
- **Mode**: `merge` with `upsert` strategy
- **Primary Key**: `id`
- **Behavior**:
  - INSERT: New rows added
  - UPDATE: Existing rows updated based on primary key
  - DELETE: `deleted_at` timestamp set (soft delete)

### 3. Apache Iceberg (Table Format)

**Implementation in DLT**:
- Uses PyIceberg library
- Ephemeral SQLite catalog (created on-demand)
- Parquet file format for data storage

**Metadata Files**:
```
metadata/
├── v1.metadata.json        # Initial table metadata
├── v2.metadata.json        # After first snapshot
├── snap-1.avro             # Snapshot manifest
└── ...
```

**Schema Evolution**:
```python
# DLT automatically handles schema changes
with table.update_schema() as update:
    update.union_by_name(new_schema)
    update.commit()
```

**Partition Evolution**:
- ⚠️ Not currently supported in DLT
- Partition specs must be defined before table creation

### 4. MinIO (Object Storage)

**S3 API Compatibility**:
- Endpoint: `http://minio:9000`
- Access via `s3://` protocol in DLT
- Bucket: `iceberg-data`

**Storage Structure**:
```
s3://iceberg-data/iceberg_lakehouse/
├── users/
│   ├── metadata/
│   │   ├── 00000-<uuid>.metadata.json
│   │   └── snap-<uuid>.avro
│   └── data/
│       ├── created_at_year=2024/
│       │   └── username_bucket=5/
│       │       └── part-00000.parquet
│       └── created_at_year=2025/
└── orders/
    ├── metadata/
    └── data/
        ├── order_date_month=2024-01/
        │   └── status=completed/
        │       └── part-00000.parquet
        └── order_date_month=2024-02/
```

## Change Data Capture Flow

### 1. Initial Load (Optional)
```python
# If persist_snapshots=True
initial_load = init_replication(
    slot_name="dlt_replication_slot",
    pub_name="dlt_publication",
    persist_snapshots=True  # Captures current table state
)
```

### 2. Continuous Replication
```python
# Stream changes from WAL
replication = replication_resource(
    slot_name="dlt_replication_slot",
    pub_name="dlt_publication"
)

# Each change yields:
{
  "old": {"id": 1, "username": "old_name"},  # For UPDATE/DELETE
  "new": {"id": 1, "username": "new_name"},  # For INSERT/UPDATE
  "change_type": "update"                    # insert/update/delete
}
```

### 3. Metadata Enrichment
```python
# Transform adds:
- extracted_at: "2025-01-12T10:30:45Z"
- deleted_at: "2025-01-12T10:30:45Z" (if delete)
- _dlt_table_name: "users"
- _dlt_change_type: "update"
```

### 4. Iceberg Write
```python
# Upsert based on primary key
table.upsert(
    df=data,
    join_cols=["id"],
    when_matched_update_all=True,
    when_not_matched_insert_all=True
)
```

## Partition Transformations

### 1. Identity
- **Use Case**: Low cardinality columns (status, category)
- **Behavior**: Exact value partitioning
- **Example**: `status = 'completed'` → `status=completed/`

### 2. Year
- **Use Case**: Date/timestamp columns
- **Behavior**: Extracts year from date
- **Example**: `2025-01-15` → `created_at_year=2025/`

### 3. Month
- **Use Case**: Date/timestamp columns
- **Behavior**: Extracts year and month
- **Example**: `2025-01-15` → `order_date_month=2025-01/`

### 4. Bucket
- **Use Case**: High cardinality columns (user_id, username)
- **Behavior**: Hash value into N buckets
- **Example**: Hash(`username`) % 16 → `username_bucket=5/`

### 5. Truncate
- **Use Case**: String columns
- **Behavior**: Truncate to N characters
- **Example**: `ELECTRONICS` → `category_trunc_3=ELE/`

## Performance Considerations

### 1. PostgreSQL Replication
- **Slot Lag**: Monitor replication slot size
- **WAL Retention**: Ensure enough disk space
- **Network**: Low latency between Postgres and DLT pod

### 2. DLT Pipeline
- **Batch Size**: 1000 items/batch (configurable)
- **Parallelism**: 3 parallel load items (configurable)
- **Memory**: 512Mi-1Gi per pod

### 3. Iceberg/MinIO
- **File Size**: Aim for 128MB-1GB Parquet files
- **Partition Pruning**: Design partitions for query patterns
- **Metadata Caching**: Iceberg client caches metadata

## Monitoring

### Key Metrics
- Replication slot lag size
- DLT pipeline throughput (rows/sec)
- Iceberg snapshot size
- MinIO storage usage
- Pod resource usage (CPU/Memory)

### Alerts
- Replication slot lag > threshold
- Pipeline pod restarts
- MinIO disk space > 80%
- Failed transactions

## Security

### Authentication
- PostgreSQL: Password-based (use SSL in production)
- MinIO: Access key/secret key
- DLT: Secrets from K8s secrets

### Authorization
- PostgreSQL replication user: REPLICATION privilege only
- MinIO bucket policies: Restrict access
- K8s RBAC: Pod service accounts

### Network
- Network policies: Restrict pod-to-pod communication
- Service mesh: Consider for production deployments
