# DLT Iceberg Pipeline

MySQL → DLT → MinIO → DuckDB CDC Pipeline with automated scheduling and GTID tracking.

## 🎯 Overview

This project implements a complete Change Data Capture (CDC) pipeline that:
- Extracts data from MySQL database
- Loads it into MinIO (S3-compatible storage) using DLT
- Enables querying with DuckDB
- Visualizes data with Streamlit UI
- **Runs automatically every 2 minutes**
- **Tracks GTID (Global Transaction Identifier) for CDC monitoring**
- **Real-time log viewing in Streamlit UI**

## 📊 Architecture

```
MySQL Source → DLT Pipeline → MinIO Storage → DuckDB → Streamlit UI
   (3306)      (cron: 2min)     (9000)       (query)    (8501)
    ↓              ↓
  GTID        GTID Logging
Tracking      (/tmp/dlt_gtid.log)
```

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- Colima (for macOS) or Docker Desktop

### Start All Services

```bash
cd /Users/tien.nguyen6/Desktop/Cake/nttien/lakehouse/dlt-iceberg
docker-compose up -d --build
```

This starts:
- **MySQL** (port 3306) - Source database with products & sales tables, **GTID enabled**
- **MinIO** (port 9000/9001) - S3-compatible storage
- **DuckDB UI** (port 8501) - Data exploration interface with real-time log viewing
- **DLT Cron Job** - Runs CDC pipeline every 2 minutes automatically with GTID tracking
- **Data Generator** - Runs every 1 minute, inserts/updates random data

### Access Points

- **DuckDB UI**: http://localhost:8501
- **MinIO Console**: http://localhost:9001 (minio / minio123)
- **MySQL**: localhost:3306 (root / rootpw / appdb)

## 📈 Data Pipeline

### Source Data (MySQL)
- **products** table: 5 products (Laptop, Mouse, Keyboard, Monitor, Headphones)
- **sales** table: 5 sales records

### Destination (MinIO)
- Data stored at: `s3://dlt-warehouse/warehouse/`
- Format: Compressed JSONL files (*.jsonl.gz)
- Buckets: `dlt-warehouse`

### Query Interface (DuckDB UI)
Access the Streamlit UI at http://localhost:8501 to:
- Browse tables and schemas
- Run SQL queries on S3 data
- Visualize results
- View query history
- **View real-time DLT pipeline logs** (with auto-refresh)
- **Monitor GTID status and configuration**
- **View GTID log history from pipeline runs**

## 🔧 Management Commands

### View Running Containers
```bash
docker ps
```

### View Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker logs -f dlt-cron-job    # CDC pipeline
docker logs -f mysql-source    # MySQL database
docker logs -f minio-storage   # MinIO storage
docker logs -f duckdb-ui       # DuckDB interface
```

### Stop All Services
```bash
docker-compose down
```

### Restart Services
```bash
docker-compose restart
```

### Run Pipeline Manually
```bash
docker run --network lakehouse_default --rm mysql-iceberg-pipeline
```

## 📊 Sample Queries

In the DuckDB UI (http://localhost:8501):

### View Products
```sql
SELECT * FROM read_json_auto('s3://dlt-warehouse/warehouse/products/*.jsonl.gz')
```

### View Sales
```sql
SELECT * FROM read_json_auto('s3://dlt-warehouse/warehouse/sales/*.jsonl.gz')
```

### Join Tables
```sql
SELECT
    p.name,
    s.quantity,
    s.total
FROM read_json_auto('s3://dlt-warehouse/warehouse/products/*.jsonl.gz') p
JOIN read_json_auto('s3://dlt-warehouse/warehouse/sales/*.jsonl.gz') s
    ON p.id = s.product_id
```

### Sales Summary
```sql
SELECT
    p.name,
    COUNT(s.id) as num_transactions,
    SUM(s.quantity) as units_sold,
    SUM(s.total) as total_revenue
