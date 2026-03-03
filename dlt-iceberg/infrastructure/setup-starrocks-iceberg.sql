-- StarRocks Iceberg catalog: read from same Iceberg as DLT pipeline (Nessie + MinIO).
-- Ref: https://docs.starrocks.io/docs/quick_start/iceberg/
--
-- Run after StarRocks FE is healthy (--profile analytics):
--   docker exec -i starrocks-fe mysql -h 127.0.0.1 -P 9030 -u root < infrastructure/setup-starrocks-iceberg.sql

-- Create Iceberg REST catalog (StarRocks 3.2 has no IF NOT EXISTS; run once).
-- If catalog already exists, skip or drop it first in a session.
CREATE EXTERNAL CATALOG iceberg_nessie
COMMENT "Iceberg catalog (Nessie) - same as DLT pipeline writes to"
PROPERTIES (
    "type" = "iceberg",
    "iceberg.catalog.type" = "rest",
    "iceberg.catalog.uri" = "http://nessie:19120/iceberg/v1",
    "iceberg.catalog.warehouse" = "s3://dlt-warehouse/iceberg",
    "aws.s3.endpoint" = "http://minio:9000",
    "aws.s3.access_key" = "minio",
    "aws.s3.secret_key" = "minio123",
    "aws.s3.enable_path_style_access" = "true"
);

SHOW CATALOGS;

-- After CDC has run (with --profile catalog), query Iceberg tables (dlt writes to dataset_name, table cdc_events):
--   SET CATALOG iceberg_nessie;
--   SHOW DATABASES;
--   USE <your_dataset_name>;   -- e.g. debezium_cdc from DATASET_NAME
--   SHOW TABLES;
--   SELECT * FROM cdc_events LIMIT 10;
