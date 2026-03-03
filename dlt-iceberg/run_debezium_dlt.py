#!/usr/bin/env python3
"""
Debezium-style DLT CDC Connector - Main Entry Point
Real-time CDC from MySQL to MinIO with Iceberg checkpointing
"""

import sys
import logging
from datetime import datetime

# Setup logging (pipeline.log for Streamlit UI; debezium_dlt.log for debugging)
import os
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
        config.dlt.destination_bucket = os.getenv('DEST_BUCKET', 'dlt-warehouse')
        config.dlt.dataset_name = os.getenv('DATASET_NAME', 'debezium_cdc')
        config.dlt.write_disposition = 'append'  # Use append instead of merge for CDC events
        config.table_include_list = ['appdb.products', 'appdb.sales']
        config.snapshot_fetch_size = 1000
        config.streaming_batch_size = 100
        # Filter GTID to only your server is applied in binlog_streamer (recommended)

        logger.info("🎯 Debezium DLT Connector Configuration:")
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
