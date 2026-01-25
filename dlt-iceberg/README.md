# DLT to Iceberg Pipeline

## Overview

This DLT pipeline loads data from MySQL (`products` and `sales` tables) to Iceberg-compatible Parquet files stored in MinIO S3 (`dlt-warehouse` bucket).

## Architecture

```
MySQL (Source) → DLT Pipeline → MinIO S3 (dlt-warehouse)
                        ↓
                  Parquet Files
```

## Prerequisites

- Docker and Docker Compose installed
- Running Flink CDC pipeline (for source MySQL data)
- MinIO service available

## Quick Start

### 1. Start the Base Infrastructure

First, ensure the base services (MySQL, MinIO) are running:

```bash
cd /Users/tien.nguyen6/Desktop/Cake/nttien/lakehouse/flink_iceberg
docker-compose up -d mysql minio mc
```

### 2. Run the DLT Pipeline

```bash
cd /Users/tien.nguyen6/Desktop/Cake/nttien/lakehouse/dlt-iceberg

# Build and run the pipeline
docker-compose up --build
```

The pipeline will:
1. Create the `dlt-warehouse` bucket in MinIO
2. Extract data from MySQL (`products` and `sales` tables)
3. Load data into MinIO as Parquet files

### 3. Verify the Data

Check MinIO console at http://localhost:9001:
- Login: minio / minio123
- Navigate to `dlt-warehouse` bucket
- You should see:
  - `products/` directory with Parquet files
  - `sales/` directory with Parquet files

Or use the MinIO client:

```bash
docker exec -it mc mc ls /data/dlt-warehouse/
docker exec -it mc mc ls /data/dlt-warehouse/products/
docker exec -it mc mc ls /data/dlt-warehouse/sales/
```

## Pipeline Details

### Source Tables

**products** table:
- `id` (INT, PRIMARY KEY)
- `sku` (VARCHAR(64))
- `name` (VARCHAR(128))

**sales** table:
- `id` (BIGINT, PRIMARY KEY)
- `product_id` (INT)
- `qty` (INT)
- `price` (DECIMAL(10,2))
- `sale_ts` (TIMESTAMP)

### Destination Structure

Data is written to: `s3://dlt-warehouse/`

```
dlt-warehouse/
├── products/
│   ├── products_YYYYMMDDHHMMSS_000.parquet
│   └── _dlt_pipeline_state/
└── sales/
    ├── sales_YYYYMMDDHHMMSS_000.parquet
    └── _dlt_pipeline_state/
```

## Incremental Loading

The pipeline uses **merge** disposition:
- New records are appended
- Existing records (matched by primary key) are updated
- No duplicate records

## Rerun the Pipeline

To reload data or update with new changes:

```bash
docker-compose up --build --force-recreate
```

## Troubleshooting

### Pipeline fails to connect to MySQL

Ensure MySQL is running:
```bash
docker-compose -f ../flink_iceberg/docker-compose.yml ps mysql
```

### Bucket creation fails

Check MinIO is running:
```bash
docker-compose -f ../flink_iceberg/docker-compose.yml ps minio
```

### No data appears in bucket

Check DLT pipeline logs:
```bash
docker logs dlt-pipeline
```

## Integration with Existing Setup

This DLT pipeline:
- ✅ Uses the same MySQL database as Flink CDC
- ✅ Writes to a separate bucket (`dlt-warehouse`) to avoid conflicts
- ✅ Complements the Flink CDC → Iceberg pipeline
- ✅ Provides batch loading alternative to streaming

## Differences from Flink CDC

| Feature | DLT Pipeline | Flink CDC |
|---------|--------------|-----------|
| Type | Batch loading | Streaming/CDC |
| Latency | Manual/on-demand | Real-time (sub-second) |
| Format | Parquet files | Iceberg tables |
| Schema Evolution | Automatic | Manual SQL |
| Use Case | Periodic bulk loads | Continuous sync |

## Next Steps

- Schedule the pipeline to run periodically (cron, Airflow)
- Add data validation and quality checks
- Configure DLT transformations for business logic
- Set up monitoring and alerts
