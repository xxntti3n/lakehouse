# Flink CDC Checkpoint Storage - Visual Guide

## **Complete Architecture Diagram**

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          LAKEHOUSE ARCHITECTURE                         │
└─────────────────────────────────────────────────────────────────────────┘

┌──────────────┐     CDC      ┌──────────────┐      Transform      ┌─────────────┐
│    MySQL     │ ──────────►  │ Flink SQL    │ ─────────────────►  │   Iceberg   │
│              │   Binlog     │   Streaming  │   Enriched Data    │  (MinIO/S3)  │
│  - sales     │              │              │                      │             │
│  - products  │              │  ┌────────┐  │  ┌────────────────┐ │ Parquet     │
│              │              │  │ CDC    │  │  │  Join         │ │             │
│  Binlog:     │              │  │ Source │──┼─►│  sales +      │ │             │
│  mysql-bin.  │              │  │        │  │  │  products     │ │             │
│  000003     │              │  └───────┘  │  └────────────────┘ │             │
│              │              │              │                      │             │
└──────────────┘              └──────┬───────┘                      └──────┬──────┘
                                     │                                     │
                                     │ ────────────────────────────────────┘
                                     │
                    ┌────────────────┴────────────────┐
                    │                                 │
                    ↓ CHECKPOINT STORAGE              ↓
         ┌──────────────────────┐          ┌──────────────────┐
         │   MinIO (S3)         │          │     Trino        │
         │                      │          │   Query Layer    │
         │ s3://flink-checkpoints/         │                  │
         │  └── chk-123/         │          │  - BI Tools      │
         │      ├── metadata     │          │  - Analytics     │
         │      └── shared/      │          │  - Dashboards    │
         │          └── state    │          └──────────────────┘
         │                      │
         └──────────────────────┘
```

---

## **Checkpoint Flow (Detailed)**

```
TIME: Every 30 seconds (configurable)

┌────────────────────────────────────────────────────────────────────┐
│ FLINK JOBMANAGER                                                  │
│                                                                    │
│  1. Trigger Checkpoint                                            │
│     - Sends "checkpoint barrier" to all operators                  │
│     - Checkpoint ID: 123                                           │
└────────────────────────┬───────────────────────────────────────────┘
                         │
                    ↓ broadcasts
┌────────────────────────────────────────────────────────────────────┐
│ FLINK TASKMANAGER (s)                                             │
│                                                                    │
│  2. Receive Checkpoint Barrier                                    │
│     - Pause processing                                             │
│     - Snapshot state:                                             │
│       ├─ MySQL CDC binlog position: (mysql-bin.000003, pos: 456789)
│       ├─ Join state: {1: "Laptop", 2: "Mouse", ...}              │
│       └─ Aggregation state: {count: 1234, sum: 56789}            │
│     - Write to local RocksDB: /tmp/flink-rocksdb/chk-123/         │
│                                                                    │
│  3. Upload to MinIO                                               │
│     - PUT s3://flink-checkpoints/checkpoints/chk-123/metadata     │
│     - PUT s3://flink-checkpoints/checkpoints/chk-123/shared/...   │
│                                                                    │
│  4. Acknowledge JobManager                                        │
│     - "Checkpoint 123 completed"                                   │
└────────────────────────┬───────────────────────────────────────────┘
                         │
                    ↓ acknowledgment
