# Local Development Setup

This guide explains how to run the DLT-Iceberg CDC pipeline locally for development and testing.

## Prerequisites

To run locally, you need:
1. **PostgreSQL** - with logical replication enabled
2. **MinIO** - or any S3-compatible storage
3. **Python 3.11+** - with virtual environment support

## Option 1: Docker Compose (Recommended for Local Testing)

The easiest way to run locally is with Docker Compose, which starts PostgreSQL and MinIO for you.

### Step 1: Start Services

```bash
cd /Users/tien.nguyen6/Desktop/Cake/nttien/lakehouse/dlt-iceberg
docker-compose up -d
```

This starts:
- PostgreSQL on port 5432
- MinIO on ports 9000 (API) and 9001 (Console)
- DLT Pipeline (will start automatically)

### Step 2: Initialize Replication

The first time, you need to initialize PostgreSQL replication:

```bash
# Enter the pipeline container
docker-compose exec dlt-pipeline bash

# Run the initialization script
python -c "
from dlt.sources.pg_replication import init_replication

init_replication(
    slot_name='dlt_replication_slot',
    pub_name='dlt_publication',
    credentials='postgresql://replication_user:replication123@postgres:5432/dlt_data',
    schema_name='public',
    table_names=None,
    reset=True
)
"

exit
```

### Step 3: View Logs

```bash
docker-compose logs -f dlt-pipeline
```

### Step 4: Test CDC

Make changes in PostgreSQL:

```bash
docker-compose exec postgres psql -U postgres -d dlt_data

# Make changes
INSERT INTO users (username, email) VALUES ('test_user', 'test@example.com');
UPDATE users SET email = 'new@example.com' WHERE username = 'test_user';

exit
```

Watch the DLT logs to see the changes captured!

### Stop Services

```bash
docker-compose down
```

## Option 2: Manual Local Setup

If you want to run everything manually on your local machine.

### Step 1: Install Dependencies

```bash
cd /Users/tien.nguyen6/Desktop/Cake/nttien/lakehouse/dlt-iceberg

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install Python packages
pip install -r pipeline/requirements.txt
```

### Step 2: Start PostgreSQL

Using Docker:

```bash
docker run -d \
  --name dlt-postgres \
  -e POSTGRES_DB=dlt_data \
  -e POSTGRES_USER=replication_user \
  -e POSTGRES_PASSWORD=replication123 \
  -p 5432:5432 \
  postgres:16-alpine
```

Or use your local PostgreSQL installation.

Initialize the database:

```bash
psql -h localhost -U postgres -d dlt_data < scripts/init-postgres.sql
```

### Step 3: Start MinIO

```bash
docker run -d \
  --name dlt-minio \
  -e MINIO_ROOT_USER=minioadmin \
  -e MINIO_ROOT_PASSWORD=minioadmin123 \
  -p 9000:9000 \
  -p 9001:9001 \
  minio/minio server /data --console-address ":9001"
```

Create bucket:

```bash
# Install mc CLI first
brew install minio/stable/mc

# Configure mc
mc alias set local http://localhost:9000 minioadmin minioadmin123

# Create bucket
mc mb local/iceberg-data
```

### Step 4: Run the Pipeline

**Option A: Using the helper script**

```bash
cd /Users/tien.nguyen6/Desktop/Cake/nttien/lakehouse/dlt-iceberg
./scripts/run-local.sh
```

**Option B: Manually**

```bash
cd /Users/tien.nguyen6/Desktop/Cake/nttien/lakehouse/dlt-iceberg

# Activate virtual environment
source .venv/bin/activate

# Set environment variables
export POSTGRES_HOST=localhost
export POSTGRES_PORT=5432
export POSTGRES_DB=dlt_data
export POSTGRES_USER=replication_user
export POSTGRES_PASSWORD=replication123

export MINIO_ENDPOINT=http://localhost:9000
export ICEBERG_BUCKET=iceberg-data
export MINIO_ACCESS_KEY=minioadmin
export MINIO_SECRET_KEY=minioadmin123

# Run the pipeline
cd pipeline
python pg_to_iceberg_pipeline.py
```

