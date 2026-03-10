# Flink CDC Pipeline: Sales + Products Join

This pipeline demonstrates real-time data streaming using Apache Flink, MySQL CDC, and Apache Iceberg.

## Architecture Overview

```
┌──────────────┐     CDC      ┌──────────────┐     Join      ┌─────────────┐
│    MySQL     │ ──────────►  │  Flink SQL   │ ────────────► │   Iceberg   │
│              │   Binlog     │  Streaming   │   Enriched   │ (MinIO/S3)  │
│  - sales     │              │              │              │             │
│  - products  │              │ Transform:   │              │ Parquet     │
└──────────────┘              │  - Join      │              └──────┬──────┘
                               │  - Filter   │                     │
                               │  - Enrich   │                     │
                               └──────────────┘                     │
                                                                    │
                                                                    ▼
                                                          ┌──────────────┐
                                                          │    Trino     │
                                                          │  Analytics   │
                                                          └──────────────┘
```

## Flink Transformations Used

### 1. **CDC Capture (Change Data Capture)**
- **Connector**: Flink MySQL CDC
- **What it does**: Reads MySQL binlog directly
- **Captures**: INSERT, UPDATE, DELETE operations
- **Latency**: Sub-second

```sql
CREATE TABLE sales_source (
    id INT,
    product_id INT,
    qty INT,
    price DECIMAL(10, 2),
    sale_ts TIMESTAMP(3)
) WITH (
    'connector' = 'mysql-cdc',
    'hostname' = 'mysql',
    ...
);
```

### 2. **Stream Join**
- **Type**: LEFT JOIN (streaming)
- **How it works**:
  - Products table cached in Flink state
  - Sales records stream through
  - Real-time lookup for each sales record

```sql
SELECT s.*, p.name, p.category
FROM sales_source s
LEFT JOIN products_source p
  ON s.product_id = p.id;
```

### 3. **Enrichment**
- **Adds**: Product name, SKU, category to sales data
- **Result**: Denormalized, ready for analytics

```sql
SELECT
    s.id AS sale_id,
    s.qty AS quantity,
    s.price AS sale_price,
    p.name AS product_name,      -- ← Enriched
    p.category AS product_category -- ← Enriched
FROM sales_source s
LEFT JOIN products_source p ON s.product_id = p.id;
```

### 4. **Aggregation (Optional)**
- **Window**: Tumbling window (1 hour)
- **Operations**: COUNT, SUM, AVG
- **Output**: Hourly metrics per product

```sql
SELECT
    product_id,
    COUNT(*) AS total_orders,
    SUM(qty * price) AS total_revenue
FROM enriched_sales
GROUP BY
    product_id,
    TUMBLE(sale_ts, INTERVAL '1' HOUR);
```

## Quick Start

### 1. Start the Infrastructure

```bash
cd /Users/tien.nguyen6/Desktop/Cake/nttien/lakehouse/flink-iceberg

# Start all services
docker-compose up -d mysql minio jobmanager taskmanager trino

# Wait for services to be ready (30 seconds)
sleep 30
```

### 2. Initialize MySQL with Tables

```bash
# The init.sql will run automatically on first start
# Verify tables exist:
docker exec -it mysql mysql -uroot -prootpw appdb -e "SHOW TABLES;"
docker exec -it mysql mysql -uroot -prootpw appdb -e "SELECT * FROM products;"
```

### 3. Submit the Flink SQL Job

```bash
# Make script executable (already done)
chmod +x submit-direct-cdc-job.sh

# Run inside the jobmanager container
docker exec -it jobmanager /opt/flink/jobs/submit-direct-cdc-job.sh
```

Or manually:

```bash
docker exec -it jobmanager /opt/flink/bin/sql-client.sh embedded \
    -f /opt/flink/jobs/sales-products-join-direct-cdc.sql
```

### 4. Insert Test Data

```bash
# Option 1: Use the auto-inserter (every 10 seconds)
docker-compose up -d mysql-data-inserter

# Option 2: Manually insert records
docker exec -it mysql mysql -uroot -prootpw appdb

mysql> INSERT INTO sales (product_id, qty, price) VALUES
    (1, 2, 49.99),
    (2, 1, 29.99),
    (3, 5, 99.99);
```

### 5. Query Results via Trino

```bash
# Connect to Trino
docker exec -it trino trino

# Query the enriched sales table
SELECT * FROM iceberg.appdb.enriched_sales
ORDER BY sale_timestamp DESC
LIMIT 10;

# See hourly aggregation
SELECT * FROM iceberg.appdb.product_sales_hourly
ORDER BY hour_window_start DESC;
```

## Files Created