┌────────────────────────────────────────────────────────────────────┐
│ FLINK JOBMANAGER                                                  │
│                                                                    │
│  5. Confirm Checkpoint                                            │
│     - Mark checkpoint 123 as COMPLETED                             │
│     - Clean up old checkpoints (keep last 1)                      │
│     - Update job status: "Checkpoints: 123 completed"             │
└────────────────────────────────────────────────────────────────────┘
```

---

## **What's Inside a Checkpoint?**

### **Checkpoint Directory Structure**
```
s3://flink-checkpoints/checkpoints/chk-123/
├── metadata                          # JSON metadata
│   {
│     "id": 123,
│     "timestamp": 1738420800000,
│     "duration_ms": 2500,
│     "size_bytes": 1048576
│   }
│
└── shared/                           # Shared operator state
    ├── mysql-cdc-sales/
    │   └── binlog-offset
    │       {
    │         "file": "mysql-bin.000003",
    │         "position": 456789,
    │         "gtid": "3E11FA47-...:234"
    │       }
    │
    ├── mysql-cdc-products/
    │   └── binlog-offset
    │       {
    │         "file": "mysql-bin.000003",
    │         "position": 456700
    │       }
    │
    ├── join-operator/
    │   └── product-lookup-cache
    │       {
    │         "1": {"name": "Laptop", "sku": "PROD-001"},
    │         "2": {"name": "Mouse", "sku": "PROD-002"}
    │       }
    │
    └── aggregation-operator/
        └── hourly-revenue
            {
              "2025-02-01-12": {
                "count": 150,
                "revenue": 15000.00
              }
            }
```

---

## **Recovery Scenario**

### **Before Crash (Normal Operation)**
```
MySQL Binlog:
  mysql-bin.000003
  └─ Events: 1...1000

Flink State:
  ├─ Last processed: Event 1000
  ├─ Binlog position: (mysql-bin.000003, pos: 456789)
  └─ Checkpoint 123 saved

Iceberg:
  └─ 1000 rows processed
```

### **Crash! (Flink dies)**
```
❌ Flink JobManager crashes
❌ TaskManagers crash
❌ Local state lost
```

### **After Recovery (Automatic)**
```
┌─────────────────────────────────────┐
│ Flink Restart                       │
│                                     │
│ 1. Load latest checkpoint:          │
│    - Download from s3://.../chk-123 │
│    - Restore binlog position:       │
│      (mysql-bin.000003, 456789)     │
│    - Restore join state:            │
│      {1: "Laptop", 2: "Mouse", ...} │
│                                     │
│ 2. Resume MySQL CDC:                │
│    - Start from Event 1001 ✓        │
│    - No data loss ✓                 │
│    - No duplicates ✓                │
└─────────────────────────────────────┘

Result:
  ✅ Events 1-1000: Already in Iceberg
  ✅ Events 1001+: Processing now
  ✅ State fully recovered
```

---

## **Comparison: Checkpoint vs No Checkpoint**

```
┌─────────────────────────────────────────────────────────────────┐
│ SCENARIO: Flink processes 1000 events, then crashes            │
└─────────────────────────────────────────────────────────────────┘

WITHOUT CHECKPOINT:
  ─────────────────
  MySQL:     [1.........1000][1001.......2000]
  Flink:     [↑ process ↑]       💀 CRASH
  Iceberg:   [1.........1000]
                           [↑ restart from beginning ↑]
  Result:    ❌ Events 1-1000 DUPLICATED
             ❌ Wrong analytics
             ❌ Data corruption


WITH CHECKPOINT:
  ────────────
  MySQL:     [1.........1000][1001.......2000]
  Flink:     [↑ process ↑]  📸 Checkpoint: 1000 💀 CRASH
  Iceberg:   [1.........1000]
                                    [↑ resume from 1001 ↑]
  Result:    ✅ Events 1-1000: Already in Iceberg (skipped)
             ✅ Events 1001-2000: Processing now
             ✅ No duplicates
             ✅ Accurate analytics
