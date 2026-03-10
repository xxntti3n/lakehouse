"""
Binlog Streamer - Real-time CDC from MySQL binlog
Uses pymysqlreplication to stream binlog events.
Implements Filter GTID to Only Your Server (recommended for replication).
Updated for multi-GTID testing with dlt 1.23.0
"""

import logging
from typing import Generator, Optional, Dict, Any
from datetime import datetime

from pymysqlreplication import BinLogStreamReader
from pymysqlreplication.row_event import (
    DeleteRowsEvent,
    UpdateRowsEvent,
    WriteRowsEvent,
)

from .config import MySQLConfig
from .events import ChangeEvent, EventType, SourceInfo
from .offset_store import OffsetStore

logger = logging.getLogger(__name__)


def filter_gtid_set_to_server(gtid_set: Optional[str], server_uuid: Optional[str]) -> Optional[str]:
    """
    Filter GTID set to only include transactions from the given server (Recommended).
    GTID set format: "uuid1:1-5,uuid2:1-10" -> keep only "server_uuid:..." part.

    Args:
        gtid_set: Full GTID set from offset or MySQL (e.g. "uuid1:1-5,uuid2:1-10")
        server_uuid: This MySQL server's UUID (from @@server_uuid)

    Returns:
        Filtered GTID set string for this server only, or None/empty if none.
    """
    if not gtid_set or not server_uuid:
        return gtid_set
    gtid_set = gtid_set.strip()
    if not gtid_set:
        return None
    # Split by comma; each part is "uuid:intervals"
    parts = [p.strip() for p in gtid_set.split(',') if p.strip()]
    for part in parts:
        if ':' in part:
            uuid_part, intervals = part.split(':', 1)
            if uuid_part.strip().lower() == server_uuid.strip().lower():
                return f"{uuid_part}:{intervals}"
    return None


def get_gtid_sources_from_set(gtid_set: Optional[str]) -> Dict[str, str]:
    """
    Parse GTID set and extract all server UUIDs with their intervals.

    Args:
        gtid_set: Full GTID set (e.g. "uuid1:1-5,uuid2:1-10")

    Returns:
        Dict mapping server UUID -> intervals string
    """
    if not gtid_set:
        return {}

    sources = {}
    parts = [p.strip() for p in gtid_set.split(',') if p.strip()]
    for part in parts:
        if ':' in part:
            uuid_part, intervals = part.split(':', 1)
            sources[uuid_part.strip()] = intervals
    return sources


