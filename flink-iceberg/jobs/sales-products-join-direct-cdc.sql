-- ====================================================================
-- Flink SQL Job: Join Sales with Products (Direct MySQL CDC)
-- Description: Uses Flink MySQL CDC connector to directly read from
--              MySQL binlog (no intermediate Kafka needed)
-- ====================================================================

-- ====================================================================
-- STEP 1: CREATE CATALOG FOR ICEBERG
-- ====================================================================
CREATE CATALOG iceberg WITH (
    'type' = 'iceberg',
    'catalog-type' = 'rest',
    'uri' = 'http://minio:9001',
    'warehouse' = 's3://warehouse',
    's3.endpoint' = 'http://minio:9000',
    's3.access-key' = 'minio',
    's3.secret-key' = 'minio123'
);

USE CATALOG iceberg;

-- Create database
CREATE DATABASE IF NOT EXISTS appdb;
USE appdb;

-- ====================================================================
-- STEP 2: CREATE MYSQL CDC SOURCE TABLES (Direct from MySQL)
-- ====================================================================

-- Products CDC Source (Dimension Table)
-- Flink directly connects to MySQL and reads binlog
CREATE TABLE IF NOT EXISTS products_source (
    id INT,
    sku STRING,
    name STRING,
    price DECIMAL(10, 2),
    category STRING,
    created_at TIMESTAMP(3),
    updated_at TIMESTAMP(3),
    PRIMARY KEY (id) NOT ENFORCED
) WITH (
    'connector' = 'mysql-cdc',
    'hostname' = 'mysql',
    'port' = '3306',
    'username' = 'root',
    'password' = 'rootpw',
    'database-name' = 'appdb',
    'table-name' = 'products',
    'server-time-zone' = 'UTC',
    'scan.incremental.snapshot.enabled' = 'true',
    'scan.incremental.snapshot.chunk.size' = '8096',
    'scan.snapshot.fetch.size' = '1024'
);

-- Sales CDC Source (Fact Table)
-- Captures all INSERT/UPDATE/DELETE operations from sales table
CREATE TABLE IF NOT EXISTS sales_source (
    id INT,
    product_id INT,
    qty INT,
    price DECIMAL(10, 2),
    sale_ts TIMESTAMP(3),
    PRIMARY KEY (id) NOT ENFORCED,
    WATERMARK FOR sale_ts AS sale_ts - INTERVAL '5' SECONDS
) WITH (
    'connector' = 'mysql-cdc',
    'hostname' = 'mysql',
    'port' = '3306',
    'username' = 'root',
    'password' = 'rootpw',
    'database-name' = 'appdb',
    'table-name' = 'sales',
    'server-time-zone' = 'UTC',
    'scan.incremental.snapshot.enabled' = 'true',
    'scan.incremental.snapshot.chunk.size' = '8096'
);

-- ====================================================================
-- STEP 3: CREATE ICEBERG SINK TABLE (Enriched Sales Data)
-- ====================================================================
-- Result table: Sales enriched with product information
CREATE TABLE IF NOT EXISTS enriched_sales (
    -- Sales data
    sale_id INT,
    product_id INT,
    quantity INT,
    sale_price DECIMAL(10, 2),
    sale_timestamp TIMESTAMP(3),

    -- Product data (joined)
    product_sku STRING,
    product_name STRING,
    product_category STRING,
    product_current_price DECIMAL(10, 2),

    -- Metadata
    processing_time TIMESTAMP(3) METADATA FROM 'timestamp'
) WITH (
    'format-version' = '2',
    'write.format' = 'parquet',
    'write.parquet.compression-codec' = 'snappy',
    'write.metadata.compression-codec' = 'gzip'
);

-- ====================================================================
-- STEP 4: STREAMING JOIN - SALES + PRODUCTS → ICEBERG
-- ====================================================================
-- This query runs continuously:
-- 1. Watches MySQL sales table for changes
-- 2. Joins with products table
-- 3. Enriches and writes to Iceberg

INSERT INTO enriched_sales

SELECT
    -- Sales fields
    s.id AS sale_id,
    s.product_id,
    s.qty AS quantity,
    s.price AS sale_price,
    s.sale_ts AS sale_timestamp,

    -- Product fields (enriched via join)
    p.sku AS product_sku,
    p.name AS product_name,
    p.category AS product_category,
    p.price AS product_current_price,

    -- Metadata
    CURRENT_TIMESTAMP AS processing_time

