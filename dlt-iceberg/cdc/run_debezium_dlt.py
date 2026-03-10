#!/usr/bin/env python3
"""
Debezium-style DLT CDC Connector - Main Entry Point
Real-time CDC from MySQL to MinIO with Iceberg checkpointing
Updated for dlt 1.23.0 with multi-GTID support
"""

import sys
import logging
import os
from datetime import datetime

# Setup logging (pipeline.log for Streamlit UI; debezium_dlt.log for debugging)
_log_dir = '/logs'
if os.path.exists(_log_dir):
    _handlers = [
        logging.FileHandler(os.path.join(_log_dir, 'debezium_dlt.log')),
        logging.FileHandler(os.path.join(_log_dir, 'pipeline.log')),
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


def main():
    """Main entry point for Debezium DLT connector"""
    try:
        from debezium_dlt import DebeziumConfig, DebeziumDLTConnector

        # Load from environment (includes NESSIE_URI, NESSIE_REF, MySQL, S3, etc.)
        config = DebeziumConfig.from_env()

        # Override with defaults for this pipeline
        config.mysql.snapshot_mode = os.getenv('SNAPSHOT_MODE', 'initial')
        config.mysql.host = os.getenv('MYSQL_HOST', 'mysql')
        config.mysql.port = int(os.getenv('MYSQL_PORT', '3306'))
        config.mysql.user = os.getenv('MYSQL_USER', 'root')
        config.mysql.password = os.getenv('MYSQL_PASSWORD', 'rootpw')
        config.mysql.database = os.getenv('MYSQL_DATABASE', 'appdb')

        config.dlt.destination_bucket = os.getenv('DEST_BUCKET', 'dlt-warehouse')
        config.dlt.dataset_name = os.getenv('DATASET_NAME', 'debezium_cdc')
        config.dlt.write_disposition = 'append'  # Use append instead of merge for CDC events

        # Tables to capture - can be overridden via TABLE_INCLUDE_LIST env var
        table_list = os.getenv('TABLE_INCLUDE_LIST', 'appdb.products,appdb.sales')
        config.table_include_list = table_list.split(',')

        config.snapshot_fetch_size = int(os.getenv('SNAPSHOT_FETCH_SIZE', '1000'))
        config.streaming_batch_size = int(os.getenv('STREAMING_BATCH_SIZE', '100'))

        # GTID filtering - configure from environment
        # GTID_SOURCE_INCLUDE: comma-separated list of server UUIDs to include
        # If not set, will auto-filter to only the connected server's GTIDs (recommended)
        gtid_include = os.getenv('GTID_SOURCE_INCLUDE')
        if gtid_include:
            config.gtid_source_include = gtid_include
            logger.info(f"🔒 GTID filtering enabled for sources: {gtid_include}")
        else:
            logger.info("🔒 GTID filtering: auto (only this server's GTIDs, recommended)")

        logger.info("🎯 Debezium DLT Connector Configuration:")
        logger.info(f"   MySQL: {config.mysql.host}:{config.mysql.port}/{config.mysql.database}")
        logger.info(f"   Tables: {config.table_include_list}")
        logger.info(f"   Snapshot mode: {config.mysql.snapshot_mode}")
        logger.info(f"   Destination: s3://{config.dlt.destination_bucket}/{config.dlt.dataset_name}")
        logger.info(f"   Checkpoints: s3://{config.iceberg.checkpoint_bucket}/")
        if config.iceberg.nessie_uri:
            logger.info(f"   Nessie catalog: {config.iceberg.nessie_uri} (ref={config.iceberg.nessie_ref})")
        logger.info("   GTID: filtered to this server only (recommended)")

        # Create and run connector
        connector = DebeziumDLTConnector(config)

        try:
            # Log server info for debugging GTID filtering
            logger.info("=" * 80)
            logger.info("MySQL Server Information:")
            logger.info("=" * 80)

            import pymysql
            conn = pymysql.connect(
                host=config.mysql.host,
                port=config.mysql.port,
                user=config.mysql.user,
                password=config.mysql.password
            )
            cursor = conn.cursor()

            # Get server_id and server_uuid
            cursor.execute("SELECT @@server_id, @@server_uuid")
            server_id, server_uuid = cursor.fetchone()
            logger.info(f"  server_id: {server_id}")
            logger.info(f"  server_uuid: {server_uuid}")

            # Get GTID status
            cursor.execute("SHOW GLOBAL VARIABLES LIKE 'gtid_executed'")
            gtid_result = cursor.fetchone()
            if gtid_result:
                logger.info(f"  gtid_executed: {gtid_result[1]}")

            cursor.execute("SHOW GLOBAL VARIABLES LIKE 'gtid_mode'")
            gtid_mode = cursor.fetchone()
            if gtid_mode:
                logger.info(f"  gtid_mode: {gtid_mode[1]}")

            cursor.close()
            conn.close()

            logger.info("=" * 80)
            logger.info("")

            load_info = connector.run_cdc()

            if load_info:
                logger.info("✅ CDC pipeline completed successfully")
                return 0
            else:
                logger.error("❌ CDC pipeline failed")
                return 1

        finally:
            connector.close()

    except ImportError as e:
        logger.error(f"❌ Missing dependencies: {e}")
        logger.error("Please install pymysql-replication:")
        logger.error("   pip install pymysql-replication")
        return 1

    except Exception as e:
        logger.error(f"❌ Fatal error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
