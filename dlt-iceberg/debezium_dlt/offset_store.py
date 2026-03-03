"""
Offset Store - Stores CDC offsets in Iceberg/MinIO
Persists GTID positions and binlog offsets
"""

import json
import logging
from typing import Dict, Optional
from datetime import datetime
from pathlib import Path

import dlt
from .config import IcebergConfig

logger = logging.getLogger(__name__)


class OffsetStore:
    """
    Stores and retrieves CDC offsets using DLT + Iceberg
    This replaces Kafka offset storage
    """

    def __init__(self, iceberg_config: IcebergConfig, pipeline_name: str = 'debezium_offset_store'):
        """
        Initialize offset store

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

    def save_offset(self, partition: str, offset: Dict) -> bool:
        """
        Save offset for a partition

        Args:
            partition: Partition key (e.g., server UUID)
            offset: Offset data (GTID set, binlog position, etc.)

        Returns:
            True if successful
        """
        try:
            offset_record = {
                'partition': partition,
                'gtid_set': offset.get('gtid_set', ''),
                'binlog_file': offset.get('binlog_file', ''),
                'binlog_position': offset.get('binlog_position', 0),
                'server_id': offset.get('server_id', 0),
                'timestamp': datetime.now().isoformat(),
                'snapshot_completed': offset.get('snapshot_completed', False)
            }

            # Use DLT to write offset
            pipeline = dlt.pipeline(
                pipeline_name=self.pipeline_name,
                destination='filesystem',
                dataset_name='offsets'
            )

            # Convert to list for DLT
            pipeline.run([offset_record], table_name='offsets', write_disposition='append')

            logger.info(f"💾 Saved offset for partition '{partition}': GTID={offset.get('gtid_set', 'N/A')}")
            return True

        except Exception as e:
            logger.error(f"Failed to save offset: {e}")
            return False

    def load_offset(self, partition: str) -> Optional[Dict]:
        """
        Load offset for a partition

        Args:
            partition: Partition key

        Returns:
            Offset dict or None if not found
        """
        try:
            # Read from DLT's stored data (DLT may write to subdirs: offsets/offsets/**/*.jsonl.gz)
            import os
            base = f"s3://{self.iceberg_config.checkpoint_bucket}"
            # DLT may write to offsets/offsets/ or offsets/offsets/<load_id>/
            offset_glob = f"{base}/offsets/offsets/*.jsonl.gz"

            import duckdb
            con = duckdb.connect(':memory:')

            endpoint = self.iceberg_config.endpoint_url.replace('http://', '').replace('https://', '').strip('/')
            con.execute(f"""
                INSTALL httpfs;
                LOAD httpfs;
                SET s3_endpoint = '{endpoint}';
                SET s3_access_key_id = '{self.iceberg_config.access_key}';
                SET s3_secret_access_key = '{self.iceberg_config.secret_key}';
                SET s3_use_ssl = false;
                SET s3_url_style = 'path';
            """)

            # Query for this partition (use fetchall to avoid pandas/numpy dependency)
            result = con.execute(f"""
                SELECT partition, gtid_set, binlog_file, binlog_position, server_id, timestamp, snapshot_completed
                FROM read_json_auto('{offset_glob}', union_by_name=true)
                WHERE partition = '{partition}'
                ORDER BY timestamp DESC
                LIMIT 1
            """).fetchall()

            if result:
                row = result[0]
                # row: (partition, gtid_set, binlog_file, binlog_position, server_id, timestamp, snapshot_completed)
                offset = {
                    'gtid_set': row[1] or '',
                    'binlog_file': row[2] or '',
                    'binlog_position': int(row[3] or 0),
                    'server_id': int(row[4] or 0),
                    'snapshot_completed': bool(row[6]) if len(row) > 6 and row[6] is not None else False
                }
                logger.info(f"📥 Loaded offset for partition '{partition}': GTID={offset['gtid_set']}")
                return offset

            logger.info(f"📥 No offset found for partition '{partition}' (will start from current position)")
            return None

        except Exception as e:
            # No files yet (first run) is expected - do not log as ERROR
            err_msg = str(e).lower()
            if "no files found" in err_msg or "could not open" in err_msg:
                logger.info(f"No offset file yet for partition '{partition}', will start from current position")
            else:
                logger.error(f"Failed to load offset: {e}")
            return None

    def delete_offset(self, partition: str) -> bool:
        """
        Delete offset for a partition

        Args:
            partition: Partition key

        Returns:
            True if successful
        """
        try:
            # For file-based storage, we can't easily delete
            # We'll just overwrite with a new empty offset
            return self.save_offset(partition, {
                'gtid_set': '',
                'binlog_file': '',
                'binlog_position': 0,
                'server_id': 0,
                'snapshot_completed': False
            })
        except Exception as e:
            logger.error(f"Failed to delete offset: {e}")
            return False
