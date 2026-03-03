# DLT Native Iceberg Pipeline

**Architecture:** DLT pipeline reads CDC from MySQL → writes **native Iceberg format** via DLT's Iceberg destination → Nessie catalog stores metadata → MinIO stores data files → StarRocks queries via Nessie.

## 🎯 Overview

- **MySQL** (source): binlog CDC with GTID for change data capture
- **DLT Pipeline**: Snapshot + streaming using **DLT native Iceberg destination**
- **Nessie**: Iceberg REST catalog for table metadata
- **MinIO**: S3-compatible storage for Iceberg data files
- **StarRocks**: Queries Iceberg tables via Nessie catalog
- **Native Iceberg Format**: Proper metadata.json, manifests, and Parquet data files

## 📊 Architecture

```
                    ┌─────────────┐
                    │   MySQL     │  binlog CDC
                    │  (source)   │
                    └──────┬──────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│  DLT Pipeline with Native Iceberg Destination                    │
│  - Snapshot initial data to Iceberg                             │
│  - Stream binlog changes to Iceberg                             │
│  - Each table gets proper schema (not generic CDC schema)        │
│  - Automatic partitioning by timestamp                          │
└───────────────────────────────┬──────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       Nessie Catalog                                │
│  REST API: http://nessie:19120/iceberg                            │
│  - Stores table metadata                                          │
│  - Manages snapshots                                              │
│  - Handles schema evolution                                       │
└───────────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        MinIO (S3)                                    │
│  Warehouse: s3://dlt-warehouse/iceberg                              │
│  - appdb/products/ (metadata + data)                               │
│  - appdb/sales/ (metadata + data)                                  │
│  - Proper Iceberg format with metadata.json, manifests             │
└─────────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      StarRocks (--profile analytics)               │
│  - Queries Iceberg tables via Nessie catalog                      │
│  - Same data, single source of truth                               │
└─────────────────────────────────────────────────────────────────────┘
```

## 🚀 Quick Start

### Prerequisites
- Colima or Docker Desktop
- Docker Compose

### Start All Services

```bash
cd lakehouse/dlt-iceberg
docker-compose up -d --build
```

This starts:
- **MySQL** - Source database with sample data
- **MinIO** - S3-compatible object storage
- **Nessie** - Iceberg REST catalog (enabled by default)
- **Debezium DLT** - CDC pipeline writing to Iceberg
- **Data Generator** - Random data changes every minute

### Add StarRocks (optional)

```bash
docker-compose --profile analytics up -d
```

## 📁 Iceberg Format in MinIO

With the updated pipeline, you'll see proper Iceberg format:

```
s3://dlt-warehouse/iceberg/
└── appdb/
    ├── products/
    │   ├── metadata/
    │   │   ├── v1.metadata.json      ← Table metadata
    │   │   ├── v2.metadata.json
    │   │   └── snap-1-*.avro          ← Manifest list
    │   └── data/
    │       ├── part-00000-*.parquet  ← Data files
    │       └── part-00001-*.parquet
    └── sales/
        ├── metadata/
        │   └── v1.metadata.json
        └── data/
            └── part-00000-*.parquet
```

### Verify Iceberg Format

```bash
# Run verification script
docker exec -it debezium-dlt-connector python /app/scripts/verify_iceberg.py

# Or check MinIO console
# Browse to: dlt-warehouse/iceberg/appdb/
# You should see metadata/ directories with .metadata.json files
```

## 🔧 Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| MYSQL_HOST | mysql | MySQL host |
| MYSQL_PORT | 3306 | MySQL port |
| MYSQL_DATABASE | appdb | Source database |
| NESSIE_ICEBERG_URI | http://nessie:19120/iceberg | Iceberg REST catalog |
| ICEBERG_WAREHOUSE | s3://dlt-warehouse/iceberg | Warehouse location |
| ICEBERG_NAMESPACE | appdb | Default namespace |
| TABLE_INCLUDE_LIST | appdb.products,appdb.sales | Tables to capture |
| SNAPSHOT_MODE | initial | initial or never |
| STREAMING_MAX_EVENTS | 10000 | Max streaming events per run |

## 📊 Table Schemas

### Products Table
- id: bigint (primary key)
- name: varchar
- description: varchar
- price: decimal
- stock: int
- category: varchar
- created_at: timestamp
- updated_at: timestamp
- __op: varchar (CDC: r, c, u_old, u_new, d)
- __ts_ms: bigint (CDC timestamp)
- __source: varchar (snapshot/binlog)

### Sales Table
- id: bigint (primary key)
- product_id: bigint
- quantity: int
- total: decimal
- customer_name: varchar
- sale_date: timestamp
- created_at: timestamp
- updated_at: timestamp
- __op, __ts_ms, __source (CDC metadata)

## 🔍 Verification

```bash
# Verify Iceberg tables
docker exec -it debezium-dlt-connector python scripts/verify_iceberg.py

# Check Nessie API
curl http://localhost:19120/api/v2/trees

# Query with StarRocks (after --profile analytics)
docker exec -it starrocks-fe mysql -h 127.0.0.1 -P 9030 -u root -e \
  "SET CATALOG iceberg_nessie; USE appdb; SHOW TABLES; SELECT * FROM products;"
```

---

**Last Updated**: February 2025
**Status**: Native Iceberg Format ✅