FROM sales_source s

-- Left join with products to enrich sales data
-- Uses product_id as the join key
LEFT JOIN products_source p
    ON s.product_id = p.id;

-- ====================================================================
-- STEP 5: REAL-TIME AGGREGATION (Sales per Product per Hour)
-- ====================================================================
-- Optional: Create an aggregated table for faster analytics

CREATE TABLE IF NOT EXISTS product_sales_hourly (
    product_id INT,
    product_name STRING,
    product_category STRING,
    hour_window_start TIMESTAMP(3),
    hour_window_end TIMESTAMP(3),
    total_orders BIGINT,
    total_quantity BIGINT,
    total_revenue DECIMAL(20, 2),
    avg_order_value DECIMAL(10, 2)
) PARTITIONED BY (days(hour_window_start)) WITH (
    'format-version' = '2',
    'write.format' = 'parquet',
    'write.parquet.compression-codec' = 'snappy'
);

-- Hourly aggregation using tumbling window
INSERT INTO product_sales_hourly

SELECT
    s.product_id,
    p.name AS product_name,
    p.category AS product_category,
    TUMBLE_START(s.sale_ts, INTERVAL '1' HOUR) AS hour_window_start,
    TUMBLE_END(s.sale_ts, INTERVAL '1' HOUR) AS hour_window_end,
    COUNT(*) AS total_orders,
    SUM(s.qty) AS total_quantity,
    SUM(s.qty * s.price) AS total_revenue,
    AVG(s.qty * s.price) AS avg_order_value

FROM enriched_sales s
LEFT JOIN products_source p ON s.product_id = p.id
GROUP BY
    s.product_id,
    p.name,
    p.category,
    TUMBLE(s.sale_ts, INTERVAL '1' HOUR);

-- ====================================================================
-- ARCHITECTURE NOTES
-- ====================================================================
/*
PIPELINE:

MySQL Binlog
    ↓
Flink MySQL CDC Connector (reads binlog directly)
    ↓
Flink SQL Streaming Engine
    ├─ sales_source (CDC stream)
    ├─ products_source (CDC stream + cached for joins)
    ↓
Flink SQL Transformations:
    ├─ Filter: None (all changes captured)
    ├─ Join: sales_source LEFT JOIN products_source
    ├─ Enrich: Add product details to sales
    └─ Aggregate: Hourly summaries
    ↓
Iceberg Table (MinIO/S3)
    ├─ enriched_sales (raw joined data)
    └─ product_sales_hourly (aggregated metrics)
    ↓
Trino Analytics Engine
    └─ SQL queries for BI/reporting

TRANSFORMATIONS APPLIED:

1. CDC Capture:
   - Flink MySQL CDC connector reads binlog
   - Captures INSERT, UPDATE, DELETE operations
   - Maintains consistent snapshots

2. Stream Join:
   - sales_source LEFT JOIN products_source
   - Products table cached in Flink state
   - Real-time lookup as sales stream through

3. Enrichment:
   - Add product SKU, name, category
   - Both historical and current price

4. Aggregation (Optional):
   - Tumbling window: 1-hour intervals
   - COUNT, SUM, AVG calculations
   - Partitioned by day for efficiency

BENEFITS OF DIRECT CDC (vs Kafka):

✓ Simpler architecture (no Kafka/Debezium needed)
✓ Lower latency (direct binlog reading)
✓ Less operational overhead
✓ Easier to debug and monitor

WHEN TO USE KAFKA INSTEAD:

✗ Multiple consumers need same data
✗ Need event replay capabilities
✗ Decoupling producers from consumers
✗ Very high throughput requirements

TESTING THE PIPELINE:

1. Start the stack:
   docker-compose up -d mysql jobmanager taskmanager minio

2. Submit the job:
   ./submit-direct-cdc-job.sh

3. Insert test data:
   docker exec -it mysql mysql -uroot -prootpw appdb
   INSERT INTO sales (product_id, qty, price) VALUES (1, 2, 49.99);

4. Query Iceberg via Trino:
   docker exec -it trino trino
   SELECT * FROM iceberg.appdb.enriched_sales;

5. Watch data flow in Flink UI:
   http://localhost:8081
*/