```

---

## **Storage Location Comparison**

```
┌─────────────────┬──────────────┬──────────────┬──────────────┐
│ Storage Type    │ Location     │ Persistence  │ Recommended  │
├─────────────────┼──────────────┼──────────────┼──────────────┤
│ JobManager      │ Memory       │ ❌ Lost on   │ ❌ No        │
│ Memory          │              │    restart   │              │
├─────────────────┼──────────────┼──────────────┼──────────────┤
│ TaskManager     │ Local disk   │ ❌ Lost on   │ ⚠️  Only     │
│ Local Disk      │              │    restart   │    testing   │
├─────────────────┼──────────────┼──────────────┼──────────────┤
│ Docker Volume   │ /flink/      │ ✅ Survives  │ ✅ Good      │
│                 │  checkpoints │    restart   │    for dev   │
├─────────────────┼──────────────┼──────────────┼──────────────┤
│ MinIO / S3      │ s3://        │ ✅ Persistent│ ✅ YES       │
│                 │  flink-      │ ✅ Scalable  │    for       │
│                 │  checkpoints │ ✅ Shareable │    production │
└─────────────────┴──────────────┴──────────────┴──────────────┘
```

---

## **Configuration Examples**

### **Development (Local Disk)**
```yaml
# Simple, fast, good for testing
state.backend: filesystem
state.checkpoints.dir: file:///tmp/flink-checkpoints/
execution.checkpointing.interval: 60s
```

### **Staging (Docker Volume)**
```yaml
# Survives container restarts
state.backend: rocksdb
state.checkpoints.dir: file:///flink/checkpoints/
execution.checkpointing.interval: 30s

# docker-compose.yml
volumes:
  - flink-checkpoints:/flink/checkpoints
```

### **Production (MinIO/S3)**
```yaml
# Durable, scalable, cluster-ready
state.backend: rocksdb
state.checkpoints.dir: s3://flink-checkpoints/checkpoints/
state.savepoints.dir: s3://flink-checkpoints/savepoints/
execution.checkpointing.interval: 30s
execution.checkpointing.timeout: 10min

s3.endpoint: http://minio:9000
s3.access-key: ${MINIO_ACCESS_KEY}
s3.secret-key: ${MINIO_SECRET_KEY}
```

---

## **Monitoring Dashboard**

```
FLINK WEB UI: http://localhost:8081

Job: sales_products_join
└─ Checkpoints Tab
   ├─ Overview
   │  ├─ Checkpoint count: 1,234
   │  ├─ Duration (avg): 2.5s
   │  ├─ Size (avg): 10.5 MB
   │  └─ Recovery time: 8s
   │
   ├─ History
   │  ├─ chk-1234 ✅ Completed (2.3s, 10.2 MB)
   │  ├─ chk-1233 ✅ Completed (2.5s, 10.3 MB)
   │  └─ chk-1232 ✅ Completed (2.1s, 10.1 MB)
   │
   └─ Summary
      ├─ Triggered: Every 30s
      ├─ Completed: 1,234
      ├─ Failed: 0
      └─ Restored: 2 (after restarts)
```

---

## **Quick Reference: Where Are My Checkpoints?**

### **In Your Architecture:**

```
Container Path:
  - TaskManager: /opt/flink/rocksdb/ (local state)
  - MinIO: s3://flink-checkpoints/checkpoints/ (persistent)

Host Machine:
  - Docker volume: /var/lib/docker/volumes/flink-iceberg_flink-checkpoints/

MinIO Console:
  - http://localhost:9001
  - Login: minio / minio123
  - Bucket: flink-checkpoints → checkpoints → chk-XXX
```

### **Check from CLI:**
```bash
# Check MinIO
docker exec minio mc ls minio/flink-checkpoints/checkpoints/

# Check Docker volume
docker run --rm -v flink-iceberg_flink-checkpoints:/data busybox \
  ls -lh /data/

# Check Flink REST API
curl http://localhost:8081/jobs/<job-id>/checkpoints | jq
```

---

## **Summary**

**Checkpoint Location = s3://flink-checkpoints/** in MinIO

✅ **Durable**: Survives any container restart
✅ **Scalable**: Works with multiple TaskManagers
✅ **Observable**: View in MinIO console
✅ **Essential**: Required for CDC exactly-once guarantees

**Key Configuration:**
```yaml
state.backend: rocksdb
state.checkpoints.dir: s3://flink-checkpoints/checkpoints/
```

**What Gets Stored:**
- MySQL binlog position
- Join state (product lookup cache)
- Aggregation state
- Window state

**Why It Matters:**
- No data loss
- No duplicates
- Automatic recovery
- Exactly-once processing
```
