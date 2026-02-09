-- ====================================================================
-- Flink SQL Job: Join Sales with Products CDC Pipeline
-- Description: Captures MySQL CDC events via Kafka, joins sales with
--              products, and writes enriched results to Iceberg
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
-- STEP 2: CREATE CDC SOURCE TABLES (From MySQL via Kafka + Debezium)
-- ====================================================================

-- Products CDC Source (Dimension Table)
-- This table captures all changes to the products table in MySQL
CREATE TABLE IF NOT EXISTS products_cdc (
    id INT,
    sku STRING,
    name STRING,
    price DECIMAL(10, 2),
    category STRING,
    created_at TIMESTAMP(3),
    updated_at TIMESTAMP(3),
    op STRING,                   -- Operation: c=create, u=update, d=delete
    ts_ms TIMESTAMP(3) METADATA, -- Event timestamp
    WATERMARK FOR updated_at AS updated_at - INTERVAL '5' SECONDS,
    PRIMARY KEY (id) NOT ENFORCED
) WITH (
    'connector' = 'kafka',
    'topic' = 'mysql-appdb.products',
    'properties.bootstrap.servers' = 'kafka:29092',
    'properties.group.id' = 'flink-products-consumer',
    'scan.startup.mode' = 'earliest-offset',
    'format' = 'debezium-json',
    'debezium-json.schema.include' = 'false'
);

-- Sales CDC Source (Fact Table)
-- This table captures all changes to the sales table in MySQL
CREATE TABLE IF NOT EXISTS sales_cdc (
    id INT,
    product_id INT,
    qty INT,
    price DECIMAL(10, 2),
    sale_ts TIMESTAMP(3),
    op STRING,                   -- Operation: c=create, u=update, d=delete
    ts_ms TIMESTAMP(3) METADATA, -- Event timestamp
    WATERMARK FOR sale_ts AS sale_ts - INTERVAL '5' SECONDS,
    PRIMARY KEY (id) NOT ENFORCED
) WITH (
    'connector' = 'kafka',
    'topic' = 'mysql-appdb.sales',
    'properties.bootstrap.servers' = 'kafka:29092',
    'properties.group.id' = 'flink-sales-consumer',
    'scan.startup.mode' = 'earliest-offset',
    'format' = 'debezium-json',
    'debezium-json.schema.include' = 'false'
);

-- ====================================================================
-- STEP 3: CREATE ICEBERG SINK TABLE (Enriched Sales Data)
-- ====================================================================
-- This table stores the joined result of sales + products
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
    cdc_operation STRING,        -- Original CDC operation
    event_timestamp TIMESTAMP(3), -- When the event was processed
    processing_time AS PROCTIME() -- Flink processing time (computed column)
) WITH (
    'format-version' = '2',
    'write.format' = 'parquet',
    'write.parquet.compression-codec' = 'snappy',
    'write.metadata.compression-codec' = 'gzip'
);

-- ====================================================================
-- STEP 4: STREAMING JOIN - SALES + PRODUCTS → ICEBERG
-- ====================================================================
-- This query continuously:
-- 1. Reads INSERT operations from sales_cdc
-- 2. Looks up product information from products_cdc
-- 3. Enriches sales data with product details
-- 4. Writes to Iceberg for analytics

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
    s.op AS cdc_operation,
    s.ts_ms AS event_timestamp

FROM sales_cdc s

-- Left join with products to enrich sales data
-- If product is deleted, we still keep the sales record
LEFT JOIN products_cdc p
    ON s.product_id = p.id

-- Only process new sales records (INSERT operations)
WHERE s.op = 'c';

-- ====================================================================
-- STEP 5: AGGREGATION TABLE (Optional - Sales per Product)
-- ====================================================================
-- Real-time aggregation: Total sales and revenue per product
CREATE TABLE IF NOT EXISTS product_sales_summary (
    product_id INT,
    product_name STRING,
    product_category STRING,
    total_orders BIGINT,
    total_quantity BIGINT,
    total_revenue DECIMAL(20, 2),
    avg_order_value DECIMAL(10, 2),
    last_sale_time TIMESTAMP(3),
    window_start TIMESTAMP(3),
    window_end TIMESTAMP(3)
) PARTITIONED BY (days(window_start)) WITH (
    'format-version' = '2',
    'write.format' = 'parquet',
    'write.parquet.compression-codec' = 'snappy'
);

-- Insert aggregated data every 1 minute
INSERT INTO product_sales_summary

SELECT
    p.product_id,
    p.product_name,
    p.product_category,
    COUNT(*) AS total_orders,
    SUM(p.quantity) AS total_quantity,
    SUM(p.quantity * p.sale_price) AS total_revenue,
    AVG(p.quantity * p.sale_price) AS avg_order_value,
    MAX(p.sale_timestamp) AS last_sale_time,
    TUMBLE_START(p.sale_timestamp, INTERVAL '1' MINUTE) AS window_start,
    TUMBLE_END(p.sale_timestamp, INTERVAL '1' MINUTE) AS window_end
FROM enriched_sales
GROUP BY
    p.product_id,
    p.product_name,
    p.product_category,
    TUMBLE(p.sale_timestamp, INTERVAL '1' MINUTE);

-- ====================================================================
-- NOTES & ARCHITECTURE EXPLANATION
-- ====================================================================
/*
TRANSFORMATION PIPELINE:

1. MySQL → Binlog (CDC)
   Every INSERT/UPDATE/DELETE is captured in MySQL binlog

2. Debezium → Kafka (Not yet configured)
   Debezium connector reads binlog and produces events to Kafka topics:
   - mysql-appdb.products
   - mysql-appdb.sales

3. Kafka → Flink SQL (Streaming)
   Flink consumes CDC events from Kafka in real-time

4. Flink SQL Transformations:
   a) FILTER: WHERE s.op = 'c' (only new sales)
   b) JOIN: sales_cdc LEFT JOIN products_cdc
   c) ENRICH: Add product name, category, SKU
   d) AGGREGATE: Windowed aggregations per product

5. Flink → Iceberg (Data Lake)
   Results stored in columnar Parquet format on MinIO (S3-compatible)

6. Iceberg → Trino (Analytics)
   Trino queries Iceberg tables for BI dashboards

TRANSFORMATIONS USED:
- Filter: Only INSERT operations (op = 'c')
- Join: Streaming LEFT JOIN with lookup table
- Map: Column aliases and renaming
- Aggregate: Windowed aggregation (1-minute tumbling windows)
- Watermark: Event-time processing with 5-second lateness allowance

BENEFITS:
- Real-time: Data available in seconds
- Enriched: Sales + product information in one table
- Historical: Iceberg keeps all versions
- Fast analytics: Columnar storage for aggregations
- Time travel: Query previous snapshots with Iceberg
*/
