#!/usr/bin/env python3
"""
DLT Native Iceberg Pipeline - CDC from MySQL to Iceberg
Writes native Iceberg format via Nessie catalog with proper table schemas
"""

import os
import sys
import logging
from datetime import datetime
from typing import Iterator, Dict, Any, Optional

import dlt
import pymysql
from pymysqlreplication import BinLogStreamReader
from pymysqlreplication.row_event import (
    DeleteRowsEvent,
    UpdateRowsEvent,
    WriteRowsEvent,
)

# Setup logging
_log_dir = '/logs'
if os.path.exists(_log_dir):
    _handlers = [
        logging.FileHandler(os.path.join(_log_dir, 'iceberg_pipeline.log')),
        logging.StreamHandler()
    ]
else:
    _handlers = [logging.StreamHandler()]

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=_handlers
)
logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================

class PipelineConfig:
    """Pipeline configuration from environment variables"""

    def __init__(self):
        # MySQL configuration
        self.mysql_host = os.getenv('MYSQL_HOST', 'mysql')
        self.mysql_port = int(os.getenv('MYSQL_PORT', '3306'))
        self.mysql_user = os.getenv('MYSQL_USER', 'root')
        self.mysql_password = os.getenv('MYSQL_PASSWORD', 'rootpw')
        self.mysql_database = os.getenv('MYSQL_DATABASE', 'appdb')

        # Nessie/Iceberg configuration
        self.nessie_uri = os.getenv('NESSIE_URI', 'http://nessie:19120/api/v2')
        self.nessie_iceberg_uri = os.getenv('NESSIE_ICEBERG_URI', 'http://nessie:19120/iceberg')
        self.warehouse = os.getenv('ICEBERG_WAREHOUSE', 's3://dlt-warehouse/iceberg')
        self.namespace = os.getenv('ICEBERG_NAMESPACE', 'appdb')

        # S3/MinIO configuration
        self.s3_endpoint = os.getenv('S3_ENDPOINT_URL', 'http://minio:9000')
        self.s3_access_key = os.getenv('S3_ACCESS_KEY', 'minio')
        self.s3_secret_key = os.getenv('S3_SECRET_KEY', 'minio123')
        self.s3_region = os.getenv('AWS_REGION', 'us-east-1')

        # Pipeline configuration
        self.snapshot_mode = os.getenv('SNAPSHOT_MODE', 'initial')  # initial, never
        self.streaming_batch_size = int(os.getenv('STREAMING_BATCH_SIZE', '1000'))
        self.streaming_max_events = int(os.getenv('STREAMING_MAX_EVENTS', '10000'))

        # Tables to capture
        self.tables = os.getenv('TABLE_INCLUDE_LIST', 'appdb.products,appdb.sales').split(',')

    def log_config(self):
        """Log configuration"""
        logger.info("=" * 60)
        logger.info("DLT ICEBERG PIPELINE CONFIGURATION")
        logger.info("=" * 60)
        logger.info(f"MySQL: {self.mysql_user}@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}")
        logger.info(f"Tables: {self.tables}")
        logger.info(f"Nessie: {self.nessie_uri}")
        logger.info(f"Nessie Iceberg: {self.nessie_iceberg_uri}")
        logger.info(f"Warehouse: {self.warehouse}")
        logger.info(f"Namespace: {self.namespace}")
        logger.info(f"Snapshot mode: {self.snapshot_mode}")
        logger.info("=" * 60)


# =============================================================================
# MYSQL CDC SOURCE
# =============================================================================

