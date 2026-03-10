"""
Snapshot Manager - Handles initial and incremental snapshots
Debezium-style non-blocking snapshots with GTID watermarks
"""

import logging
import pymysql
from typing import Dict, List, Generator, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass

from .config import MySQLConfig
from .events import ChangeEvent, EventType, SourceInfo
from .schema_history import SchemaHistory, SchemaChangeEvent

logger = logging.getLogger(__name__)


@dataclass
class SnapshotChunk:
    """A chunk of data from snapshot"""
    rows: List[Dict]
    low_watermark_gtid: str
    high_watermark_gtid: str
    chunk_start: int
    chunk_end: int


class SnapshotManager:
    """
    Manages database snapshots with GTID-based watermarks
    Supports both initial and incremental snapshot modes
    """

    def __init__(self, mysql_config: MySQLConfig, schema_history: SchemaHistory):
        """
        Initialize snapshot manager

        Args:
            mysql_config: MySQL configuration
            schema_history: Schema history manager
        """
        self.mysql_config = mysql_config
        self.schema_history = schema_history
        self.chunk_size = mysql_config.snapshot_chunk_size

    def get_connection(self):
        """Get MySQL connection"""
        return pymysql.connect(
            host=self.mysql_config.host,
            port=self.mysql_config.port,
            user=self.mysql_config.user,
            password=self.mysql_config.password,
            database=self.mysql_config.database
        )

    def get_gtid_set(self) -> str:
        """Get current GTID set from MySQL"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute("SELECT @@GLOBAL.GTID_EXECUTED")
            result = cursor.fetchone()

            cursor.close()
            conn.close()

            return result[0] if result else ''

        except Exception as e:
            logger.error(f"Failed to get GTID set: {e}")
            return ''

    def get_table_schema(self, table_name: str) -> Tuple[Dict[str, str], List[str]]:
        """
        Get table schema (columns and primary keys)

        Args:
            table_name: Name of table

        Returns:
            Tuple of (columns dict, primary keys list)
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor(pymysql.cursors.DictCursor)

            # Get column info
            cursor.execute(f"""
                SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, COLUMN_KEY
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
                ORDER BY ORDINAL_POSITION
            """, (self.mysql_config.database, table_name))

            columns = {}
            primary_keys = []

            for row in cursor.fetchall():
                col_name = row['COLUMN_NAME']
                columns[col_name] = row['DATA_TYPE']
                if row['COLUMN_KEY'] == 'PRI':
                    primary_keys.append(col_name)

            cursor.close()
            conn.close()

            return columns, primary_keys

        except Exception as e:
            logger.error(f"Failed to get schema for {table_name}: {e}")
            return {}, []

    def record_table_schema(self, table_name: str, gtid: Optional[str] = None):
        """
        Record table schema in schema history

        Args:
            table_name: Name of table
            gtid: Optional GTID position
        """
        try:
            latest_schema = self.schema_history.get_latest_schema(
                self.mysql_config.database,
                table_name
            )

            if latest_schema:
                columns = latest_schema.columns
                primary_keys = latest_schema.primary_keys
            else:
                columns, primary_keys = {}, []
        except Exception as e:
            logger.warning(f"Could not load latest schema, will create new one: {e}")
            columns, primary_keys = {}, []

        # Check if schema changed
        current_columns, current_pks = self.get_table_schema(table_name)

        if not columns or current_columns != columns:
            # Schema changed or first time
            schema_version = 1 if not columns else columns.get('schema_version', 0) + 1

            schema_event = SchemaChangeEvent(
                table_name=table_name,
                database=self.mysql_config.database,
                schema_version=schema_version,
                columns=current_columns,
                primary_keys=current_pks,
                change_type='CREATE' if not columns else 'ALTER',
                gtid=gtid,
                timestamp=datetime.now().isoformat()
            )

            self.schema_history.record_schema(schema_event)

    def initial_snapshot(self, table_name: str) -> Generator[ChangeEvent, None, None]:
        """
        Perform initial snapshot of a table (blocking mode for simplicity)

        Args:
            table_name: Name of table

        Yields:
            ChangeEvent for each row
        """
        try:
            logger.info(f"📸 Starting initial snapshot for {table_name}")

            # Record schema
            self.record_table_schema(table_name)

            conn = self.get_connection()
            cursor = conn.cursor(pymysql.cursors.DictCursor)

            # Get primary keys
            _, primary_keys = self.get_table_schema(table_name)

            # Get row count
            cursor.execute(f"SELECT COUNT(*) as total FROM {table_name}")
            total_rows = cursor.fetchone()['total']

            logger.info(f"   Table {table_name} has {total_rows} rows")

            # Read all data
            cursor.execute(f"SELECT * FROM {table_name}")

            rows_processed = 0
            gtid = self.get_gtid_set()

            for row in cursor:
                # Build primary key dict
                primary_key = {pk: row[pk] for pk in primary_keys if pk in row}

                yield ChangeEvent.from_snapshot_row(
                    row=row,
                    database=self.mysql_config.database,
                    table=table_name,
                    primary_key=primary_key,
                    gtid_info=gtid
                )

                rows_processed += 1
                if rows_processed % 1000 == 0:
                    logger.info(f"   Snapshotted {rows_processed}/{total_rows} rows")

            cursor.close()
            conn.close()

            logger.info(f"✅ Initial snapshot complete for {table_name}: {rows_processed} rows")

        except Exception as e:
            logger.error(f"Initial snapshot failed for {table_name}: {e}")
            raise

    def incremental_snapshot_chunk(self, table_name: str, chunk_start: int,
                                   chunk_end: int) -> SnapshotChunk:
        """
        Read a chunk for incremental snapshot with GTID watermarks

        Args:
            table_name: Name of table
            chunk_start: Starting primary key value
            chunk_end: Ending primary key value

        Returns:
            SnapshotChunk with data and GTID watermarks
        """
        try:
            # Get low watermark GTID
            low_gtid = self.get_gtid_set()

            # Read chunk data
            conn = self.get_connection()
            cursor = conn.cursor(pymysql.cursors.DictCursor)

            # Get primary key column
            _, primary_keys = self.get_table_schema(table_name)
            pk_column = primary_keys[0] if primary_keys else 'id'

            cursor.execute(f"""
                SELECT * FROM {table_name}
                WHERE {pk_column} BETWEEN %s AND %s
                ORDER BY {pk_column}
            """, (chunk_start, chunk_end))

            rows = list(cursor.fetchall())

            cursor.close()
            conn.close()

            # Get high watermark GTID
            high_gtid = self.get_gtid_set()

            return SnapshotChunk(
                rows=rows,
                low_watermark_gtid=low_gtid,
                high_watermark_gtid=high_gtid,
                chunk_start=chunk_start,
                chunk_end=chunk_end
            )

        except Exception as e:
            logger.error(f"Incremental snapshot chunk failed: {e}")
            raise

    def incremental_snapshot(self, table_name: str) -> Generator[ChangeEvent, None, None]:
        """
        Perform incremental snapshot (non-blocking)

        Args:
            table_name: Name of table

        Yields:
            ChangeEvent for each row
        """
        try:
            logger.info(f"📸 Starting incremental snapshot for {table_name}")

            # Record schema
            self.record_table_schema(table_name)

            # Get primary key and row count
            conn = self.get_connection()
            cursor = conn.cursor(pymysql.cursors.DictCursor)

            _, primary_keys = self.get_table_schema(table_name)
            pk_column = primary_keys[0] if primary_keys else 'id'

            cursor.execute(f"SELECT MIN({pk_column}) as min_id, MAX({pk_column}) as max_id, COUNT(*) as total FROM {table_name}")
            row_info = cursor.fetchone()

            cursor.close()
            conn.close()

            min_id = row_info['min_id'] or 0
            max_id = row_info['max_id'] or 0
            total_rows = row_info['total']

            logger.info(f"   Table {table_name}: ID range {min_id}-{max_id}, {total_rows} rows")

            # Process in chunks
            current_id = min_id
            chunk_num = 0

            while current_id <= max_id:
                chunk_start = current_id
                chunk_end = min(current_id + self.chunk_size - 1, max_id)

                chunk_num += 1
                logger.info(f"   Processing chunk {chunk_num}: IDs {chunk_start}-{chunk_end}")

                # Read chunk with watermarks
                chunk = self.incremental_snapshot_chunk(table_name, chunk_start, chunk_end)

                # Yield events for each row
                for row in chunk.rows:
                    primary_key = {pk: row[pk] for pk in primary_keys if pk in row}

                    yield ChangeEvent.from_snapshot_row(
                        row=row,
                        database=self.mysql_config.database,
                        table=table_name,
                        primary_key=primary_key,
                        gtid_info=chunk.high_watermark_gtid
                    )

                current_id = chunk_end + 1

            logger.info(f"✅ Incremental snapshot complete for {table_name}: {total_rows} rows in {chunk_num} chunks")

        except Exception as e:
            logger.error(f"Incremental snapshot failed for {table_name}: {e}")
            raise
