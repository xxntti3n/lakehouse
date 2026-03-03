# Services & access URLs

Use these URLs from your machine (localhost). Deploy with:  
`docker-compose --profile catalog --profile analytics up -d`

---

## Service status (verified)

| Service | Container | Status | Ports |
|--------|-----------|--------|-------|
| MySQL | mysql-source | Up (healthy) | 3306 |
| MinIO | minio-storage | Up (healthy) | 9000, 9001 |
| Nessie | nessie-catalog | Up (healthy) | 19120 |
| CDC pipeline | debezium-dlt-connector | Up | — |
| Data generator | mysql-data-generator | Up | — |
| StarRocks FE | starrocks-fe | Up (healthy) | 8030, 9020, 9030 |
| StarRocks BE | starrocks-be | Up | 8040 |
| StarRocks init | starrocks-init | Exited (one-shot) | — |

---

## Access URLs

### MySQL (source)

| What | URL / command | Credentials |
|------|----------------|-------------|
| TCP | `localhost:3306` | user: **root** / password: **rootpw** |
| Database | `appdb` | — |
| CLI | `mysql -h 127.0.0.1 -P 3306 -u root -prootpw` | — |
| From Docker | `docker exec -it mysql-source mysql -uroot -prootpw appdb` | — |

---

### MinIO (S3 storage)

| What | URL | Credentials |
|------|-----|-------------|
| Web console | **http://localhost:9001** | **minio** / **minio123** |
| S3 API | http://localhost:9000 | same |

Buckets: `dlt-warehouse` (CDC + Iceberg data), `dlt-checkpoints` (offsets).

---

### Nessie (Iceberg catalog)

| What | URL | Credentials |
|------|-----|-------------|
| API v2 config | **http://localhost:19120/api/v2/config** | — |
| Iceberg REST | http://localhost:19120/iceberg | — |

No login; HTTP only.

---

### StarRocks

| What | URL / command | Credentials |
|------|----------------|-------------|
| Frontend (web / HTTP API) | **http://localhost:8030** | — |
| MySQL protocol (CLI, JDBC) | `localhost:9030` | user: **root** / password: *(empty)* |
| CLI from host | `mysql -h 127.0.0.1 -P 9030 -u root` | — |
| CLI via Docker | `docker exec -it starrocks-fe mysql -h 127.0.0.1 -P 9030 -u root` | — |

---

### DuckDB / Streamlit UI (optional)

Only if you start with `--profile duckdb`:

| What | URL | Credentials |
|------|-----|-------------|
| Streamlit app | **http://localhost:8501** | — |

---

### CDC pipeline (no web UI)

| What | How |
|------|-----|
| Logs | `docker logs debezium-dlt-connector -f` |
| Runs | Every 5 minutes (snapshot + binlog stream) |

---

## Quick copy-paste URLs

```
MySQL:          localhost:3306          (root / rootpw)
MinIO console:  http://localhost:9001   (minio / minio123)
Nessie API:     http://localhost:19120/api/v2/config
StarRocks UI:   http://localhost:8030
StarRocks SQL:  mysql -h 127.0.0.1 -P 9030 -u root   (no browser; use CLI/JDBC)
DuckDB UI:      http://localhost:8501   (only with --profile duckdb)
```