class MySQLCDCSource:
    """
    MySQL CDC source using pymysql-replication
    Emits DLT resources with proper schema for each table
    """

    # Table schemas - define proper columns for each table
    TABLE_SCHEMAS = {
        'products': {
            'columns': {
                'id': {'type': 'bigint', 'primary_key': True, 'nullable': False},
                'name': {'type': 'varchar', 'nullable': False},
                'description': {'type': 'varchar', 'nullable': True},
                'price': {'type': 'decimal', 'nullable': False},
                'stock': {'type': 'int', 'nullable': False},
                'category': {'type': 'varchar', 'nullable': True},
                'created_at': {'type': 'timestamp', 'nullable': False},
                'updated_at': {'type': 'timestamp', 'nullable': True},
            },
            'partition_by': 'updated_at',
        },
        'sales': {
            'columns': {
                'id': {'type': 'bigint', 'primary_key': True, 'nullable': False},
                'product_id': {'type': 'bigint', 'nullable': False},
                'quantity': {'type': 'int', 'nullable': False},
                'total': {'type': 'decimal', 'nullable': False},
                'customer_name': {'type': 'varchar', 'nullable': True},
                'sale_date': {'type': 'timestamp', 'nullable': False},
                'created_at': {'type': 'timestamp', 'nullable': False},
                'updated_at': {'type': 'timestamp', 'nullable': True},
            },
            'partition_by': 'sale_date',
        }
    }

    def __init__(self, config: PipelineConfig):
        self.config = config
        self.mysql_conn = None
        self.stream_settings = {
            'server_id': 100,  # Fake server ID for this slave
            'blocking': True,
            'only_events': [DeleteRowsEvent, WriteRowsEvent, UpdateRowsEvent],
            'resume_stream': True,
        }

    def _get_mysql_connection(self):
        """Get MySQL connection for snapshot"""
        if self.mysql_conn is None:
            self.mysql_conn = pymysql.connect(
                host=self.config.mysql_host,
                port=self.config.mysql_port,
                user=self.config.mysql_user,
                password=self.config.mysql_password,
                database=self.config.mysql_database,
                cursorclass=pymysql.cursors.DictCursor
            )
        return self.mysql_conn

    def _get_binlog_position(self) -> Optional[Dict[str, Any]]:
        """Get saved binlog position from state"""
        # In production, load from persistent storage
        # For now, return None to start from beginning
        return None

    def _save_binlog_position(self, log_file: str, log_pos: int):
        """Save binlog position for resumption"""
        logger.info(f"Saving binlog position: {log_file}:{log_pos}")
        # In production, save to persistent storage (S3, database, etc.)

    def snapshot_table(self, table_name: str) -> Iterator[Dict[str, Any]]:
        """
        Snapshot a table's current data

        Yields records with metadata for CDC tracking
        """
        logger.info(f"Starting snapshot for table: {table_name}")

        conn = self._get_mysql_connection()

        with conn.cursor() as cursor:
            cursor.execute(f"SELECT * FROM {table_name}")
            columns = [desc[0] for desc in cursor.description]

            row_count = 0
            for row in cursor:
                record = dict(zip(columns, row))

                # Add CDC metadata
                record['__op'] = 'r'  # r = read (snapshot)
                record['__ts_ms'] = int(datetime.now().timestamp() * 1000)
                record['__source'] = 'snapshot'

                yield record
                row_count += 1

                if row_count % 1000 == 0:
                    logger.info(f"  Snapshotted {row_count} rows from {table_name}")

        logger.info(f"Snapshot complete for {table_name}: {row_count} rows")

    def stream_table(self, table_name: str, max_events: int = None) -> Iterator[Dict[str, Any]]:
        """
        Stream CDC events from binlog for a table

        Yields records with metadata for CDC tracking
        """
        logger.info(f"Starting binlog stream for table: {table_name}")

        # Get saved position
        position = self._get_binlog_position()

        # Create binlog stream reader
        stream = BinLogStreamReader(
            connection_settings={
                'host': self.config.mysql_host,
                'port': self.config.mysql_port,
                'user': self.config.mysql_user,
                'passwd': self.config.mysql_password,
            },
            server_id=self.stream_settings['server_id'],
            only_events=self.stream_settings['only_events'],
            resume_stream=(position is not None),
            log_file=position['log_file'] if position else None,
            log_pos=position['log_pos'] if position else None,
            blocking=True,
        )

        event_count = 0

        try:
            for binlog_event in stream:
                # Check if event is for our table
                schema = binlog_event.schema
                table = binlog_event.table

                if schema != self.config.mysql_database or table != table_name:
                    continue

                # Process rows based on event type
                for row in self._process_binlog_event(binlog_event):
                    yield row
                    event_count += 1

                    # Save position periodically
                    if event_count % 100 == 0:
                        self._save_binlog_position(stream.log_file, stream.log_pos)
                        logger.info(f"  Streamed {event_count} events from {table_name}")

                    if max_events and event_count >= max_events:
                        logger.info(f"Reached max events limit: {max_events}")
                        break

                if max_events and event_count >= max_events:
                    break

        finally:
            stream.close()
            # Save final position
            self._save_binlog_position(stream.log_file, stream.log_pos)

        logger.info(f"Binlog stream complete for {table_name}: {event_count} events")

    def _process_binlog_event(self, event) -> Iterator[Dict[str, Any]]:
        """Process a binlog event and yield CDC records"""

        if isinstance(event, WriteRowsEvent):
            # Insert
            for row in event.rows:
                record = row['values'].copy()
                record['__op'] = 'c'  # c = create
                record['__ts_ms'] = int(datetime.now().timestamp() * 1000)
                record['__source'] = 'binlog'
                yield record

        elif isinstance(event, DeleteRowsEvent):
            # Delete
            for row in event.rows:
                record = row['values'].copy()
                record['__op'] = 'd'  # d = delete
                record['__ts_ms'] = int(datetime.now().timestamp() * 1000)
                record['__source'] = 'binlog'
                yield record

        elif isinstance(event, UpdateRowsEvent):
            # Update - yield both old and new
            for row in event.rows:
                # Old values (before update)
                old_record = row['before_values'].copy()
                old_record['__op'] = 'u_old'  # u_old = update (before)
                old_record['__ts_ms'] = int(datetime.now().timestamp() * 1000)
                old_record['__source'] = 'binlog'
                yield old_record

                # New values (after update)
                new_record = row['after_values'].copy()
                new_record['__op'] = 'u_new'  # u_new = update (after)
                new_record['__ts_ms'] = int(datetime.now().timestamp() * 1000)
                new_record['__source'] = 'binlog'
                yield new_record

    def get_table_schema(self, table_name: str) -> Dict[str, Any]:
        """Get DLT schema for a table"""
        base_name = table_name.split('.')[-1]  # Remove schema prefix if present
        return self.TABLE_SCHEMAS.get(base_name, {})

    def get_primary_keys(self, table_name: str) -> list:
        """Get primary key columns for a table"""
        schema = self.get_table_schema(table_name)
        return [col for col, spec in schema.get('columns', {}).items()
                if spec.get('primary_key', False)]

    def get_partition_column(self, table_name: str) -> Optional[str]:
        """Get partition column for a table"""
        schema = self.get_table_schema(table_name)
        return schema.get('partition_by')


