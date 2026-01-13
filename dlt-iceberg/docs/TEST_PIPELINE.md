# Testing the PostgreSQL CDC Pipeline

## Prerequisites Check

✅ PostgreSQL running with logical replication
✅ MinIO running and accessible
✅ DLT with pg_replication installed
✅ Virtual environment created

## Quick Test

### Step 1: Run the pipeline

```bash
cd /Users/tien.nguyen6/Desktop/Cake/nttien/lakehouse/dlt-iceberg/pipeline
source .venv/bin/activate
python pg_to_iceberg_simple.py
```

The pipeline will start and listen for changes. Keep it running!

### Step 2: Make changes in PostgreSQL

In a new terminal:

```bash
# Test INSERT
docker exec -it dlt-postgres psql -U postgres -d dlt_data

INSERT INTO users (username, email) VALUES ('cdc_test_1', 'cdc1@example.com');
INSERT INTO orders (user_id, amount, status) VALUES (1, 150.00, 'processing');

UPDATE users SET email = 'updated@example.com' WHERE username = 'cdc_test_1';

DELETE FROM users WHERE username = 'cdc_test_1';
```

### Step 3: Check MinIO for captured data

```bash
docker exec dlt-minio mc ls -r local/iceberg-data/cdc/
```

You should see JSONL files with the captured changes!

## What to Expect

**Pipeline Output:**
```
============================================================
PostgreSQL to Filesystem CDC Pipeline
============================================================
PostgreSQL: localhost:5432/dlt_data
Destination: http://localhost:9000/iceberg-data

Initializing replication slot: dlt_replication_slot, publication: dlt_publication
Replication initialized successfully
Creating replication resource...
Starting replication pipeline...
Listening for changes in PostgreSQL...
(Press Ctrl+C to stop)
------------------------------------------------------------
```

**After making changes:**
The pipeline will capture them and write to MinIO.

**In MinIO:**
```
s3://iceberg-data/cdc/
├── users/
│   └── users_0.jsonl
└── orders/
    └── orders_0.jsonl
```

**File content example** (`users_0.jsonl`):
```json
{"id": 6, "username": "cdc_test_1", "email": "cdc1@example.com", "created_at": "2025-01-12T16:30:00", "updated_at": "2025-01-12T16:30:00", "extracted_at": "2025-01-12T16:30:05.123456", "deleted_at": null, "pipeline_run_id": "2025-01-12T16:30:05.123456"}
{"id": 7, "username": "cdc_test_1", "email": "updated@example.com", "created_at": "2025-01-12T16:30:10", "updated_at": "2025-01-12T16:30:10", "extracted_at": "2025-01-12T16:30:15.123456", "deleted_at": null, "pipeline_run_id": "2025-01-12T16:30:15.123456"}
{"id": 6, "username": "cdc_test_1", "email": "updated@example.com", "created_at": "2025-01-12T16:30:10", "updated_at": "2025-01-12T16:30:10", "extracted_at": "2025-01-12T16:30:20.123456", "deleted_at": "2025-01-12T16:30:20.123456", "pipeline_run_id": "2025-01-12T16:30:20.123456"}
```

## Troubleshooting

### Pipeline doesn't capture changes

**Check replication slot:**
```bash
docker exec dlt-postgres psql -U postgres -d dlt_data -c "SELECT slot_name, slot_type, active FROM pg_replication_slots;"
```

**Check publication:**
```bash
docker exec dlt-postgres psql -U postgres -d dlt_data -c "SELECT * FROM pg_publication_tables;"
```

**Check if slot is active:**
```bash
docker exec dlt-postgres psql -U postgres -d dlt_data -c "SELECT slot_name, active, restart_lsn FROM pg_replication_slots WHERE slot_name = 'dlt_replication_slot';"
```

### No data in MinIO

**Check pipeline state:**
```bash
# In the pipeline directory
dlt pipeline pg_to_filesystem_cdc show
dlt pipeline pg_to_filesystem_cdc state
```

**Check DLT logs:**
The pipeline will show detailed logging about what it's doing.

### Publication owner error

If you see "must be owner of publication dlt_publication", recreate it:

```sql
DROP PUBLICATION dlt_publication;
CREATE PUBLICATION dlt_publication FOR TABLE users, orders;
```

## Success Indicators

✅ Pipeline starts without errors
✅ Shows "Listening for changes in PostgreSQL..."
✅ Captures INSERT, UPDATE, DELETE operations
✅ Files appear in MinIO `s3://iceberg-data/cdc/`
✅ Files contain `extracted_at` and `deleted_at` metadata fields

## Next Steps

Once this is working:

1. **Deploy to Kubernetes**: Use the K8s manifests
2. **Add Iceberg format**: Convert to Parquet + Iceberg metadata
3. **Scale up**: Run multiple pipeline instances
4. **Production hardening**: Add monitoring, alerts, etc.
