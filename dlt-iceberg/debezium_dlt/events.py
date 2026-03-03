"""
Change Events for Debezium-style CDC
Represents database change events
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Dict, Optional
from datetime import datetime


class EventType(Enum):
    """Types of change events"""
    CREATE = 'c'  # Insert
    READ = 'r'    # Snapshot read
    UPDATE = 'u'  # Update
    DELETE = 'd'  # Delete
    TRUNCATE = 't'
    BEGIN = 'b'   # Transaction begin
    COMMIT = 'c'  # Transaction commit


@dataclass
class SourceInfo:
    """Source metadata for change event"""
    connector: str = 'mysql'
    name: str = 'appdb'
    server_id: int = 0
    ts_sec: int = 0
    gtids: Optional[str] = None
    binlog_file: Optional[str] = None
    binlog_pos: int = 0
    binlog_row: int = 0
    server_uuid: Optional[str] = None
    thread: Optional[int] = None
    table: Optional[str] = None
    query: Optional[str] = None


@dataclass
class ChangeEvent:
    """
    Represents a database change event (Debezium-style)
    """
    # Event metadata
    event_type: EventType
    timestamp: datetime

    # Table information
    database: str
    table: str
    primary_key: Dict[str, Any]

    # Data
    before: Dict[str, Any] = field(default_factory=dict)  # State before change
    after: Dict[str, Any] = field(default_factory=dict)   # State after change

    # Transaction info
    transaction_id: Optional[str] = None
    sequence: Optional[int] = None

    # Source metadata
    source: SourceInfo = field(default_factory=SourceInfo)

    # Schema information
    schema_version: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for DLT"""
        result = {
            '_op': self.event_type.value,
            '_ts': self.timestamp.isoformat(),
            '_db': self.database,
            '_table': self.table,
        }

        # Add source metadata with _cdc prefix
        if self.source:
            result['_cdc_server_id'] = self.source.server_uuid or ''
            result['_cdc_gtid'] = self.source.gtids or ''
            result['_cdc_binlog_file'] = self.source.binlog_file or ''
            result['_cdc_binlog_pos'] = self.source.binlog_pos
            result['_cdc_binlog_row'] = self.source.binlog_row

        # Add transaction info
        if self.transaction_id:
            result['_tx_id'] = self.transaction_id
        if self.sequence is not None:
            result['_seq'] = self.sequence

        # Add before/after data
        if self.event_type == EventType.DELETE:
            result.update(self.before)
        elif self.event_type in (EventType.CREATE, EventType.READ, EventType.UPDATE):
            result.update(self.after)

        return result

    @classmethod
    def from_snapshot_row(cls, row: Dict[str, Any], database: str, table: str,
                          primary_key: Dict[str, Any], gtid_info: Optional[str] = None):
        """Create change event from snapshot row"""
        return cls(
            event_type=EventType.READ,
            timestamp=datetime.now(),
            database=database,
            table=table,
            primary_key=primary_key,
            after=row.copy(),
            source=SourceInfo(
                connector='mysql',
                name=database,
                gtids=gtid_info
            )
        )
