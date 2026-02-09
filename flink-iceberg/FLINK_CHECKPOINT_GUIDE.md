# Flink CDC Checkpoint Storage Guide

## **What Are Flink Checkpoints?**

**Checkpoints** are snapshots of Flink's state at a specific point in time. For CDC pipelines, they include:
- **Binlog Position**: Which MySQL binlog offset has been processed
- **Operator State**: Aggregations, joins, window states
- **Kafka Offsets**: (if using Kafka) Last consumed message offset

### **Why Checkpoints Matter for CDC**

```
Scenario: Flink crashes or restarts

Without Checkpoints:
  ✗ Loses track of binlog position
  ✗ Re-processes data from beginning (duplicates)
  ✗ Misses data (gaps in CDC stream)

With Checkpoints:
  ✓ Restores from last successful checkpoint
  ✓ Continues from exact binlog position
  ✓ Exactly-once processing guarantees
  ✓ No data loss, no duplicates
```

---

## **Checkpoint Storage Architecture**

### **Current Architecture (Recommended)**

```
┌───────────────────────────────────────────────────────┐
│                   Flink Cluster                       │
├───────────────────────────────────────────────────────┤
│                                                        │
│  ┌──────────────┐        ┌──────────────────┐        │
│  │ JobManager   │        │  TaskManager(s)  │        │
│  │              │        │                  │        │
│  │ - Checkpoint │◄───────│ - RocksDB State  │        │
│  │   Metadata   │  Sync  │ - Operator State │        │
│  │ (in memory)  │        │ - Local files    │        │
│  └──────┬───────┘        └────────┬─────────┘        │
│         │                          │                   │
│         │ Checkpoint files         │                   │
│         └──────────────────────────┘                   │
│                    │                                   │
└────────────────────┼───────────────────────────────────┘
                     │ ↓ saves to
                     ↓
          ┌──────────────────────┐
          │   MinIO (S3)         │
          │                      │
          │ s3://flink-checkpoints/
          │   ├── chk-1/         │
          │   ├── chk-2/         │
          │   └── chk-3/         │
          └──────────────────────┘
```

### **What Gets Stored Where?**

| Component | Location | Persistence |
|-----------|----------|-------------|
| **Checkpoint Metadata** | JobManager memory | Lost on restart (small) |
| **RocksDB State Files** | TaskManager local disk | Lost on restart |
| **Checkpoint Snapshots** | MinIO (S3) | **Persistent** ✅ |
| **Savepoints** | MinIO (S3) | **Manual snapshots** ✅ |

---

## **Configuration Options**

### **Option 1: MinIO/S3 (Recommended for Production)**

**Pros:**
- ✅ Durable storage
- ✅ Survives container restarts
- ✅ Supports scaling (add/remove TaskManagers)
- ✅ Can restore from any checkpoint

**Configuration:**
```yaml
# flink-conf.yaml
state.backend: rocksdb
state.checkpoints.dir: s3://flink-checkpoints/checkpoints/
state.savepoints.dir: s3://flink-checkpoints/savepoints/

s3.endpoint: http://minio:9000
s3.access-key: minio
s3.secret-key: minio123
s3.path.style.access: true
```

**Checkpoint Storage Structure:**
```
s3://flink-checkpoints/
├── checkpoints/
│   ├── chk-123/
│   │   ├── metadata                 # Checkpoint metadata
│   │   └── shared/                  # Shared state files
│   │       ├── file1                # RocksDB SST files
│   │       └── file2
│   ├── chk-124/
│   └── chk-125/
└── savepoints/
    └── savepoint-1234567890/
```

---

### **Option 2: Docker Volume (Local Filesystem)**

**Pros:**
- ✅ Simpler setup
- ✅ No S3 dependency
- ✅ Fast local I/O

**Cons:**
- ❌ Tied to specific node
- ❌ Not easily shareable across cluster
- ❌ Host machine storage required

**Configuration:**
```yaml
# flink-conf.yaml
state.backend: rocksdb
state.checkpoints.dir: file:///flink/checkpoints/
state.savepoints.dir: file:///flink/savepoints/
```

**docker-compose.yml:**
```yaml
volumes:
  flink-checkpoints:
    driver: local

services:
  jobmanager:
    volumes:
      - flink-checkpoints:/flink/checkpoints

  taskmanager:
    volumes:
      - flink-checkpoints:/flink/checkpoints
```

---

### **Option 3: JobManager Memory (Not Recommended)**

**Configuration:**
```yaml
state.backend: jobmanager
```

**⚠️ Problems:**
- ❌ Checkpoints lost on JobManager restart
- ❌ Limited by JobManager heap size
- ❌ Not suitable for production CDC

---

## **Flink CDC Checkpoint Contents**

For a **MySQL CDC pipeline**, checkpoints store:

### **1. Binlog Position**
```json
{
  "binlog_filename": "mysql-bin.000003",
  "position": 123456,
  "gtid": "3E11FA47-71CA-11E1-9E33-C80AA9429562:23"
}
```

### **2. Operator State**
- **Join State**: Cached product data for stream joins
- **Aggregation State**: Running totals, counts
- **Window State**: Time window buffers

### **3. Kafka Offsets** (if using Kafka)
```json
{
  "topic": "mysql-appdb.sales",
  "partition": 0,
  "offset": 987654
}
```

---

## **Checkpoint Lifecycle**

```
1. Trigger (every 30s)
   ↓
2. TaskManager writes local snapshot
   - RocksDB SST files
   - State to local disk
   ↓
3. Upload to MinIO
   - chk-1/ uploaded to s3://flink-checkpoints/
   ↓
4. JobManager acknowledges
   - Metadata updated
   - Old checkpoints deleted
   ↓
5. Retention Policy
   - Keep last N checkpoints (configurable)
   - Default: retain 1 checkpoint
```

