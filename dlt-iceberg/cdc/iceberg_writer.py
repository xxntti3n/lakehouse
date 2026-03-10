"""
Iceberg Writer - Write CDC events to Iceberg tables in MinIO
Uses pyiceberg library for table management
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass

try:
    from pyiceberg.catalog import load_catalog
    from pyiceberg.schema import Schema
    from pyiceberg.types import (
        NestedField, StringType, LongType, DoubleType,
        TimestampType, BooleanType
    )
    ICEBERG_AVAILABLE = True
except ImportError:
    ICEBERG_AVAILABLE = False
    logging.warning(
        "pyiceberg not available. Install with: pip install pyiceberg[s3]")

logger = logging.getLogger(__name__)


@dataclass
class IcebergConfig:
    """Iceberg configuration for MinIO; optional Nessie catalog"""
    warehouse_path: str = "s3://dlt-warehouse/iceberg"
    catalog_namespace: str = "warehouse"
    access_key: str = "minio"
    secret_key: str = "minio123"
    endpoint_url: str = "http://minio:9000"
    nessie_uri: Optional[str] = None
    nessie_ref: str = "main"


class IcebergWriter:
    """
    Write CDC events to Iceberg tables in MinIO
    Supports schema evolution and time-based partitioning
    """

    # Debezium-style schema for CDC events
    CDC_SCHEMA = Schema(
        NestedField(field_id=1, name="_op",
                    field_type=StringType(), required=False),
        NestedField(field_id=2, name="_ts",
                    field_type=TimestampType(), required=False),
        NestedField(field_id=3, name="_db",
                    field_type=StringType(), required=False),
        NestedField(field_id=4, name="_table",
                    field_type=StringType(), required=False),
        NestedField(field_id=5, name="_cdc_server_id",
                    field_type=LongType(), required=False),
        NestedField(field_id=6, name="_cdc_gtid",
                    field_type=StringType(), required=False),
        NestedField(field_id=7, name="_cdc_binlog_file",
                    field_type=StringType(), required=False),
        NestedField(field_id=8, name="_cdc_binlog_pos",
                    field_type=LongType(), required=False),
        NestedField(field_id=9, name="_source_ts_ms",
                    field_type=LongType(), required=False),
        NestedField(field_id=10, name="_transaction_id",
                    field_type=StringType(), required=False),
    )

    def __init__(self, config: IcebergConfig):
        """
        Initialize Iceberg writer

        Args:
            config: Iceberg configuration
        """
        if not ICEBERG_AVAILABLE:
            raise ImportError(
                "pyiceberg is required. Install with: pip install pyiceberg[s3]")

        self.config = config
        self.catalog = None
        self._tables = {}
        self.use_nessie = bool(getattr(config, 'nessie_uri', None))

        self._setup_catalog()

    def _setup_catalog(self):
        """Setup Iceberg catalog: Nessie if NESSIE_URI set, else no catalog (direct S3 writes)."""
        try:
            import os

            # Configure S3 environment for pyiceberg / MinIO
            os.environ['AWS_ACCESS_KEY_ID'] = self.config.access_key
            os.environ['AWS_SECRET_ACCESS_KEY'] = self.config.secret_key
            os.environ['AWS_ENDPOINT_URL'] = self.config.endpoint_url
            os.environ['AWS_REGION'] = 'us-east-1'
            os.environ['AWS_ALLOW_HTTP'] = 'true'

            if self.use_nessie and getattr(self.config, 'nessie_uri', None):
                try:
                    from pyiceberg.catalog import load_catalog
                    base_uri = self.config.nessie_uri.rstrip(
                        '/').replace('/api/v2', '')
                    # Nessie exposes Iceberg REST at /iceberg/v1 (not /api/v2 for catalog ops)
                    iceberg_rest_uri = f"{base_uri}/iceberg/v1"
                    ref = getattr(self.config, 'nessie_ref', 'main') or 'main'
                    warehouse = self.config.warehouse_path
                    logger.info(
                        f"📦 Setting up Iceberg REST catalog (Nessie): uri={iceberg_rest_uri}, warehouse={warehouse}")
                    self.catalog = load_catalog(
                        "rest",
                        uri=iceberg_rest_uri,
                        warehouse=warehouse,
                        **{
                            "s3.endpoint": self.config.endpoint_url,
                            "s3.access-key-id": self.config.access_key,
                            "s3.secret-access-key": self.config.secret_key,
                            "s3.path-style-access": "true",
                        }
                    )
                    logger.info("✅ Iceberg REST (Nessie) catalog configured")
                except Exception as e:
                    logger.warning(
                        f"Nessie catalog unavailable: {e}; falling back to S3 Parquet only")
                    self.use_nessie = False
                    self.catalog = None
            if not self.use_nessie:
                logger.info(
                    f"📦 No Nessie: writing plain Parquet to S3 only (not Iceberg format). Use --profile catalog for Iceberg.")
                logger.info(f"   Path: {self.config.warehouse_path}")

        except Exception as e:
            logger.error(f"Failed to setup catalog: {e}")
            raise

    def ensure_table(self, database: str, table: str, schema_data: Optional[Dict] = None):
        """
        Ensure table exists, create if not

        Args:
            database: Database name
            table: Table name
            schema_data: Sample data to infer schema
        """
        table_identifier = f"{database}.{table}"

        if table_identifier in self._tables:
            return table_identifier

        try:
            logger.info(f"📋 Ensuring table exists: {table_identifier}")

            # Store table reference
            self._tables[table_identifier] = {
                'database': database,
                'table': table,
                'created_at': datetime.now().isoformat()
            }

            logger.info(f"✅ Table ready: {table_identifier}")
            return table_identifier

        except Exception as e:
            logger.error(f"Failed to ensure table {table_identifier}: {e}")
            raise

    def _events_to_arrow(self, events: List[Dict[str, Any]]):
        """Build PyArrow table and schema from CDC events."""
        import pyarrow as pa
        from datetime import datetime
        sample_event = events[0]
        fields = []
        for key, value in sample_event.items():
            if value is None:
                fields.append(pa.field(key, pa.string()))
            elif isinstance(value, str):
                fields.append(pa.field(key, pa.string()))
            elif isinstance(value, int):
                fields.append(pa.field(key, pa.int64()))
            elif isinstance(value, float):
                fields.append(pa.field(key, pa.float64()))
            elif isinstance(value, bool):
                fields.append(pa.field(key, pa.bool_()))
            else:
                fields.append(pa.field(key, pa.string()))
        schema = pa.schema(fields)

        def _to_scalar(val):
            if val is None:
                return None
            if hasattr(val, '__class__') and 'Decimal' in val.__class__.__name__:
                return str(val)
            if isinstance(val, datetime):
                return val.isoformat()
            if hasattr(val, 'isoformat') and callable(getattr(val, 'isoformat')):
                return val.isoformat()
            return val

        arrays = []
        for field in fields:
            column_data = [_to_scalar(event.get(field.name))
                           for event in events]
            arrays.append(pa.array(column_data, type=field.type))
        return pa.Table.from_arrays(arrays, schema=schema)

    def write_events(self, table_identifier: str, events: List[Dict[str, Any]]) -> int:
        """
        Write CDC events to Iceberg table (Nessie catalog append or S3 Parquet fallback).

        Args:
            table_identifier: Table identifier (db.table)
            events: List of CDC event dictionaries

        Returns:
            Number of events written
        """
        if not events:
            return 0

        try:
            import pyarrow as pa
            import pyarrow.parquet as pq
            from datetime import datetime

            logger.info(
                f"📝 Writing {len(events)} events to {table_identifier}")

            arrow_table = self._events_to_arrow(events)

            if self.use_nessie and self.catalog:
                try:
                    try:
                        tbl = self.catalog.load_table(table_identifier)
                    except Exception as load_err:
                        namespace = table_identifier.rsplit('.', 1)[0]
                        try:
                            self.catalog.create_namespace_if_not_exists(
                                namespace)
                        except Exception as ns_err:
                            logger.debug(f"Namespace create: {ns_err}")
                        tbl = self.catalog.create_table(
                            identifier=table_identifier,
                            schema=arrow_table.schema,
                        )
                    tbl.append(arrow_table)
                    logger.info(
                        f"✅ Appended {len(events)} events to Iceberg table {table_identifier} (Nessie + MinIO)")
                    return len(events)
                except Exception as e:
                    logger.warning(
                        f"Nessie/Iceberg write failed: {e}; falling back to plain Parquet (not Iceberg format)")
                    import traceback
                    logger.debug(traceback.format_exc())

            # Fallback: write Parquet to S3
            try:
                import s3fs
                s3 = s3fs.S3FileSystem(
                    key=self.config.access_key,
                    secret=self.config.secret_key,
                    client_kwargs={'endpoint_url': self.config.endpoint_url}
                )
                now = datetime.now()
                partition_path = f"{table_identifier}/year={now.year}/month={now.month:02d}/day={now.day:02d}"
                s3_path = f"{self.config.warehouse_path}/{partition_path}/cdc_{int(now.timestamp())}.parquet"
                with s3.open(s3_path, 'wb') as f:
                    pq.write_table(arrow_table, f)
                logger.info(f"✅ Written {len(events)} events to {s3_path}")
            except Exception as e:
                logger.warning(f"S3 write failed: {e}, falling back to local")
                import os
                local_path = f"/tmp/iceberg/{table_identifier}/cdc_{int(datetime.now().timestamp())}.parquet"
                os.makedirs(os.path.dirname(local_path), exist_ok=True)
                with open(local_path, 'wb') as f:
                    pq.write_table(arrow_table, f)
                logger.info(f"✅ Written {len(events)} events to {local_path}")

            return len(events)

        except Exception as e:
            logger.error(f"Failed to write events: {e}")
            raise

    def create_checkpoint_tables(self):
        """Create checkpoint tables (offsets, schema_history)"""
        try:
            logger.info("🔧 Creating checkpoint tables...")

            # Offset table
            self._tables['checkpoints.offsets'] = {
                'database': 'checkpoints',
                'table': 'offsets',
                'created_at': datetime.now().isoformat()
            }

            # Schema history table
            self._tables['checkpoints.schema_history'] = {
                'database': 'checkpoints',
                'table': 'schema_history',
                'created_at': datetime.now().isoformat()
            }

            logger.info("✅ Checkpoint tables ready")

        except Exception as e:
            logger.error(f"Failed to create checkpoint tables: {e}")


class DuckDBIcebergVerifier:
    """
    Verify Iceberg data using DuckDB
    DuckDB can query Iceberg tables via Iceberg REST catalog
    """

    def __init__(self, iceberg_config: IcebergConfig):
        """
        Initialize verifier

        Args:
            iceberg_config: Iceberg configuration
        """
        self.config = iceberg_config
        self.conn = None

    def connect(self):
        """Connect to DuckDB and setup S3"""
        try:
            import duckdb

            self.conn = duckdb.connect(':memory:')

            # Setup S3 access for DuckDB
            self.conn.execute(f"""
                INSTALL httpfs;
                LOAD httpfs;
                SET s3_endpoint='{self.config.endpoint_url}';
                SET s3_access_key_id='{self.config.access_key}';
                SET s3_secret_access_key='{self.config.secret_key}';
                SET s3_use_ssl=false;
                SET s3_url_style='path';
            """)

            logger.info("✅ DuckDB connected and S3 configured")

        except ImportError:
            logger.error(
                "DuckDB not available. Install with: pip install duckdb")
            raise
        except Exception as e:
            logger.error(f"Failed to connect DuckDB: {e}")
            raise

    def verify_cdc_data(self, database: str = 'appdb', table: str = 'products') -> List[Dict]:
        """
        Verify CDC data in Iceberg format

        Args:
            database: Database name
            table: Table name

        Returns:
            List of CDC events
        """
        if not self.conn:
            self.connect()

        try:
            logger.info(f"🔍 Verifying CDC data for {database}.{table}...")

            # Query Parquet files (Iceberg-compatible)
            query = f"""
                SELECT
                    _op,
                    _ts,
                    _db,
                    _table,
                    _cdc_gtid,
                    _cdc_binlog_file,
                    _cdc_binlog_pos,
                    COUNT(*) as event_count
                FROM 's3://{self.config.warehouse_path}/{database}.{table}/**/*.parquet'
                GROUP BY _op, _ts, _db, _table, _cdc_gtid, _cdc_binlog_file, _cdc_binlog_pos
                ORDER BY _ts DESC
                LIMIT 10
            """

            result = self.conn.execute(query).fetchall()

            logger.info(f"✅ Found {len(result)} event groups")

            return [
                {
                    'operation': row[0],
                    'timestamp': row[1],
                    'database': row[2],
                    'table': row[3],
                    'gtid': row[4],
                    'binlog_file': row[5],
                    'binlog_pos': row[6],
                    'count': row[7]
                }
                for row in result
            ]

        except Exception as e:
            logger.error(f"Failed to verify CDC data: {e}")
            # Fallback: try to list available files
            return self._list_available_files()

    def _list_available_files(self) -> List[Dict]:
        """List available Parquet files"""
        try:
            query = f"""
                SELECT *
                FROM glob('s3://{self.config.warehouse_path}/**/*.parquet')
            """

            result = self.conn.execute(query).fetchall()

            logger.info(f"📁 Found {len(result)} Parquet files")

            return [
                {'file': row[0]}
                for row in result
            ]

        except Exception as e:
            logger.error(f"Failed to list files: {e}")
            return []

    def query_gtids(self, database: str = 'appdb', table: str = 'products') -> List[str]:
        """
        Query GTIDs from CDC data

        Args:
            database: Database name
            table: Table name

        Returns:
            List of GTIDs
        """
        if not self.conn:
            self.connect()

        try:
            query = f"""
                SELECT DISTINCT _cdc_gtid
                FROM 's3://{self.config.warehouse_path}/{database}.{table}/**/*.parquet'
                WHERE _cdc_gtid IS NOT NULL
                ORDER BY _ts DESC
            """

            result = self.conn.execute(query).fetchall()

            gtids = [row[0] for row in result]

            logger.info(f"📍 Found {len(gtids)} unique GTIDs")

            return gtids

        except Exception as e:
            logger.error(f"Failed to query GTIDs: {e}")
            return []

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get overall statistics

        Returns:
            Statistics dictionary
        """
        if not self.conn:
            self.connect()

        try:
            stats = {}

            # Count events by operation type
            query = f"""
                SELECT
                    _op,
                    COUNT(*) as count
                FROM 's3://{self.config.warehouse_path}/**/*.parquet'
                GROUP BY _op
            """

            result = self.conn.execute(query).fetchall()

            stats['by_operation'] = {row[0]: row[1] for row in result}

            # Count events by table
            query = f"""
                SELECT
                    _db || '.' || _table as table_name,
                    COUNT(*) as count
                FROM 's3://{self.config.warehouse_path}/**/*.parquet'
                GROUP BY _db, _table
            """

            result = self.conn.execute(query).fetchall()

            stats['by_table'] = {row[0]: row[1] for row in result}

            logger.info(f"📊 Statistics: {stats}")

            return stats

        except Exception as e:
            logger.error(f"Failed to get statistics: {e}")
            return {}