# =============================================================================
# DLT RESOURCE GENERATORS
# =============================================================================

def create_table_resource(cdc_source: MySQLCDCSource, table_name: str,
                         snapshot: bool = True, stream: bool = True,
                         max_stream_events: int = None):
    """
    Create a DLT resource for a table

    The resource yields records with CDC metadata (__op, __ts_ms, __source)
    """

    @dlt.resource(
        name=table_name,
        write_disposition='merge',
        primary_key=lambda: cdc_source.get_primary_keys(table_name),
        columns=lambda: cdc_source.get_table_schema(table_name).get('columns', {}),
    )
    def table_resource() -> Iterator[Dict[str, Any]]:
        """Resource for table with CDC tracking"""

        # Snapshot phase
        if snapshot:
            logger.info(f"Starting snapshot phase for {table_name}")
            for record in cdc_source.snapshot_table(table_name):
                yield record

        # Streaming phase
        if stream:
            logger.info(f"Starting streaming phase for {table_name}")
            for record in cdc_source.stream_table(table_name, max_stream_events):
                yield record

    return table_resource


# =============================================================================
# PIPELINE MAIN
# =============================================================================

def setup_iceberg_catalog(config: PipelineConfig) -> dlt.Pipeline:
    """
    Create DLT pipeline with Iceberg destination

    Configures Nessie as the Iceberg REST catalog
    """

    # Configure Iceberg catalog environment variables
    os.environ['DESTINATION__ICEBERG__URI'] = config.nessie_iceberg_uri
    os.environ['DESTINATION__ICEBERG__TYPE'] = 'rest'

    # Configure S3 for Iceberg data files
    os.environ['DESTINATION__ICEBERG__S3_ENDPOINT'] = config.s3_endpoint
    os.environ['DESTINATION__ICEBERG__S3_ACCESS_KEY_ID'] = config.s3_access_key
    os.environ['DESTINATION__ICEBERG__S3_SECRET_ACCESS_KEY'] = config.s3_secret_key
    os.environ['DESTINATION__ICEBERG__S3_REGION'] = config.s3_region
    os.environ['DESTINATION__ICEBERG__S3_PATH_STYLE_ACCESS'] = 'true'

    # Warehouse location
    os.environ['DESTINATION__ICEBERG__WAREHOUSE'] = config.warehouse

    logger.info("Configured Iceberg destination:")
    logger.info(f"  Catalog URI: {config.nessie_iceberg_uri}")
    logger.info(f"  Warehouse: {config.warehouse}")
    logger.info(f"  S3 Endpoint: {config.s3_endpoint}")

    # Create pipeline
    pipeline = dlt.pipeline(
        pipeline_name='mysql_to_iceberg',
        destination='iceberg',
        dataset_name=config.namespace,
    )

    return pipeline


