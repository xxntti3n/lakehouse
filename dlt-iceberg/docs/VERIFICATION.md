# Deployment verification

## After redeploy

Run from project root:  
`docker-compose --profile catalog --profile analytics up -d --build`

### 1. Container status

All services should be **Up** and (where applicable) **healthy**:

| Service              | Expected status        | Notes                          |
|----------------------|------------------------|--------------------------------|
| mysql-source         | Up (healthy)           | 512MB limit to avoid OOM       |
| minio-storage        | Up (healthy)           |                                |
| nessie-catalog       | Up (healthy)           |                                |
| debezium-dlt-connector | Up                  | CDC every 5 min                |
| mysql-data-generator | Up                     |                                |
| starrocks-fe         | Up (healthy)           | 1GB limit                      |
| starrocks-be         | Up                     |                                |
| starrocks-init       | Exited (0) or (1)      | One-shot; (1) if BE already registered |

Check:

```bash
docker-compose --profile catalog --profile analytics ps -a
```

### 2. Requirements checklist

| Requirement | Status | How to verify |
|-------------|--------|----------------|
| DLT reads CDC from MySQL | ✅ | `docker logs debezium-dlt-connector` shows "Snapshot complete", "CDC Pipeline Complete" |
| GTID filtered to this server | ✅ | Logs show server UUID and offset; `filter_gtid_set_to_server` used in binlog_streamer |
| Data to MinIO | ✅ | MinIO console http://localhost:9001 → buckets `dlt-warehouse`, `dlt-checkpoints` |
| Nessie catalog | ✅ | Container healthy; http://localhost:19120 |
| Iceberg format in MinIO | ⚠️ | If Nessie Iceberg REST fails, writer falls back to **plain Parquet** (same path). For full Iceberg, check logs for "Iceberg REST (Nessie) catalog configured" and no "falling back to plain Parquet". |
| StarRocks minimal (Docker) | ✅ | FE (8030, 9030) + BE running |
| StarRocks reads Iceberg | ⚠️ | Catalog `iceberg_nessie` created; if pipeline used Parquet fallback, Nessie has no tables so StarRocks will show "Warehouse not known" or empty DBs. Fix: get Nessie Iceberg REST working so pipeline writes real Iceberg. |
| Deploy without DuckDB/Streamlit | ✅ | Default compose has no duckdb profile; use `--profile duckdb` to add UI. |

### 3. StarRocks

- **Frontend (HTTP):** http://localhost:8030  
- **MySQL protocol:** `mysql -h 127.0.0.1 -P 9030 -u root` or  
  `docker exec -it starrocks-fe mysql -h 127.0.0.1 -P 9030 -u root`

Create Iceberg catalog (run once, no `IF NOT EXISTS` in StarRocks 3.2):

```bash
docker exec -i starrocks-fe mysql -h 127.0.0.1 -P 9030 -u root < infrastructure/setup-starrocks-iceberg.sql
```

If pipeline wrote **real Iceberg** (Nessie REST succeeded), then:

```sql
SET CATALOG iceberg_nessie;
USE appdb;
SHOW TABLES;
SELECT * FROM products LIMIT 5;
```

If you see "Warehouse not known" or no tables, the pipeline is still using Parquet fallback; data is in MinIO under `dlt-warehouse/iceberg/` as plain Parquet.

### 4. Quick commands

```bash
# Logs
docker logs debezium-dlt-connector --tail 80
docker logs mysql-source --tail 20

# MySQL
docker exec -it mysql-source mysql -uroot -prootpw -e "SELECT COUNT(*) FROM appdb.products; SELECT COUNT(*) FROM appdb.sales;"
```
