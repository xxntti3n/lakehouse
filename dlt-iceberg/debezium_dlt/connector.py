"""
Debezium DLT Connector - Main orchestrator
Combines snapshot and streaming for complete CDC
"""

import logging
import os
import json
import glob
import dlt
from typing import Generator, Optional, List, Any, Dict
from datetime import datetime
from enum import Enum

from .config import DebeziumConfig
from .snapshot import SnapshotManager
from .binlog_streamer import BinlogStreamer
from .offset_store import OffsetStore
from .schema_history import SchemaHistory
from .events import ChangeEvent
from .iceberg_writer import IcebergWriter, IcebergConfig, DuckDBIcebergVerifier
from .nessie_register import NessieTableRegister, NessieRegisterConfig

logger = logging.getLogger(__name__)


class SnapshotMode(Enum):
    """Snapshot modes"""
    INITIAL = 'initial'  # Full blocking snapshot
    INCREMENTAL = 'incremental'  # Non-blocking incremental snapshot
    SCHEMA_ONLY = 'schema_only'  # Only capture schema
    NEVER = 'never'  # Don't snapshot, start streaming from offset


class DebeziumDLTConnector:
    """
    Main CDC connector that combines snapshot and streaming
    Debezium-style architecture adapted for DLT
    """

    def __init__(self, config: DebeziumConfig):
        """
        Initialize Debezium DLT connector

        Args:
            config: Connector configuration
        """
        self.config = config

        # Initialize components
        self.offset_store = OffsetStore(config.iceberg)
        self.schema_history = SchemaHistory(config.iceberg)
        self.snapshot_manager = SnapshotManager(config.mysql, self.schema_history)
        self.binlog_streamer = BinlogStreamer(config.mysql, self.offset_store)

        # Setup DLT environment
        self._setup_dlt_env()

        # Initialize Iceberg writer (for Iceberg format storage; optional Nessie catalog)
        try:
            iceberg_config = IcebergConfig(
                warehouse_path=f"s3://{config.dlt.destination_bucket}/iceberg",
                access_key=config.iceberg.access_key,
                secret_key=config.iceberg.secret_key,
                endpoint_url=config.iceberg.endpoint_url,
                nessie_uri=config.iceberg.nessie_uri,
                nessie_ref=config.iceberg.nessie_ref
            )
            self.iceberg_writer = IcebergWriter(iceberg_config)
            self.iceberg_writer.create_checkpoint_tables()
            self.use_iceberg = True
            logger.info("✅ Iceberg writer initialized")
        except Exception as e:
            logger.warning(f"⚠️  Iceberg writer not available: {e}")
            logger.info("   Falling back to filesystem destination")
            self.iceberg_writer = None
            self.use_iceberg = False

        # Use dlt native Iceberg when Iceberg REST catalog is configured (no custom writer for CDC table)
        self.use_dlt_iceberg = bool(
            getattr(self.config.iceberg, 'iceberg_rest_uri', None) or os.environ.get('ICEBERG_REST_URI')
        )
        if self.use_dlt_iceberg:
            logger.info("📦 Using dlt native Iceberg destination (table_format='iceberg')")

        # State
        self.snapshot_completed = False

    def _setup_dlt_env(self):
        """Setup DLT environment variables (filesystem + optional Iceberg catalog for dlt native Iceberg)."""
        import os
        os.environ['DESTINATION__FILESYSTEM__BUCKET_URL'] = f"s3://{self.config.dlt.destination_bucket}"
        os.environ['DESTINATION__FILESYSTEM__CREDENTIALS__AWS_ACCESS_KEY_ID'] = self.config.iceberg.access_key
        os.environ['DESTINATION__FILESYSTEM__CREDENTIALS__AWS_SECRET_ACCESS_KEY'] = self.config.iceberg.secret_key
        os.environ['DESTINATION__FILESYSTEM__CREDENTIALS__ENDPOINT_URL'] = self.config.iceberg.endpoint_url

        # dlt native Iceberg destination (see https://dlthub.com/docs/dlt-ecosystem/destinations/iceberg)
        rest_uri = getattr(self.config.iceberg, 'iceberg_rest_uri', None) or os.environ.get('ICEBERG_REST_URI')
        if rest_uri:
            warehouse = f"s3://{self.config.dlt.destination_bucket}/iceberg"
            os.environ['ICEBERG_CATALOG__ICEBERG_CATALOG_NAME'] = 'default'
            os.environ['ICEBERG_CATALOG__ICEBERG_CATALOG_TYPE'] = 'rest'
            os.environ['ICEBERG_CATALOG__ICEBERG_CATALOG_CONFIG__URI'] = rest_uri
            os.environ['ICEBERG_CATALOG__ICEBERG_CATALOG_CONFIG__TYPE'] = 'rest'
            os.environ['ICEBERG_CATALOG__ICEBERG_CATALOG_CONFIG__WAREHOUSE'] = warehouse
            os.environ['ICEBERG_CATALOG__ICEBERG_CATALOG_CONFIG__PY_IO_IMPL'] = 'pyiceberg.io.fsspec.FsspecFileIO'
            os.environ['ICEBERG_CATALOG__ICEBERG_CATALOG_CONFIG__S3_ENDPOINT'] = self.config.iceberg.endpoint_url
            os.environ['ICEBERG_CATALOG__ICEBERG_CATALOG_CONFIG__S3_ACCESS_KEY_ID'] = self.config.iceberg.access_key
            os.environ['ICEBERG_CATALOG__ICEBERG_CATALOG_CONFIG__S3_SECRET_ACCESS_KEY'] = self.config.iceberg.secret_key
            os.environ['ICEBERG_CATALOG__ICEBERG_CATALOG_CONFIG__S3_REGION'] = getattr(
                self.config.iceberg, 'region', 'us-east-1'
            )
            logger.info(f"✅ dlt Iceberg catalog configured: uri={rest_uri}, warehouse={warehouse}")

    def _parse_table_include(self) -> List[tuple]:
        """
        Parse table include list

        Returns:
            List of (database, table) tuples
        """
        tables = []
        for table_spec in self.config.table_include_list:
            parts = table_spec.split('.')
            if len(parts) == 2:
                tables.append((parts[0], parts[1]))
            else:
                logger.warning(f"Invalid table specification: {table_spec}")
        return tables

    def _get_snapshot_mode(self) -> SnapshotMode:
        """Get snapshot mode from config"""
        mode_str = self.config.mysql.snapshot_mode.lower()
        try:
            return SnapshotMode(mode_str)
        except ValueError:
            logger.warning(f"Invalid snapshot mode: {mode_str}, using 'initial'")
            return SnapshotMode.INITIAL

    def run_snapshot(self, tables: List[tuple]) -> Generator[ChangeEvent, None, None]:
        """
        Run snapshot phase

        Args:
            tables: List of (database, table) tuples

        Yields:
            ChangeEvent from snapshot
        """
        snapshot_mode = self._get_snapshot_mode()

        if snapshot_mode == SnapshotMode.NEVER:
            logger.info("⏭️  Snapshot mode: NEVER - skipping snapshot")
            return

        if snapshot_mode == SnapshotMode.SCHEMA_ONLY:
            logger.info("📝 Snapshot mode: SCHEMA_ONLY - capturing schema only")
            for database, table in tables:
                self.snapshot_manager.record_table_schema(table)
            return

        if snapshot_mode == SnapshotMode.INITIAL:
            logger.info("📸 Snapshot mode: INITIAL - full blocking snapshot")

            for database, table in tables:
                logger.info(f"  Snapshotting {database}.{table}...")
                for event in self.snapshot_manager.initial_snapshot(table):
                    yield event

        elif snapshot_mode == SnapshotMode.INCREMENTAL:
            logger.info("📸 Snapshot mode: INCREMENTAL - non-blocking snapshot")

            for database, table in tables:
                logger.info(f"  Incrementally snapshotting {database}.{table}...")
                for event in self.snapshot_manager.incremental_snapshot(table):
                    yield event

        # Mark snapshot as completed
        self.snapshot_completed = True

        gtid_set = self.snapshot_manager.get_gtid_set()
        if self.binlog_streamer.server_uuid:
            self.offset_store.save_offset(
                self.binlog_streamer.server_uuid,
                {
                    'gtid_set': gtid_set,
                    'snapshot_completed': True
                }
            )
        self._append_gtid_log(phase='snapshot', gtid_set=gtid_set)

        logger.info(f"✅ Snapshot complete")

    def run_streaming(self, tables: List[tuple]) -> Generator[ChangeEvent, None, None]:
        """
        Run streaming phase

        Args:
            tables: List of (database, table) tuples

        Yields:
            ChangeEvent from binlog
        """
        logger.info("📡 Starting binlog streaming phase...")

        # Get offset info
        partition = self.binlog_streamer.server_uuid or 'default'
        offset = self.offset_store.load_offset(partition)

        gtid_set = None
        if offset:
            gtid_set = offset.get('gtid_set')

        # Stream from all tables
        for database, table in tables:
            logger.info(f"  Streaming {database}.{table}...")

            try:
                for event in self.binlog_streamer.start_streaming(
                    table_name=table,
                    gtid_set=gtid_set
                ):
                    yield event

            except Exception as e:
                logger.error(f"Error streaming {table}: {e}")
                continue

    def run_cdc(self) -> Any:
        """
        Run complete CDC pipeline: snapshot + streaming

        Returns:
            Pipeline trace info
        """
        logger.info("=" * 80)
        logger.info(f"🚀 Starting Debezium DLT Connector at {datetime.now().isoformat()}")
        logger.info("=" * 80)

        # Parse tables
        tables = self._parse_table_include()

        if not tables:
            logger.error("❌ No tables to capture!")
            return None

        logger.info(f"📋 Tables to capture: {[f'{db}.{tbl}' for db, tbl in tables]}")

        # Create DLT pipeline
        pipeline = dlt.pipeline(
            pipeline_name=self.config.dlt.pipeline_name,
            destination='filesystem',
            dataset_name=self.config.dlt.dataset_name
        )

        # Phase 1: Snapshot
        logger.info("\n" + "=" * 80)
        logger.info("PHASE 1: SNAPSHOT")
        logger.info("=" * 80)

        snapshot_events = []

        for event in self.run_snapshot(tables):
            snapshot_events.append(event.to_dict())

            # Write in batches
            if len(snapshot_events) >= self.config.snapshot_fetch_size:
                logger.info(f"  Writing {len(snapshot_events)} snapshot events...")
                self._write_batch(pipeline, snapshot_events, tables)
                snapshot_events = []

        # Write remaining snapshot events
        if snapshot_events:
            logger.info(f"  Writing {len(snapshot_events)} final snapshot events...")
            self._write_batch(pipeline, snapshot_events, tables)

        # Phase 2: Streaming (for demo, run once and stop)
        logger.info("\n" + "=" * 80)
        logger.info("PHASE 2: STREAMING")
        logger.info("=" * 80)

        # For this demo, we'll stream for a limited time or events
        # In production, this would run continuously
        streaming_events = []
        max_streaming_events = 100  # Limit for demo

        streaming_event_count = 0
        for event in self.run_streaming(tables):
            streaming_events.append(event.to_dict())
            streaming_event_count += 1

            if len(streaming_events) >= self.config.streaming_batch_size:
                logger.info(f"  Writing {len(streaming_events)} streaming events...")
                self._write_batch(pipeline, streaming_events, tables)
                streaming_events = []

            if streaming_event_count >= max_streaming_events:
                logger.info(f"  Reached demo limit of {max_streaming_events} streaming events")
                break

        # Write remaining streaming events
        if streaming_events:
            logger.info(f"  Writing {len(streaming_events)} streaming events...")
            self._write_batch(pipeline, streaming_events, tables)

        logger.info(f"  📡 Streaming phase complete: {streaming_event_count} events processed")

        # Save offset after streaming so next run resumes from here (GTID from MySQL)
        try:
            final_gtid = self.snapshot_manager.get_gtid_set()
            self._append_gtid_log(phase='streaming_end', gtid_set=final_gtid)
            if self.binlog_streamer.server_uuid:
                self.offset_store.save_offset(
                    self.binlog_streamer.server_uuid,
                    {
                        'gtid_set': final_gtid,
                        'snapshot_completed': True,
                    }
                )
        except Exception as e:
            logger.warning(f"Could not save offset after streaming: {e}")

        logger.info("\n" + "=" * 80)
        logger.info("✅ CDC Pipeline Complete!")
        logger.info("=" * 80)
        logger.info(f"📦 Data stored in: s3://{self.config.dlt.destination_bucket}/{self.config.dlt.dataset_name}/")
        logger.info(f"📍 Checkpoints stored in: s3://{self.config.iceberg.checkpoint_bucket}/")

        # Verify data with DuckDB
        self._verify_data()

        # Register tables with Nessie catalog
        self._register_with_nessie()

        return pipeline.last_trace if hasattr(pipeline, 'last_trace') else None

    def _write_batch(self, pipeline, events: List[Dict], tables: List[tuple]):
        """
        Write batch of events via DLT. Uses dlt native Iceberg when catalog is configured,
        otherwise filesystem (JSONL) and optionally legacy custom Iceberg writer.
        """
        run_kw = {
            "table_name": "cdc_events",
            "write_disposition": self.config.dlt.write_disposition,
        }
        if self.use_dlt_iceberg:
            run_kw["table_format"] = "iceberg"
        pipeline.run(events, **run_kw)

        # Legacy path: also write via custom Iceberg writer only when not using dlt Iceberg
        if not self.use_dlt_iceberg and self.use_iceberg and self.iceberg_writer:
            try:
                for database, table in tables:
                    table_events = [e for e in events if e.get('_db') == database and e.get('_table') == table]
                    if table_events:
                        table_identifier = self.iceberg_writer.ensure_table(database, table)
                        self.iceberg_writer.write_events(table_identifier, table_events)
                        logger.info(f"  ✅ Also wrote {len(table_events)} events to Iceberg format")
            except Exception as e:
                logger.warning(f"  ⚠️  Iceberg write failed: {e}")

    def _verify_data(self):
        """Verify data using DuckDB"""
        if not self.use_iceberg:
            return

        try:
            logger.info("\n" + "=" * 80)
            logger.info("VERIFYING DATA WITH DUCKDB")
            logger.info("=" * 80)

            iceberg_config = IcebergConfig(
                warehouse_path=f"s3://{self.config.dlt.destination_bucket}/iceberg",
                access_key=self.config.iceberg.access_key,
                secret_key=self.config.iceberg.secret_key,
                endpoint_url=self.config.iceberg.endpoint_url
            )

            verifier = DuckDBIcebergVerifier(iceberg_config)

            # Get statistics
            stats = verifier.get_statistics()

            if stats:
                logger.info("\n📊 CDC Event Statistics:")
                if 'by_operation' in stats:
                    logger.info("  By Operation:")
                    for op, count in stats['by_operation'].items():
                        logger.info(f"    {op}: {count} events")

                if 'by_table' in stats:
                    logger.info("  By Table:")
                    for table, count in stats['by_table'].items():
                        logger.info(f"    {table}: {count} events")

                # Query GTIDs
                for database, table in self._parse_table_include():
                    gtids = verifier.query_gtids(database, table)
                    if gtids:
                        logger.info(f"\n📍 GTIDs for {database}.{table}:")
                        for gtid in gtids[:5]:  # Show first 5
                            logger.info(f"    {gtid}")
                        if len(gtids) > 5:
                            logger.info(f"    ... and {len(gtids) - 5} more")

        except Exception as e:
            logger.warning(f"⚠️  Data verification failed: {e}")

    def _append_gtid_log(self, phase: str, gtid_set: str):
        """Append GTID position to shared log for Streamlit UI"""
        try:
            import json
            log_path = '/logs/dlt_gtid.log'
            if os.path.exists(os.path.dirname(log_path)):
                with open(log_path, 'a') as f:
                    f.write(json.dumps({
                        'ts': datetime.now().isoformat(),
                        'phase': phase,
                        'gtid_set': gtid_set or '',
                        'server_uuid': self.binlog_streamer.server_uuid or ''
                    }) + '\n')
        except Exception as e:
            logger.debug(f"Could not write GTID log: {e}")

    def _register_with_nessie(self):
        """Register Iceberg tables with Nessie catalog"""
        # Only register if using dlt Iceberg format and Nessie is configured
        if not self.use_dlt_iceberg:
            logger.debug("Skipping Nessie registration (not using dlt Iceberg format)")
            return

        nessie_uri = getattr(self.config.iceberg, 'iceberg_rest_uri', None) or os.environ.get('ICEBERG_REST_URI')
        if not nessie_uri:
            logger.debug("Skipping Nessie registration (no ICEBERG_REST_URI configured)")
            return

        try:
            logger.info("\n" + "=" * 80)
            logger.info("REGISTERING TABLES WITH NESSIE CATALOG")
            logger.info("=" * 80)

            config = NessieRegisterConfig(
                nessie_uri=nessie_uri,
                warehouse_path=f"s3://{self.config.dlt.destination_bucket}",
                access_key=self.config.iceberg.access_key,
                secret_key=self.config.iceberg.secret_key,
                endpoint_url=self.config.iceberg.endpoint_url,
                namespace=self.config.dlt.dataset_name,
                ref=getattr(self.config.iceberg, 'nessie_ref', 'main')
            )

            registrar = NessieTableRegister(config)

            # Create namespace
            registrar.create_namespace()

            # Find and register the cdc_events table
            # First, find the latest metadata file from DLT's output
            dataset_name = self.config.dlt.dataset_name
            table_name = "cdc_events"

            # Get the latest metadata version from DLT state
            metadata_location = self._find_dlt_metadata_location(dataset_name, table_name)

            if metadata_location:
                success = registrar.register_table_from_metadata(
                    table_name=table_name,
                    metadata_location=metadata_location,
                    namespace=dataset_name
                )

                if success:
                    logger.info(f"✅ Registered table: {dataset_name}.{table_name}")
                    logger.info(f"   Metadata: {metadata_location}")
                else:
                    logger.warning(f"⚠️  Failed to register table: {dataset_name}.{table_name}")
            else:
                logger.warning(f"⚠️  Could not find metadata for {dataset_name}.{table_name}")

            # List registered tables
            tables = registrar.list_registered_tables(dataset_name)
            if tables:
                logger.info(f"\n📋 Registered tables in {dataset_name}:")
                for t in tables:
                    logger.info(f"  - {t}")

        except Exception as e:
            logger.warning(f"⚠️  Nessie registration failed: {e}")
            logger.info("   Tables are still available in Iceberg format at:")
            logger.info(f"   s3://{self.config.dlt.destination_bucket}/{self.config.dlt.dataset_name}/")

    def _find_dlt_metadata_location(self, dataset_name: str, table_name: str) -> Optional[str]:
        """Find the latest DLT metadata.json location for a table"""
        try:
            import glob

            # Check local filesystem first (in-container)
            metadata_base = f"/data/{dataset_name}/{table_name}/metadata"

            if os.path.exists(metadata_base):
                # Find all v*.metadata.json files
                meta_files = glob.glob(os.path.join(metadata_base, "v*.metadata.json"))

                if meta_files:
                    # Extract version numbers and find the highest
                    versions = []
                    for f in meta_files:
                        try:
                            basename = os.path.basename(f)
                            v_str = basename.replace('v', '').replace('.metadata.json', '')
                            # Handle both simple numbers and UUID-based versions
                            if '-' in v_str:
                                # UUID-based version, use timestamp
                                v = os.path.getmtime(f)
                            else:
                                v = int(v_str)
                            versions.append((v, f))
                        except (ValueError, OSError):
                            pass

                    if versions:
                        latest = max(versions, key=lambda x: x[0])
                        # Convert local path to S3 path
                        relative_path = latest[1].replace('/data/', '')
                        s3_path = f"s3://{relative_path}"
                        return s3_path

            # Fallback: check S3 directly using the DLT pipeline state
            # DLT stores state in .dlt/pipeline_state
            state_file = f".dlt/pipeline_state/{self.config.dlt.pipeline_name}/state.json"
            if os.path.exists(state_file):
                try:
                    with open(state_file, 'r') as f:
                        state = json.load(f)
                        # Try to extract latest metadata location
                        if 'pipeline_state' in state:
                            # DLT state structure - look for completed loads
                            pass
                except Exception:
                    pass

            # Final fallback - return the expected path for v1
            return f"s3://{self.config.dlt.destination_bucket}/{dataset_name}/{table_name}/metadata/v1.metadata.json"

        except Exception as e:
            logger.warning(f"Error finding metadata location: {e}")
            return f"s3://{self.config.dlt.destination_bucket}/{dataset_name}/{table_name}/metadata/v1.metadata.json"

    def close(self):
        """Close connector and cleanup"""
        logger.info("🔒 Closing Debezium DLT Connector...")
        if self.binlog_streamer:
            self.binlog_streamer.close()
