# Flink Iceberg Pipeline with StarRocks + Apache Ranger

## Overview

This project includes:
- Flink streaming pipeline with Iceberg tables
- MinIO for S3-compatible storage
- StarRocks for high-performance analytics
- Apache Ranger for centralized data governance

## Quick Start

### Start Main Pipeline

```bash
docker-compose up -d
```

### Start StarRocks + Ranger (Data Governance)

```bash
# Start the governance stack
./scripts/setup-starrocks-ranger.sh

# Create sample policies
./scripts/create-sample-policies.sh

# Verify integration
./scripts/verify-ranger-integration.sh
```

### Services

| Service | Port | Description |
|---------|------|-------------|
| Flink JobManager | 8081 | Flink dashboard |
| MinIO Console | 9001 | Object storage UI |
| Trino | 8080 | Query engine |
| **Ranger Admin** | **6080** | **Policy management** |
| **StarRocks FE** | **9030** | **Query port (MySQL protocol)** |
| **StarRocks UI** | **8030** | **StarRocks dashboard** |

## Documentation

- [Pipeline Guide](docs/README_PIPELINE.md)
- [StarRocks + Ranger Guide](docs/STARROCKS_RANGER_GUIDE.md)