| File | Purpose |
|------|---------|
| `sql/init.sql` | MySQL database and tables initialization |
| `jobs/sales-products-join-direct-cdc.sql` | Flink SQL job (direct CDC) |
| `jobs/sales-products-join.sql` | Flink SQL job (via Kafka/Debezium) |
| `submit-direct-cdc-job.sh` | Submit job script (recommended) |
| `submit-job.sh` | Submit job script (Kafka version) |
| `insert-sales-data-loop.sh` | Auto-insert test data every 10s |

## Monitoring

### Flink Web UI
```
http://localhost:8081
```
- See running jobs
- Check checkpoint progress
- View task metrics
- Monitor backpressure

### MinIO Console
```
http://localhost:9001
Username: minio
Password: minio123
```
- Browse Iceberg tables
- Verify Parquet files
- Check storage usage

### Logs

```bash
# Flink logs
docker-compose logs -f jobmanager
docker-compose logs -f taskmanager

# MySQL data inserter
docker-compose logs -f mysql-data-inserter

# All services
docker-compose logs -f
```

## Data Flow Example

### Step 1: Data Inserted into MySQL
```sql
INSERT INTO sales (product_id, qty, price, sale_ts)
VALUES (1, 2, 49.99, NOW());
```

### Step 2: MySQL Binlog Captures Change
```
Binlog event: INSERT at position 1234
Database: appdb
Table: sales
Data: {id: 101, product_id: 1, qty: 2, price: 49.99}
```

### Step 3: Flink CDC Reads Binlog
```
Flink CDC Source receives event:
Schema: sales_source (id, product_id, qty, price, sale_ts)
Event: {101, 1, 2, 49.99, 2025-02-01 12:34:56}
```

### Step 4: Flink Joins with Products
```
Stream Join:
  sales_source: {101, 1, 2, 49.99}
  LEFT JOIN products_source ON product_id = 1
  Result: {101, 1, 2, 49.99, 'PROD-001', 'Laptop Stand', 'Electronics'}
```

### Step 5: Flink Writes to Iceberg
```
Iceberg table: enriched_sales
Format: Parquet (columnar, compressed)
Location: s3://warehouse/appdb/enriched_sales/
Data partitioned by: None (or date if configured)
```

### Step 6: Trino Queries Iceberg
```sql
SELECT
    product_name,
    SUM(quantity * sale_price) as revenue
FROM iceberg.appdb.enriched_sales
GROUP BY product_name;
```

## Performance Characteristics

| Metric | Value |
|--------|-------|
| Latency (MySQL → Iceberg) | < 5 seconds |
| Throughput | Thousands of events/sec |
| Storage Format | Parquet + Snappy compression |
| Query Performance | Columnar, fast aggregations |

## Advanced: Using Kafka (Optional)

If you need Kafka for:
- Multiple consumers
- Event replay
- Decoupling services

Use `jobs/sales-products-join.sql` instead.

Requires:
1. Debezium MySQL connector
2. Kafka topics: `mysql-appdb.products`, `mysql-appdb.sales`

## Troubleshooting

### Job Not Starting
```bash
# Check Flink is running
docker-compose ps jobmanager taskmanager

# Check Flink logs
docker-compose logs jobmanager

# Verify MySQL connectivity
docker exec -it jobmanager mysql -hmysql -uroot -prootpw -e "SELECT 1"
```

### No Data in Iceberg
```bash
# Verify MySQL has data
docker exec -it mysql mysql -uroot -prootpw appdb -e "SELECT COUNT(*) FROM sales"

# Check Flink job status
curl http://localhost:8081/jobs

# Insert test data manually
docker exec -it mysql mysql -uroot -prootpw appdb
INSERT INTO sales (product_id, qty, price) VALUES (1, 1, 49.99);
```

### Connection Errors
```bash
# Verify all services are up
docker-compose ps

# Check network connectivity
docker exec -it jobmanager ping mysql
docker exec -it jobmanager ping minio
```

## Next Steps

1. **Add more transformations**:
   - Filtering invalid orders
   - Calculating derived metrics
   - Detecting anomalies

2. **Add more sinks**:
   - Push to Kafka for real-time dashboards
   - Write to Elasticsearch for search
   - Export to BigQuery for ML

3. **Optimize**:
   - Partition Iceberg tables by date
   - Add Iceberg snapshots for time travel
   - Tune Flink checkpointing

## Resources

- [Flink CDC Documentation](https://nightlies.apache.org/flink/flink-docs-release-1.18/docs/connectors/table/cdc/)
- [Apache Iceberg](https://iceberg.apache.org/)
- [Trino](https://trino.io/)