def main():
    """Main entry point"""

    config = PipelineConfig()
    config.log_config()

    # Create CDC source
    cdc_source = MySQLCDCSource(config)

    # Setup Iceberg pipeline
    pipeline = setup_iceberg_catalog(config)

    # Parse table names
    tables = [t.strip() for t in config.tables if t.strip()]

    if not tables:
        logger.error("No tables configured! Set TABLE_INCLUDE_LIST environment variable.")
        return 1

    # Determine snapshot mode
    snapshot = config.snapshot_mode == 'initial'

    logger.info(f"Processing tables: {tables}")
    logger.info(f"Snapshot: {snapshot}")
    logger.info(f"Max streaming events: {config.streaming_max_events}")

    try:
        # Run pipeline for each table
        for table_full_name in tables:
            # Extract table name (remove schema prefix)
            table_name = table_full_name.split('.')[-1]

            logger.info("=" * 60)
            logger.info(f"Processing table: {table_name}")
            logger.info("=" * 60)

            # Create resource for this table
            resource = create_table_resource(
                cdc_source,
                table_name,
                snapshot=snapshot,
                stream=True,
                max_stream_events=config.streaming_max_events
            )

            # Run pipeline
            info = pipeline.run(
                resource,
                table_name=table_name,
            )

            logger.info(f"Pipeline run info: {info}")

        logger.info("=" * 60)
        logger.info("Pipeline completed successfully!")
        logger.info("=" * 60)

        # Print summary
        logger.info(f"Data written to:")
        logger.info(f"  Catalog: {config.nessie_uri}")
        logger.info(f"  Namespace: {config.namespace}")
        logger.info(f"  Tables: {', '.join([t.split('.')[-1] for t in tables])}")
        logger.info(f"  Warehouse: {config.warehouse}")

        return 0

    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())
