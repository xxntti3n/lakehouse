"""
Configuration for Debezium-style DLT connector
"""

import os
from dataclasses import dataclass, field
from typing import List, Optional, Dict


@dataclass
class MySQLConfig:
    """MySQL connection configuration"""
    host: str = 'mysql-source'
    port: int = 3306
    user: str = 'root'
    password: str = 'rootpw'
    database: str = 'appdb'

    # Binlog settings
    server_id: int = 12345  # Unique ID for this connector (avoid conflicts)
    only_events: List[str] = field(default_factory=lambda: ['UpdateRows', 'WriteRows', 'DeleteRows'])

    # Snapshot settings
    snapshot_mode: str = 'initial'  # initial, schema_only, never, incremental
    snapshot_chunk_size: int = 1000  # Rows per chunk for incremental snapshot


@dataclass
class IcebergConfig:
    """Iceberg/MinIO configuration for checkpoint storage"""
    checkpoint_bucket: str = 'dlt-checkpoints'
    checkpoint_prefix: str = 'checkpoints'
    warehouse: str = 's3://dlt-checkpoints/iceberg'

    # S3 settings
    endpoint_url: str = 'http://minio:9000'
    access_key: str = 'minio'
    secret_key: str = 'minio123'
    region: str = 'us-east-1'

    # Nessie catalog (optional)
    nessie_uri: Optional[str] = None  # e.g. http://nessie:19120/api/v2
    nessie_ref: str = 'main'

    # Iceberg REST catalog URI for dlt (optional). If unset, derived from nessie_uri as {base}/iceberg/v1
    iceberg_rest_uri: Optional[str] = None  # e.g. http://nessie:19120/iceberg/v1


@dataclass
class DLTConfig:
    """DLT destination configuration"""
    destination_bucket: str = 'dlt-warehouse'
    dataset_name: str = 'cdc_data'
    pipeline_name: str = 'debezium_dlt_pipeline'

    # Write disposition
    write_disposition: str = 'merge'  # merge, replace, append


@dataclass
class DebeziumConfig:
    """Main configuration for Debezium DLT connector"""

    # Sub-configurations
    mysql: MySQLConfig = field(default_factory=MySQLConfig)
    iceberg: IcebergConfig = field(default_factory=IcebergConfig)
    dlt: DLTConfig = field(default_factory=DLTConfig)

    # Tables to capture
    table_include_list: List[str] = field(default_factory=lambda: ['appdb.products', 'appdb.sales'])

    # GTID settings
    gtid_source_include: Optional[str] = None  # Filter by server UUID (e.g., 'uuid1,uuid2')
    gtid_source_exclude: Optional[str] = None

    # Behavior settings
    snapshot_fetch_size: int = 1000  # Rows per snapshot batch
    streaming_batch_size: int = 100  # Events per streaming batch
    streaming_pause_interval: float = 0.1  # Seconds between polling

    # State management
    state_file: str = '/tmp/debezium_dlt_state.json'

    # Logging
    log_level: str = 'INFO'
    log_file: str = '/logs/debezium_dlt.log'

    @classmethod
    def from_env(cls) -> 'DebeziumConfig':
        def _nessie_to_iceberg_rest(uri: Optional[str]) -> Optional[str]:
            if not uri:
                return None
            base = uri.rstrip('/').replace('/api/v2', '')
            return f"{base}/iceberg/v1"

        """Create configuration from environment variables"""
        return cls(
            mysql=MySQLConfig(
                host=os.getenv('MYSQL_HOST', 'mysql-source'),
                port=int(os.getenv('MYSQL_PORT', '3306')),
                user=os.getenv('MYSQL_USER', 'root'),
                password=os.getenv('MYSQL_PASSWORD', 'rootpw'),
                database=os.getenv('MYSQL_DATABASE', 'appdb')
            ),
            iceberg=IcebergConfig(
                checkpoint_bucket=os.getenv('CHECKPOINT_BUCKET', 'dlt-checkpoints'),
                endpoint_url=os.getenv('S3_ENDPOINT_URL', 'http://minio:9000'),
                access_key=os.getenv('S3_ACCESS_KEY', 'minio'),
                secret_key=os.getenv('S3_SECRET_KEY', 'minio123'),
                nessie_uri=os.getenv('NESSIE_URI') or None,
                nessie_ref=os.getenv('NESSIE_REF', 'main'),
                iceberg_rest_uri=os.getenv('ICEBERG_REST_URI')
                or (_nessie_to_iceberg_rest(os.getenv('NESSIE_URI')) if os.getenv('NESSIE_URI') else None),
            ),
            dlt=DLTConfig(
                destination_bucket=os.getenv('DEST_BUCKET', 'dlt-warehouse'),
                dataset_name=os.getenv('DATASET_NAME', 'cdc_data')
            )
        )