FROM read_json_auto('s3://dlt-warehouse/warehouse/products/*.jsonl.gz') p
LEFT JOIN read_json_auto('s3://dlt-warehouse/warehouse/sales/*.jsonl.gz') s
    ON p.id = s.product_id
GROUP BY p.name
ORDER BY total_revenue DESC
```

## 🔐 Credentials

| Service | Username | Password | Database/Bucket |
|---------|----------|----------|-----------------|
| MySQL | root | rootpw | appdb |
| MinIO | minio | minio123 | dlt-warehouse |

## 📁 Project Structure

```
dlt-iceberg/
├── docker-compose.yml          # Main orchestration
├── Dockerfile.pipeline         # DLT pipeline image
├── Dockerfile.duckdb           # DuckDB UI image
├── run_pipeline.py             # DLT pipeline script
├── run_pipeline_with_gtid.py   # DLT pipeline with GTID tracking
├── random_data_generator.py    # Generates random data for testing
├── requirements.txt            # Python dependencies
├── requirements-duckdb.txt     # DuckDB UI dependencies
├── infrastructure/
│   ├── init.sql                # MySQL initialization data
│   └── my.cnf                  # MySQL GTID configuration
├── duckdb-ui/
│   ├── streamlit_ui.py         # Streamlit interface with log viewing
│   └── duckdb_query.py         # DuckDB helper functions
└── .dlt/                       # DLT pipeline state
```

## 🔄 How It Works

1. **Data Generator** runs every 1 minute, inserting/updating random data in MySQL
2. **DLT Cron Container** runs continuously
3. Every 2 minutes, it executes `run_pipeline_with_gtid.py`
4. Pipeline connects to MySQL and extracts data
5. **GTID information is captured** before and after each run
6. GTID data is logged to `/tmp/dlt_gtid.log` for tracking
7. Data is loaded to MinIO as compressed JSONL
8. DuckDB UI queries data directly from S3
9. Users can explore data, view pipeline logs, and monitor GTID via Streamlit

## 📍 GTID Tracking

### What is GTID?
- **GTID** = Global Transaction Identifier
- Unique identifier for each transaction in MySQL
- Format: `source_id:transaction_number`
- Example: `f86c0440-044a-11f1-a63a-4619df7017cd:1-3`

### GTID Configuration
MySQL is configured with GTID enabled:
- `gtid_mode = ON`
- `enforce_gtid_consistency = ON`
- `log_bin = mysql-bin`
- `binlog_format = ROW`

### Viewing GTID Information

**In Streamlit UI** (http://localhost:8501):
- Go to the "📍 GTID Status" tab
- View current MySQL GTID configuration
- See GTID logs from pipeline runs
- Track which transactions have been processed

**Via MySQL CLI**:
```bash
docker exec mysql-source mysql -uroot -prootpw -e "SHOW VARIABLES LIKE '%gtid%'; SHOW MASTER STATUS;"
```

**GTID Log File**:
```bash
docker exec dlt-cron-job cat /tmp/dlt_gtid.log | jq
```

## 🎓 Technologies Used

- **DLT** - Data loading framework
- **MySQL** - Source database
- **MinIO** - S3-compatible object storage
- **DuckDB** - In-memory analytical database
- **Streamlit** - Data visualization UI
- **Docker Compose** - Container orchestration

## 🚦 Status

✅ All services running
✅ CDC pipeline active (every 2 minutes)
✅ Data flowing from MySQL to MinIO
✅ DuckDB can query S3 data successfully
✅ Streamlit UI accessible

## 📝 Notes

- The pipeline uses `write_disposition="replace"` to replace data on each run
- For incremental CDC, modify the DLT resource configuration
- Pipeline state is stored in `.dlt/` directory
- MinIO data persists in Docker volumes unless explicitly removed

---

**Last Updated**: February 8, 2026
**Status**: Production Ready ✅
