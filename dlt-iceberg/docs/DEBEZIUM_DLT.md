# Debezium-Style DLT CDC Connector

Real-time Change Data Capture from MySQL to MinIO using Debezium-style architecture with Iceberg checkpointing.

## 🎯 Overview

This is a **production-grade CDC connector** inspired by Debezium, adapted for DLT (instead of Kafka) with Iceberg-based offset storage in MinIO.

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     MySQL Server                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Binlog     │  │    GTID      │  │   Database   │      │
│  │  (Events)    │  │   Tracking   │  │   Tables     │      │
│  └──────┬───────┘  └──────┬───────┘  └──────────────┘      │
└─────────┼─────────────────┼──────────────────────────────┘
          │                 │
          │ Binlog Stream   │
          ▼                 ▼
┌─────────────────────────────────────────────────────────────┐
│            Debezium DLT Connector                           │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Phase 1: Snapshot                                   │  │
│  │  - Initial consistent snapshot                       │  │
│  │  - Or incremental snapshot (non-blocking)            │  │
│  │  - Records schema in SchemaHistory                   │  │
│  └──────────────────────────────────────────────────────┘  │
│           │                                                  │
│           ▼                                                  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Phase 2: Streaming                                  │  │
│  │  - Reads MySQL binlog via pymysqlreplication        │  │
│  │  - Emits ChangeEvent for each change                 │  │
│  │  - Updates offset in OffsetStore                     │  │
│  └──────────────────────────────────────────────────────┘  │
│           │                                                  │
│           ├──────────────────────────────────────────────┤
│           ▼                                                  │
│  ┌────────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │  OffsetStore   │  │ SchemaHistory│  │    DLT      │  │
│  │  (Iceberg)     │  │  (Iceberg)   │  │  Pipeline    │  │
│  └────────────────┘  └──────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
                  ┌──────────────┐
                  │    MinIO     │
                  │ (Iceberg)    │
                  └──────────────┘
```

## ✨ Key Features

### 1. **Real-time Binlog Streaming**
- Uses `pymysqlreplication` to read MySQL binlog
- Captures INSERT, UPDATE, DELETE operations
- GTID-based tracking for accurate positioning
- No polling - true event streaming

### 2. **Snapshot Modes**
- **Initial**: Full blocking snapshot (simple, reliable)
- **Incremental**: Non-blocking snapshot with GTID watermarks (production-safe)
- **Schema Only**: Capture schema without data
- **Never**: Start streaming from offset only

### 3. **Checkpoint Storage in Iceberg**
- **OffsetStore**: Stores GTID positions and binlog offsets
- **SchemaHistory**: Tracks schema evolution over time
- Stored in separate MinIO bucket: `s3://dlt-checkpoints/`
- Queryable with DuckDB

### 4. **Transaction Awareness**
- Tracks GTID of each transaction
- Preserves transaction boundaries
- Handles multi-server GTID sets

### 5. **Schema Evolution**
- Automatic schema detection
- Schema versioning
- Schema history stored in Iceberg

### 6. **Debezium-Compatible Events**
Each change event includes:
```json
{
  "_op": "c|u|d|r",        // Operation: create, update, delete, read
  "_ts": "2025-...",        // Timestamp
  "_db": "appdb",           // Database
  "_table": "products",     // Table
  "_cdc_server_id": "uuid", // MySQL server UUID
  "_cdc_gtid": "uuid:1-100",// GTID position
  "_cdc_binlog_file": "...",// Binlog file
  "_cdc_binlog_pos": 123,   // Binlog position
  "_tx_id": "...",          // Transaction ID
  // ... plus actual row data
}
```

## 🚀 Quick Start

See main [README](../README.md). Minimal: `docker-compose up -d --build`.

## 🔧 Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MYSQL_HOST` | mysql-source | MySQL host |
| `MYSQL_PORT` | 3306 | MySQL port |
| `MYSQL_USER` | root | MySQL user |
| `MYSQL_PASSWORD` | rootpw | MySQL password |
| `MYSQL_DATABASE` | appdb | MySQL database |
| `CHECKPOINT_BUCKET` | dlt-checkpoints | MinIO bucket for checkpoints |
| `DEST_BUCKET` | dlt-warehouse | MinIO bucket for CDC data |
| `DATASET_NAME` | debezium_cdc | DLT dataset name |
| `SNAPSHOT_MODE` | initial | Snapshot mode |

### Python Configuration

```python
from debezium_dlt import DebeziumConfig, DebeziumDLTConnector

config = DebeziumConfig(
    table_include_list=['appdb.products', 'appdb.sales'],
    snapshot_mode='incremental',
    gtid_source_include='uuid1,uuid2',  # Optional
)
connector = DebeziumDLTConnector(config)
connector.run_cdc()
```

## 📁 Storage Structure

```
MinIO (dlt-checkpoints) → offsets/, schema_history/
MinIO (dlt-warehouse)   → debezium_cdc/cdc_events/
```

## ⚠️ Troubleshooting

- **No module named 'pymysqlreplication'**: `docker-compose build debezium-cdc`
- **GTID not enabled**: `SHOW VARIABLES LIKE 'gtid_mode';` should be ON
- **Offset not saving**: Ensure bucket exists; run `docker exec minio-storage /setup-checkpoints.sh`

---

**Status**: ✅ Implemented | **Version**: 1.0.0
