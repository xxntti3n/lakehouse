-- Iceberg JDBC catalog on MySQL; data in MinIO via S3FileIO
CREATE CATALOG lake WITH (
  'type' = 'iceberg',
  'catalog-impl' = 'org.apache.iceberg.jdbc.JdbcCatalog',
  'uri' = 'jdbc:mysql://mysql:3306/iceberg_catalog',
  'jdbc.user' = 'root',
  'jdbc.password' = 'rootpw',
  'warehouse' = 's3://iceberg/warehouse',
  'io-impl' = 'org.apache.iceberg.aws.s3.S3FileIO',
  's3.endpoint' = 'http://minio:9000',
  's3.path-style-access' = 'true',
  's3.access-key-id' = 'minio',
  's3.secret-access-key' = 'minio123',
  'client.region' = 'us-east-1'
);

USE CATALOG lake;
CREATE DATABASE IF NOT EXISTS demo;
USE demo;

-- CDC sources with streaming configuration
CREATE TABLE mysql_products (
  id INT,
  sku STRING,
  name STRING,
  PRIMARY KEY (id) NOT ENFORCED
) WITH (
  'connector' = 'mysql-cdc',
  'hostname' = 'mysql',
  'port' = '3306',
  'username' = 'root',
  'password' = 'rootpw',
  'database-name' = 'appdb',
  'table-name' = 'products',
  'scan.incremental.snapshot.enabled' = 'true',
  'scan.startup.mode' = 'initial'
);

CREATE TABLE mysql_sales (
  id BIGINT,
  product_id INT,
  qty INT,
  price DECIMAL(10,2),
  sale_ts TIMESTAMP(3),
  PRIMARY KEY (id) NOT ENFORCED
) WITH (
  'connector' = 'mysql-cdc',
  'hostname' = 'mysql',
  'port' = '3306',
  'username' = 'root',
  'password' = 'rootpw',
  'database-name' = 'appdb',
  'table-name' = 'sales',
  'scan.incremental.snapshot.enabled' = 'true',
  'scan.startup.mode' = 'initial'
);

-- Iceberg targets
CREATE TABLE IF NOT EXISTS products (
  id INT,
  sku STRING,
  name STRING,
  PRIMARY KEY (id) NOT ENFORCED
);

CREATE TABLE IF NOT EXISTS sales (
  id BIGINT,
  product_id INT,
  qty INT,
  price DECIMAL(10,2),
  sale_ts TIMESTAMP(3),
  PRIMARY KEY (id) NOT ENFORCED
);

-- Stream into Iceberg
INSERT INTO products SELECT id, sku, name FROM mysql_products;
INSERT INTO sales    SELECT id, product_id, qty, price, sale_ts FROM mysql_sales;