class BinlogStreamer:
    """
    Streams real-time changes from MySQL binlog
    Replaces Debezium's BinlogStreamingChangeEventSource

    Supports multi-GTID environment with filtering by server_uuid.
    """

    def __init__(self, mysql_config: MySQLConfig, offset_store: OffsetStore):
        """
        Initialize binlog streamer

        Args:
            mysql_config: MySQL configuration
            offset_store: Offset storage for persistence
        """
        self.mysql_config = mysql_config
        self.offset_store = offset_store
        self.stream_reader = None
        self.server_uuid = None
        self.server_id = None

    def _get_mysql_connection_settings(self) -> Dict[str, Any]:
        """Get MySQL connection settings for pymysqlreplication"""
        return {
            'host': self.mysql_config.host,
            'port': self.mysql_config.port,
            'user': self.mysql_config.user,
            'password': self.mysql_config.password,
        }

    def _get_server_uuid(self) -> Optional[str]:
        """Get MySQL server UUID"""
        try:
            import pymysql
            conn = pymysql.connect(
                host=self.mysql_config.host,
                port=self.mysql_config.port,
                user=self.mysql_config.user,
                password=self.mysql_config.password
            )
            cursor = conn.cursor()
            cursor.execute("SELECT @@server_uuid")
            result = cursor.fetchone()
            cursor.close()
            conn.close()
            return result[0] if result else None
        except Exception as e:
            logger.error(f"Failed to get server UUID: {e}")
            return None

    def _get_server_id(self) -> Optional[int]:
        """Get MySQL server_id from configuration"""
        try:
            import pymysql
            conn = pymysql.connect(
                host=self.mysql_config.host,
                port=self.mysql_config.port,
                user=self.mysql_config.user,
                password=self.mysql_config.password
            )
            cursor = conn.cursor()
            cursor.execute("SELECT @@server_id")
            result = cursor.fetchone()
            cursor.close()
            conn.close()
            return result[0] if result else None
        except Exception as e:
            logger.error(f"Failed to get server_id: {e}")
            return None

    def _get_current_gtid_set(self) -> Optional[str]:
        """Get current GTID set from MySQL (all sources)"""
        try:
            import pymysql
            conn = pymysql.connect(
                host=self.mysql_config.host,
                port=self.mysql_config.port,
                user=self.mysql_config.user,
                password=self.mysql_config.password
            )
            cursor = conn.cursor()
            cursor.execute("SHOW GLOBAL VARIABLES LIKE 'gtid_executed'")
            result = cursor.fetchone()
            cursor.close()
            conn.close()
            if result:
                gtid_value = result[1]
                logger.info(f"📍 Current GTID set (all sources): {gtid_value}")
                # Parse and show individual sources
                sources = get_gtid_sources_from_set(gtid_value)
                for uuid, intervals in sources.items():
                    logger.info(f"   - {uuid}: {intervals}")
                return gtid_value
            return None
        except Exception as e:
            logger.warning(f"Failed to get GTID set: {e}")
            return None

    def _row_to_dict(self, row, columns) -> Dict[str, Any]:
        """Convert row event to dict"""
        return {col: row[col] for col in columns if col in row}

    def start_streaming(self, table_name: Optional[str] = None,
                        gtid_set: Optional[str] = None,
                        binlog_file: Optional[str] = None,
                        binlog_pos: Optional[int] = None) -> Generator[ChangeEvent, None, None]:
        """
        Start streaming binlog events

        Args:
            table_name: Optional table filter (only stream this table)
            gtid_set: Starting GTID set (from offset) - will be filtered to this server only
            binlog_file: Starting binlog file (from offset)
            binlog_pos: Starting binlog position (from offset)

        Yields:
            ChangeEvent for each change
        """
        try:
            # Get server info for filtering
            if not self.server_uuid:
                self.server_uuid = self._get_server_uuid()
            if not self.server_id:
                self.server_id = self._get_server_id()

            logger.info(f"📡 MySQL Server Info:")
            logger.info(f"   - server_id: {self.server_id}")
            logger.info(f"   - server_uuid: {self.server_uuid}")
            logger.info(f"   - host: {self.mysql_config.host}:{self.mysql_config.port}")

            # Show current GTID state before streaming
            current_gtid = self._get_current_gtid_set()

            # Load offset if available
            partition = self.server_uuid or 'default'
            offset = self.offset_store.load_offset(partition)

            if offset:
                gtid_set = offset.get('gtid_set') or gtid_set
                binlog_file = offset.get('binlog_file') or binlog_file
                binlog_pos = offset.get('binlog_position') or binlog_pos

                logger.info(f"📥 Offset loaded for partition '{partition}':")
                logger.info(f"   - GTID: {gtid_set}")
                logger.info(f"   - Binlog: {binlog_file}:{binlog_pos}")

            # Filter GTID to only your server (recommended): only consume this server's transactions
            if gtid_set and self.server_uuid:
                filtered = filter_gtid_set_to_server(gtid_set, self.server_uuid)
                if filtered:
                    gtid_set = filtered
                    logger.info(f"🔒 GTID filtered to this server only:")
                    logger.info(f"   - {self.server_uuid}: {gtid_set.split(':')[1] if ':' in gtid_set else ''}")
                else:
                    # No transactions from this server in offset; start from current for this server
                    logger.info("🔄 No GTID for this server in offset, starting from current position")
                    gtid_set = None

            # Create binlog stream reader (connection_settings is required as first/named arg)
            # blocking=False: consume available events then exit (so pipeline can complete and save offset)
            stream_settings = {
                'connection_settings': self._get_mysql_connection_settings(),
                'server_id': self.mysql_config.server_id,
                'blocking': False,
                'only_events': self.mysql_config.only_events,
                'resume_stream': True,  # Auto-resume from last position
                'only_schemas': [self.mysql_config.database],  # Only capture our database
            }

            # Set GTID set if available (resume from last position; already filtered to this server)
            if gtid_set:
                stream_settings['auto_position'] = True
                # For pymysqlreplication, we pass the filtered GTID directly
                stream_settings['only_gtids'] = gtid_set
                logger.info(f"🔒 Auto-position enabled with GTID: {gtid_set}")

            try:
                self.stream_reader = BinLogStreamReader(**stream_settings)
            except TypeError as e:
                # Older pymysqlreplication may not support only_gtids with certain options
                logger.warning(f"Adjusting stream settings for compatibility: {e}")
                stream_settings.pop('only_gtids', None)
                self.stream_reader = BinLogStreamReader(**stream_settings)

            event_count = 0
            last_save_time = datetime.now()

            logger.info("🎯 Starting binlog event stream...")

            for binlog_event in self.stream_reader:
                event_count += 1

                # Log progress every 100 events
                if event_count % 100 == 0:
                    logger.debug(f"Processed {event_count} events...")

                # Save offset periodically (every 100 events or 10 seconds)
                current_time = datetime.now()
                if event_count % 100 == 0 or (current_time - last_save_time).total_seconds() > 10:
                    self._save_current_offset(binlog_event)
                    last_save_time = current_time

                # Process row events
                if isinstance(binlog_event, (WriteRowsEvent, UpdateRowsEvent, DeleteRowsEvent)):
                    # Filter by table if specified
                    if table_name and binlog_event.table != table_name:
                        continue

                    # Filter by schema (ensure we only capture our database)
                    if binlog_event._schema != self.mysql_config.database:
                        continue

                    # Yield change events
                    for event in self._process_row_event(binlog_event):
                        yield event

            logger.info(f"✅ Binlog streaming complete: {event_count} events processed")

        except KeyboardInterrupt:
            logger.info("Streaming stopped by user")
        except Exception as e:
            logger.error(f"Streaming error: {e}", exc_info=True)
            raise
        finally:
            if self.stream_reader:
                self.stream_reader.close()
                logger.info("Binlog stream closed")

    def _process_row_event(self, binlog_event) -> Generator[ChangeEvent, None, None]:
        """
        Process a row event and yield change events

        Args:
            binlog_event: Binlog row event

        Yields:
            ChangeEvent
        """
        try:
            # Get schema info
            schema = binlog_event._schema
            table = binlog_event.table

            # Determine event type
            if isinstance(binlog_event, WriteRowsEvent):
                event_type = EventType.CREATE
            elif isinstance(binlog_event, UpdateRowsEvent):
                event_type = EventType.UPDATE
            elif isinstance(binlog_event, DeleteRowsEvent):
                event_type = EventType.DELETE
            else:
                return

            # Get primary key (first column is usually PK)
            columns = binlog_event.columns
            pk_column = columns[0] if columns else 'id'

            # Process each row in the event
            for row in binlog_event.rows:
                before = {}
                after = {}

                if isinstance(binlog_event, DeleteRowsEvent):
                    # Delete event has 'values' (row being deleted)
                    before = self._row_to_dict(row["values"], columns)
                    primary_key = {pk_column: before.get(pk_column)}
                elif isinstance(binlog_event, UpdateRowsEvent):
                    # Update event has 'before_values' and 'after_values'
                    before = self._row_to_dict(row["before_values"], columns)
                    after = self._row_to_dict(row["after_values"], columns)
                    primary_key = {pk_column: after.get(pk_column)}
                else:  # WriteRowsEvent
                    # Insert event has 'values'
                    after = self._row_to_dict(row["values"], columns)
                    primary_key = {pk_column: after.get(pk_column)}

                # Get binlog position info
                source_info = SourceInfo(
                    connector='mysql',
                    name=self.mysql_config.database,
                    server_id=self.mysql_config.server_id,
                    ts_sec=int(datetime.now().timestamp()),
                    gtids=getattr(binlog_event, 'gtid', None),
                    binlog_file=getattr(binlog_event, 'logfile', None),
                    binlog_pos=getattr(binlog_event, 'log_pos', 0),
                    server_uuid=self.server_uuid,
                    table=table
                )

                yield ChangeEvent(
                    event_type=event_type,
                    timestamp=datetime.now(),
                    database=self.mysql_config.database,
                    table=table,
                    primary_key=primary_key,
                    before=before,
                    after=after,
                    source=source_info
                )

        except Exception as e:
            logger.error(f"Error processing row event: {e}", exc_info=True)

    def _save_current_offset(self, binlog_event):
        """Save current binlog position as offset"""
        try:
            if not self.server_uuid:
                self.server_uuid = self._get_server_uuid()

            # Get the GTID for this event
            event_gtid = getattr(binlog_event, 'gtid', None)

            # Filter to only this server's GTID
            if event_gtid and self.server_uuid:
                filtered_gtid = filter_gtid_set_to_server(event_gtid, self.server_uuid)
                if filtered_gtid:
                    event_gtid = filtered_gtid

            offset = {
                'gtid_set': event_gtid or '',
                'binlog_file': getattr(binlog_event, 'logfile', ''),
                'binlog_position': getattr(binlog_event, 'log_pos', 0),
                'server_id': self.mysql_config.server_id,
                'server_uuid': self.server_uuid,
                'snapshot_completed': False
            }

            self.offset_store.save_offset(self.server_uuid or 'default', offset)
            logger.debug(f"💾 Offset saved: GTID={event_gtid}")

        except Exception as e:
            logger.error(f"Failed to save offset: {e}")

    def close(self):
        """Close the binlog streamer"""
        if self.stream_reader:
            self.stream_reader.close()
            logger.info("Binlog stream closed")
