"""
Schema History - Tracks database schema changes
Stores schema evolution in Iceberg
"""

import json
import logging
from typing import Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass, asdict

import dlt
from .config import IcebergConfig

logger = logging.getLogger(__name__)


@dataclass
class SchemaChangeEvent:
    """Represents a schema change event"""
    table_name: str
    database: str
    schema_version: int
    columns: Dict[str, str]  # column_name: data_type
    primary_keys: List[str]
    change_type: str  # CREATE, ALTER, DROP
    gtid: Optional[str] = None
    timestamp: str = ''

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return asdict(self)


class SchemaHistory:
    """
    Tracks schema history using DLT + Iceberg
    Ensures schema changes are captured and can be replayed
    """

    def __init__(self, iceberg_config: IcebergConfig, pipeline_name: str = 'debezium_schema_history'):
        """
        Initialize schema history

        Args:
            iceberg_config: Iceberg/MinIO configuration
            pipeline_name: Name for DLT pipeline
        """
        self.iceberg_config = iceberg_config
        self.pipeline_name = pipeline_name

        # Setup DLT environment
        import os
        os.environ['DESTINATION__FILESYSTEM__BUCKET_URL'] = f"s3://{iceberg_config.checkpoint_bucket}"
        os.environ['DESTINATION__FILESYSTEM__CREDENTIALS__AWS_ACCESS_KEY_ID'] = iceberg_config.access_key
        os.environ['DESTINATION__FILESYSTEM__CREDENTIALS__AWS_SECRET_ACCESS_KEY'] = iceberg_config.secret_key
        os.environ['DESTINATION__FILESYSTEM__CREDENTIALS__ENDPOINT_URL'] = iceberg_config.endpoint_url

    def record_schema(self, schema_event: SchemaChangeEvent) -> bool:
        """
        Record a schema change event

        Args:
            schema_event: Schema change event

        Returns:
            True if successful
        """
        try:
            if not schema_event.timestamp:
                schema_event.timestamp = datetime.now().isoformat()

            pipeline = dlt.pipeline(
                pipeline_name=self.pipeline_name,
                destination='filesystem',
                dataset_name='schema_history'
            )

            pipeline.run(
                [schema_event.to_dict()],
                table_name='schema_changes',
                write_disposition='append'
            )

            logger.info(f"📝 Recorded schema change: {schema_event.database}.{schema_event.table_name} v{schema_event.schema_version}")
            return True

        except Exception as e:
            logger.error(f"Failed to record schema: {e}")
            return False

    def get_latest_schema(self, database: str, table_name: str) -> Optional[SchemaChangeEvent]:
        """
        Get the latest schema for a table

        Args:
            database: Database name
            table_name: Table name

        Returns:
            Latest SchemaChangeEvent or None
        """
        try:
            import duckdb
            con = duckdb.connect(':memory:')

            # Configure S3
            con.execute(f"""
                INSTALL httpfs;
                LOAD httpfs;
                SET s3_endpoint = '{self.iceberg_config.endpoint_url.replace('http://', '').replace('https://', '')}';
                SET s3_access_key_id = '{self.iceberg_config.access_key}';
                SET s3_secret_access_key = '{self.iceberg_config.secret_key}';
                SET s3_use_ssl = false;
                SET s3_url_style = 'path';
            """)

            # Query latest schema
            schema_file = f"s3://{self.iceberg_config.checkpoint_bucket}/schema_history/schema_changes/*.jsonl.gz"
            result = con.execute(f"""
                SELECT * FROM read_json_auto('{schema_file}', union_by_name=true)
                WHERE database = '{database}' AND table_name = '{table_name}'
                ORDER BY schema_version DESC
                LIMIT 1
            """).fetchdf()

            if len(result) > 0:
                row = result.iloc[0]
                cols = row['columns']
                pks = row['primary_keys']
                if isinstance(cols, str):
                    cols = json.loads(cols) if cols else {}
                if isinstance(pks, str):
                    pks = json.loads(pks) if pks else []
                return SchemaChangeEvent(
                    table_name=row['table_name'],
                    database=row['database'],
                    schema_version=int(row['schema_version']),
                    columns=cols,
                    primary_keys=pks,
                    change_type=row['change_type'],
                    gtid=row.get('gtid'),
                    timestamp=row['timestamp']
                )

            return None

        except Exception as e:
            logger.error(f"Failed to get latest schema: {e}")
            return None

    def get_all_schemas(self) -> List[SchemaChangeEvent]:
        """
        Get all recorded schemas

        Returns:
            List of SchemaChangeEvent
        """
        try:
            import duckdb
            con = duckdb.connect(':memory:')

            # Configure S3
            con.execute(f"""
                INSTALL httpfs;
                LOAD httpfs;
                SET s3_endpoint = '{self.iceberg_config.endpoint_url.replace('http://', '').replace('https://', '')}';
                SET s3_access_key_id = '{self.iceberg_config.access_key}';
                SET s3_secret_access_key = '{self.iceberg_config.secret_key}';
                SET s3_use_ssl = false;
                SET s3_url_style = 'path';
            """)

            # Query all schemas
            schema_file = f"s3://{self.iceberg_config.checkpoint_bucket}/schema_history/schema_changes/*.jsonl.gz"
            result = con.execute(f"""
                SELECT * FROM read_json_auto('{schema_file}', union_by_name=true)
                ORDER BY database, table_name, schema_version
            """).fetchdf()

            schemas = []
            for _, row in result.iterrows():
                schemas.append(SchemaChangeEvent(
                    table_name=row['table_name'],
                    database=row['database'],
                    schema_version=int(row['schema_version']),
                    columns=json.loads(row['columns']) if isinstance(row['columns'], str) else row['columns'],
                    primary_keys=json.loads(row['primary_keys']) if isinstance(row['primary_keys'], str) else row['primary_keys'],
                    change_type=row['change_type'],
                    gtid=row.get('gtid'),
                    timestamp=row['timestamp']
                ))

            return schemas

        except Exception as e:
            logger.error(f"Failed to get all schemas: {e}")
            return []