---

## **Recovery from Checkpoint**

### **Automatic Recovery (Flink manages)**

```bash
# Flink crashes
docker-compose restart jobmanager

# Flink automatically:
1. Finds latest checkpoint in s3://flink-checkpoints/
2. Restores binlog position
3. Resumes CDC from exact position
4. Continues processing
```

### **Manual Recovery (from Savepoint)**

```bash
# Trigger savepoint
docker exec -it jobmanager flink savepoint \
  <job-id> \
  s3://flink-checkpoints/savepoints/

# Restore from savepoint
docker exec -it jobmanager flink run \
  -s s3://flink-checkpoints/savepoints/savepoint-xxx/ \
  /opt/flink/jobs/my-job.jar
```

---

## **Monitoring Checkpoints**

### **Flink Web UI**
```
http://localhost:8081
  → Click on running job
  → Checkpoints tab
```

**Metrics to Watch:**
- ✅ **Completed Checkpoints**: Should be increasing
- ✅ **Checkpoint Duration**: Should be < interval (30s)
- ✅ **Checkpoint Size**: Watch for growth (state bloating)
- ⚠️ **Failed Checkpoints**: Should be 0

### **CLI Check**
```bash
# List checkpoints
curl http://localhost:8081/jobs/<job-id>/checkpoints

# Get latest checkpoint
curl http://localhost:8081/jobs/<job-id>/checkpoints/latest
```

---

## **Best Practices**

### **1. Checkpoint Interval**
```yaml
# More frequent = faster recovery, more overhead
execution.checkpointing.interval: 30s  # Good for CDC
execution.checkpointing.interval: 1m   # Lower overhead
execution.checkpointing.interval: 10s  # Near real-time recovery
```

### **2. Checkpoint Timeout**
```yaml
# How long to wait before failing
execution.checkpointing.timeout: 10min  # For large state
execution.checkpointing.timeout: 5min   # Default
```

### **3. Retention**
```yaml
# Keep last N checkpoints
execution.checkpointing.max-concurrent-checkpoints: 1

# Automatic cleanup
execution.checkpointing.unaligned: false  # Aligned checkpoints
```

### **4. State Backend Choice**
```yaml
# For production CDC
state.backend: rocksdb

# For testing/small state
state.backend: filesystem

# NEVER for production
# state.backend: jobmanager  ❌
```

---

## **Troubleshooting**

### **Checkpoints Failing**

**Symptoms:**
- Web UI shows "Failed" checkpoints
- Logs show timeout errors

**Solutions:**
```yaml
# Increase timeout
execution.checkpointing.timeout: 20min

# Reduce state size
# - Add windowing to limit state
# - Use state TTL

# Increase network bandwidth
# - Check MinIO connection
# - Use faster storage
```

### **Checkpoint Size Growing**

**Symptoms:**
- Checkpoints getting larger over time
- Slower checkpointing

**Solutions:**
```sql
-- Add state TTL to Flink SQL
CREATE TABLE sales_with_ttl (
    ...
) WITH (
    'state.ttl' = '1h'  -- Expire state after 1 hour
);
```

### **Recovery Fails**

**Symptoms:**
- Job can't restore from checkpoint
- Binlog position not found

**Solutions:**
```bash
# Check if MySQL binlog still exists
docker exec mysql mysql -e "SHOW BINARY LOGS;"

# Increase binlog retention
# MySQL config: expire_logs_days = 7

# Use savepoint as fallback
flink run -s s3://.../savepoint-xxx/ ...
```

---

## **Testing Checkpoint Recovery**

```bash
# 1. Start the pipeline
docker-compose up -d
./submit-direct-cdc-job.sh

# 2. Insert test data
docker exec mysql mysql -uroot -prootpw appdb \
  -e "INSERT INTO sales VALUES (100, 1, 5, 49.99, NOW());"

# 3. Verify data in Iceberg
docker exec trino trino -e "SELECT * FROM iceberg.appdb.enriched_sales;"

# 4. Kill Flink (simulate crash)
docker-compose stop jobmanager taskmanager

# 5. Restart Flink
docker-compose start jobmanager taskmanager

# 6. Insert more data
docker exec mysql mysql -uroot -prootpw appdb \
  -e "INSERT INTO sales VALUES (101, 2, 3, 29.99, NOW());"

# 7. Verify recovery worked
# - Old data still there (✓)
# - New data appears (✓)
# - No duplicates (✓)
docker exec trino trino -e "SELECT COUNT(*) FROM iceberg.appdb.enriched_sales;"
```

---

## **Summary**

| Aspect | Recommendation |
|--------|---------------|
| **Storage Backend** | RocksDB |
| **Checkpoint Location** | MinIO (S3) |
| **Checkpoint Interval** | 30s for CDC |
| **Retention** | Keep last 1-3 checkpoints |
| **Monitoring** | Flink Web UI Checkpoints tab |
| **Recovery** | Automatic from latest checkpoint |
| **Savepoints** | Manual snapshots before upgrades |

---

## **Files Created**

1. **flink-conf.yaml** - Complete Flink configuration with checkpoint settings
2. **docker-compose-with-checkpoints.yml** - Docker Compose with persistent volumes
3. **minio/create-buckets.sh** - Script to create checkpoint bucket

## **Next Steps**

```bash
# Use the new docker-compose file
docker-compose -f docker-compose-with-checkpoints.yml up -d

# Submit job
docker exec -it jobmanager bash /opt/flink/jobs/submit-direct-cdc-job.sh

# Monitor checkpoints
open http://localhost:8081
# Click on your job → Checkpoints tab

# Verify checkpoints in MinIO
docker exec minio mc ls minio/flink-checkpoints/checkpoints/
```
