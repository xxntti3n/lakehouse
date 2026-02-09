#!/usr/bin/env python3
"""
MySQL to MinIO Pipeline using DLT with GTID Tracking
Logs GTID information for CDC monitoring
"""

import dlt
import os
import pymysql
import json
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/tmp/pipeline.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configure S3 filesystem destination
os.environ['DESTINATION__FILESYSTEM__BUCKET_URL'] = 's3://dlt-warehouse'
os.environ['DESTINATION__FILESYSTEM__CREDENTIALS__AWS_ACCESS_KEY_ID'] = 'minio'
os.environ['DESTINATION__FILESYSTEM__CREDENTIALS__AWS_SECRET_ACCESS_KEY'] = 'minio123'
os.environ['DESTINATION__FILESYSTEM__CREDENTIALS__ENDPOINT_URL'] = 'http://minio:9000'
os.environ['DESTINATION__FILESYSTEM__CREDENTIALS__REGION_NAME'] = 'us-east-1'

# Log file for GTID tracking
GTID_LOG_FILE = '/logs/dlt_gtid.log'


def get_mysql_gtid_info():
    """Get GTID information from MySQL"""
    try:
        conn = pymysql.connect(
            host='mysql-source',
            user='root',
            password='rootpw',
            database='appdb'
        )
        cursor = conn.cursor()

        # Get GTID status
        gtid_info = {}

        # Check if GTID is enabled
        cursor.execute("SHOW VARIABLES LIKE 'gtid_mode'")
        result = cursor.fetchone()
        gtid_info['gtid_mode'] = result[1] if result else 'UNKNOWN'

        if gtid_info['gtid_mode'] == 'ON':
            # Get executed GTIDs
            cursor.execute("SHOW VARIABLES LIKE 'gtid_executed'")
            result = cursor.fetchone()
            gtid_info['gtid_executed'] = result[1] if result else ''

            # Get GTID owned
            cursor.execute("SHOW VARIABLES LIKE 'gtid_owned'")
            result = cursor.fetchone()
            gtid_info['gtid_owned'] = result[1] if result else ''

            # Get GTID purged
            cursor.execute("SHOW VARIABLES LIKE 'gtid_purged'")
            result = cursor.fetchone()
            gtid_info['gtid_purged'] = result[1] if result else ''

        # Get binary log position
        cursor.execute("SHOW MASTER STATUS")
        result = cursor.fetchone()
        if result:
            gtid_info['binlog_file'] = result[0]
            gtid_info['binlog_position'] = result[1]

        # Get server UUID
        cursor.execute("SELECT @@server_uuid")
        result = cursor.fetchone()
        gtid_info['server_uuid'] = result[0] if result else ''

        cursor.close()
        conn.close()

        return gtid_info
    except Exception as e:
        logger.error(f"Error getting GTID info: {e}")
        return {}


def log_gtid_info(run_info):
    """Log GTID information to file"""
    try:
        timestamp = datetime.now().isoformat()

        # Get GTID information
        gtid_info = get_mysql_gtid_info()

        log_entry = {
            'timestamp': timestamp,
            'gtid_info': gtid_info,
            'pipeline_info': run_info
        }

        # Append to log file
        with open(GTID_LOG_FILE, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')

        # Also log to stdout
        logger.info(f"📍 GTID Mode: {gtid_info.get('gtid_mode', 'UNKNOWN')}")
        if gtid_info.get('gtid_mode') == 'ON':
            logger.info(f"📍 GTID Executed: {gtid_info.get('gtid_executed', 'N/A')}")
            logger.info(f"📍 Server UUID: {gtid_info.get('server_uuid', 'N/A')}")
        if gtid_info.get('binlog_file'):
            logger.info(f"📍 Binlog: {gtid_info.get('binlog_file')} @ {gtid_info.get('binlog_position')}")

        return gtid_info
    except Exception as e:
        logger.error(f"Error logging GTID info: {e}")
        return {}


@dlt.source(
    name="mysql_source",
    max_table_nesting=0
)
def mysql_source():
    @dlt.resource(
        name="products",
        write_disposition="replace",
        primary_key="id"
    )
    def products_resource():
        conn = pymysql.connect(
            host='mysql-source',
            user='root',
            password='rootpw',
            database='appdb'
        )
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        cursor.execute("SELECT * FROM products")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        yield rows

    @dlt.resource(
        name="sales",
        write_disposition="replace",
        primary_key="id"
    )
    def sales_resource():
        conn = pymysql.connect(
            host='mysql-source',
            user='root',
            password='rootpw',
            database='appdb'
        )
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        cursor.execute("SELECT * FROM sales")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        yield rows

    return products_resource, sales_resource


def main():
    """Main pipeline with GTID logging"""
    timestamp = datetime.now().isoformat()
    logger.info("=" * 60)
    logger.info(f"🚀 Starting MySQL to MinIO Pipeline at {timestamp}")

    # Log initial GTID state
    logger.info("📍 Capturing GTID state before pipeline run...")
    gtid_before = get_mysql_gtid_info()

    # Create pipeline to filesystem destination
    pipeline = dlt.pipeline(
        pipeline_name="mysql_to_minio",
        destination='filesystem',
        dataset_name="warehouse"
    )

    # Run pipeline
    logger.info("📦 Loading data from MySQL to MinIO...")
    load_info = pipeline.run(mysql_source())

    # Log final GTID state
    logger.info("📍 Capturing GTID state after pipeline run...")
    gtid_after = get_mysql_gtid_info()

    # Prepare run info
    run_info = {
        'pipeline_name': 'mysql_to_minio',
        'load_package': str(load_info.load_packages[0]) if load_info.load_packages else None,
        'status': 'completed'
    }

    # Try to get row count from load info
    try:
        if load_info.load_packages:
            # LoadPackageInfo has different attributes, just count what we can
            counts = [pkg.counts['insert'] if 'insert' in pkg.counts else 0 for pkg in load_info.load_packages]
            run_info['rows_loaded'] = sum(counts)
    except:
        run_info['rows_loaded'] = 0

    # Log GTID information
    log_gtid_info(run_info)

    logger.info("✅ Pipeline completed!")
    logger.info(f"📊 Load info: {load_info}")
    logger.info(f"📦 Data stored in: s3://dlt-warehouse/")
    logger.info(f"   MinIO Console: http://localhost:9001")
    logger.info("=" * 60)

    return load_info


if __name__ == "__main__":
    main()
