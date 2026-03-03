"""
Debezium-style CDC Connector for DLT
Real-time Change Data Capture from MySQL with Iceberg checkpointing
"""

from .config import DebeziumConfig, MySQLConfig, IcebergConfig
from .binlog_streamer import BinlogStreamer
from .snapshot import SnapshotManager
from .offset_store import OffsetStore
from .schema_history import SchemaHistory
from .connector import DebeziumDLTConnector
from .events import ChangeEvent, EventType
from .iceberg_writer import IcebergWriter, IcebergConfig as IcebergWriterConfig, DuckDBIcebergVerifier
from .nessie_register import NessieTableRegister, NessieRegisterConfig, register_dlt_iceberg_tables_with_nessie

__all__ = [
    'DebeziumConfig',
    'MySQLConfig',
    'IcebergConfig',
    'IcebergWriter',
    'IcebergWriterConfig',
    'DuckDBIcebergVerifier',
    'BinlogStreamer',
    'SnapshotManager',
    'OffsetStore',
    'SchemaHistory',
    'DebeziumDLTConnector',
    'ChangeEvent',
    'EventType',
    'NessieTableRegister',
    'NessieRegisterConfig',
    'register_dlt_iceberg_tables_with_nessie'
]

__version__ = '1.0.1'