## Environment Variables

The pipeline uses these environment variables:

### PostgreSQL
| Variable | Default | Description |
|----------|---------|-------------|
| `POSTGRES_HOST` | localhost | PostgreSQL hostname |
| `POSTGRES_PORT` | 5432 | PostgreSQL port |
| `POSTGRES_DB` | dlt_data | Database name |
| `POSTGRES_USER` | replication_user | Replication user |
| `POSTGRES_PASSWORD` | replication123 | Replication password |

### MinIO/S3
| Variable | Default | Description |
|----------|---------|-------------|
| `MINIO_ENDPOINT` | http://localhost:9000 | MinIO endpoint |
| `ICEBERG_BUCKET` | iceberg-data | S3 bucket name |
| `MINIO_ACCESS_KEY` | minioadmin | Access key |
| `MINIO_SECRET_KEY` | minioadmin123 | Secret key |

### Replication
| Variable | Default | Description |
|----------|---------|-------------|
| `SLOT_NAME` | dlt_replication_slot | Replication slot name |
| `PUB_NAME` | dlt_publication | Publication name |

## Troubleshooting

### Issue: "ModuleNotFoundError: No module named 'dlt'"

**Solution**: Activate the virtual environment:
```bash
source .venv/bin/activate
```

### Issue: "connection refused" to PostgreSQL

**Solution**: Ensure PostgreSQL is running:
```bash
# If using Docker
docker ps | grep postgres

# Check connection
psql -h localhost -U replication_user -d dlt_data
```

### Issue: "Replication slot already exists"

**Solution**: Drop and recreate the slot:
```sql
psql -h localhost -U postgres -d dlt_data

SELECT pg_drop_replication_slot('dlt_replication_slot');
```

### Issue: MinIO connection refused

**Solution**: Ensure MinIO is running and bucket exists:
```bash
# Check MinIO is running
curl http://localhost:9000/minio/health/live

# Create bucket
mc alias set local http://localhost:9000 minioadmin minioadmin123
mc mb local/iceberg-data
```

### Issue: Pipeline not capturing changes

**Check 1**: Verify publication exists:
```sql
SELECT pubname FROM pg_publication WHERE pubname = 'dlt_publication';
```

**Check 2**: Verify table is in publication:
```sql
SELECT * FROM pg_publication_tables WHERE pubname = 'dlt_publication';
```

**Check 3**: Check replication slot status:
```sql
SELECT slot_name, slot_type, active, restart_lsn
FROM pg_replication_slots
WHERE slot_name = 'dlt_replication_slot';
```

## Development Workflow

### 1. Make Code Changes

Edit files in `pipeline/` directory:
- `pg_to_iceberg_pipeline.py` - Main pipeline logic
- `.dlt/config.toml` - DLT configuration

### 2. Test Locally

```bash
# Stop any running instances
docker-compose down

# Restart with your changes
docker-compose up -d --build

# View logs
docker-compose logs -f dlt-pipeline
```

### 3. Debug

Add print statements or use a debugger:

```bash
# Run with verbose logging
export LOG_LEVEL=DEBUG
./scripts/run-local.sh
```

### 4. Check DLT State

```bash
# Enter the container/pod
docker-compose exec dlt-pipeline bash

# View pipeline state
dlt pipeline pg_to_iceberg_cdc show
dlt pipeline pg_to_iceberg_cdc state
```

## Next Steps

After local testing is working:

1. **Deploy to Kubernetes**:
   ```bash
   cd scripts
   ./deploy.sh
   ```

2. **Customize the pipeline**:
   - Add your own tables
   - Change partitioning strategies
   - Add custom metadata fields

3. **Production hardening**:
   - Use proper secrets management
   - Enable TLS/SSL
   - Configure monitoring
   - Set up alerts

## Additional Resources

- [DLT Documentation](https://dlthub.com/)
- [PostgreSQL Logical Replication](https://www.postgresql.org/docs/current/logicaldecoding.html)
- [Apache Iceberg](https://iceberg.apache.org/docs/latest/)
- [MinIO Documentation](https://min.io/docs/minio/linux/index.html)
