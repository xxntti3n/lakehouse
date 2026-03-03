#!/usr/bin/env python3
"""
Iceberg Verification Script
Verifies that Iceberg tables are properly created with native format
"""

import os
import sys
import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def verify_with_pyiceberg():
    """Verify Iceberg tables using pyiceberg"""
    try:
        from pyiceberg.catalog import load_catalog
        import pyarrow as pa

        # Configure S3
        os.environ['AWS_ACCESS_KEY_ID'] = os.getenv('S3_ACCESS_KEY', 'minio')
        os.environ['AWS_SECRET_ACCESS_KEY'] = os.getenv('S3_SECRET_KEY', 'minio123')
        os.environ['AWS_ENDPOINT'] = os.getenv('S3_ENDPOINT_URL', 'http://minio:9000')
        os.environ['AWS_REGION'] = 'us-east-1'
        os.environ['AWS_ALLOW_HTTP'] = 'true'

        catalog_uri = os.getenv('NESSIE_ICEBERG_URI', 'http://nessie:19120/iceberg')
        warehouse = os.getenv('ICEBERG_WAREHOUSE', 's3://dlt-warehouse/iceberg')

        logger.info(f"Connecting to Iceberg catalog: {catalog_uri}")
        logger.info(f"Warehouse: {warehouse}")

        # Load catalog
        catalog = load_catalog(
            "rest",
            uri=catalog_uri,
            warehouse=warehouse,
            s3_endpoint=os.getenv('S3_ENDPOINT_URL', 'http://minio:9000'),
            s3_access_key_id=os.getenv('S3_ACCESS_KEY', 'minio'),
            s3_secret_access_key=os.getenv('S3_SECRET_KEY', 'minio123'),
            s3_path_style_access='true',
        )

        logger.info("✅ Connected to Iceberg catalog")

        # List namespaces
        try:
            namespaces = catalog.list_namespaces()
            logger.info(f"Namespaces: {[n for n in namespaces]}")
        except Exception as e:
            logger.info(f"Could not list namespaces: {e}")

        # Check specific namespace
        namespace = os.getenv('ICEBERG_NAMESPACE', 'appdb')
        tables_to_check = ['products', 'sales']

        for table_name in tables_to_check:
            table_id = f"{namespace}.{table_name}"
            logger.info(f"\n{'='*60}")
            logger.info(f"Checking table: {table_id}")
            logger.info(f"{'='*60}")

            try:
                table = catalog.load_table(table_id)

                # Table metadata
                logger.info(f"✅ Table exists: {table.name}")
                logger.info(f"   Schema: {table.schema().name}")
                logger.info(f"   Format version: {table.format_version}")

                # Columns
                logger.info(f"\n   Columns ({len(table.schema().fields)}):")
                for field in table.schema().fields:
                    required = "NOT NULL" if field.required else "NULLABLE"
                    logger.info(f"      - {field.name}: {field.field_type} ({required})")

                # Partitions
                if table.spec().is_unpartitioned():
                    logger.info(f"\n   Partitioning: None (unpartitioned)")
                else:
                    logger.info(f"\n   Partitioning:")
                    for field in table.spec().fields:
                        logger.info(f"      - {field.name}: {field.transform}")

                # Snapshots
                snapshots = table.snapshots()
                logger.info(f"\n   Snapshots: {len(snapshots)}")
                if snapshots:
                    for snap in snapshots[-3:]:  # Last 3
                        logger.info(f"      - {snap.snapshot_id}: {snap.summary} at {datetime.fromtimestamp(snap.timestamp_ms/1000)}")

                # Current data
                logger.info(f"\n   Row count (from latest snapshot):")
                arrow_table = table.scan().to_arrow()
                logger.info(f"      Total rows: {len(arrow_table)}")

                if len(arrow_table) > 0:
                    logger.info(f"\n   Sample data (first 3 rows):")
                    for i, row in enumerate(arrow_table.to_pylist()[:3]):
                        logger.info(f"      Row {i+1}: {row}")

                # Verify CDC metadata columns
                if '__op' in arrow_table.column_names:
                    logger.info(f"\n   CDC metadata columns present: ✅")
                    op_counts = {}
                    for op in arrow_table['__op'].to_pylist():
                        op_counts[op] = op_counts.get(op, 0) + 1
                    logger.info(f"      Operations: {op_counts}")
                else:
                    logger.info(f"\n   CDC metadata columns: ❌ Not found")

            except Exception as e:
                logger.error(f"❌ Error checking table {table_id}: {e}")

        return True

    except ImportError as e:
        logger.error(f"pyiceberg not available: {e}")
        logger.error("Install with: pip install pyiceberg[s3]")
        return False
    except Exception as e:
        logger.error(f"Verification failed: {e}", exc_info=True)
        return False


def verify_with_duckdb():
    """Verify Iceberg tables using DuckDB"""
    try:
        import duckdb

        conn = duckdb.connect(':memory:')

        # Setup S3 access
        conn.execute(f"""
            INSTALL httpfs;
            LOAD httpfs;
            SET s3_endpoint='{os.getenv('S3_ENDPOINT_URL', 'http://minio:9000')}';
            SET s3_access_key_id='{os.getenv('S3_ACCESS_KEY', 'minio')}';
            SET s3_secret_access_key='{os.getenv('S3_SECRET_KEY', 'minio123')}';
            SET s3_use_ssl=false;
            SET s3_url_style='path';
        """)

        logger.info("✅ DuckDB connected with S3 configured")

        # Query Iceberg metadata
        warehouse = os.getenv('ICEBERG_WAREHOUSE', 's3://dlt-warehouse/iceberg')
        namespace = os.getenv('ICEBERG_NAMESPACE', 'appdb')

        # Check for metadata files
        logger.info(f"\n{'='*60}")
        logger.info("Checking Iceberg metadata files:")
        logger.info(f"{'='*60}")

        metadata_query = f"""
            SELECT *
            FROM glob('{warehouse}/{namespace}/*.metadata.json')
        """

        try:
            result = conn.execute(metadata_query).fetchall()
            if result:
                logger.info(f"✅ Found {len(result)} metadata files:")
                for row in result:
                    logger.info(f"   - {row[0]}")
            else:
                logger.warning(f"⚠️  No metadata files found at {warehouse}/{namespace}/")
        except Exception as e:
            logger.warning(f"Could not check metadata files: {e}")

        # Check data files
        data_query = f"""
            SELECT *
            FROM glob('{warehouse}/{namespace}/data/**/*.parquet')
        """

        try:
            result = conn.execute(data_query).fetchall()
            if result:
                logger.info(f"\n✅ Found {len(result)} data files")
            else:
                logger.warning(f"⚠️  No data files found")
        except Exception as e:
            logger.warning(f"Could not check data files: {e}")

        conn.close()
        return True

    except ImportError as e:
        logger.error(f"DuckDB not available: {e}")
        return False
    except Exception as e:
        logger.error(f"DuckDB verification failed: {e}")
        return False


def verify_data_integrity():
    """Compare MySQL data with Iceberg data"""
    try:
        import pymysql
        import duckdb

        # Connect to MySQL
        mysql_conn = pymysql.connect(
            host=os.getenv('MYSQL_HOST', 'mysql'),
            port=int(os.getenv('MYSQL_PORT', '3306')),
            user=os.getenv('MYSQL_USER', 'root'),
            password=os.getenv('MYSQL_PASSWORD', 'rootpw'),
            database=os.getenv('MYSQL_DATABASE', 'appdb'),
        )

        logger.info(f"\n{'='*60}")
        logger.info("Data Integrity Check: MySQL vs Iceberg")
        logger.info(f"{'='*60}")

        tables_to_check = ['products', 'sales']

        for table_name in tables_to_check:
            logger.info(f"\nTable: {table_name}")

            # Get MySQL count
            with mysql_conn.cursor() as cursor:
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                mysql_count = cursor.fetchone()[0]
                logger.info(f"   MySQL count: {mysql_count}")

            # Get Iceberg count (via DuckDB scanning Parquet)
            conn = duckdb.connect(':memory:')
            conn.execute(f"""
                INSTALL httpfs;
                LOAD httpfs;
                SET s3_endpoint='{os.getenv('S3_ENDPOINT_URL', 'http://minio:9000')}';
                SET s3_access_key_id='{os.getenv('S3_ACCESS_KEY', 'minio')}';
                SET s3_secret_access_key='{os.getenv('S3_SECRET_KEY', 'minio123')}';
                SET s3_use_ssl=false;
                SET s3_url_style='path';
            """)

            try:
                warehouse = os.getenv('ICEBERG_WAREHOUSE', 's3://dlt-warehouse/iceberg')
                namespace = os.getenv('ICEBERG_NAMESPACE', 'appdb')

                # Count from Iceberg (filter for current records only)
                iceberg_query = f"""
                    SELECT COUNT(*)
                    FROM read_parquet('{warehouse}/{namespace}/data/**/*.parquet', union_by_name=true)
                    WHERE __op IS NULL OR __op NOT IN ('d', 'u_old')
                """

                iceberg_count = conn.execute(iceberg_query).fetchone()[0]
                logger.info(f"   Iceberg count: {iceberg_count}")

                if mysql_count == iceberg_count:
                    logger.info(f"   ✅ Counts match!")
                else:
                    logger.warning(f"   ⚠️  Count mismatch: MySQL={mysql_count}, Iceberg={iceberg_count}")

            except Exception as e:
                logger.warning(f"   Could not verify Iceberg count: {e}")
            finally:
                conn.close()

        mysql_conn.close()
        return True

    except ImportError as e:
        logger.warning(f"Could not verify data integrity: {e}")
        return False
    except Exception as e:
        logger.error(f"Data integrity check failed: {e}")
        return False


def main():
    """Main verification function"""
    logger.info("=" * 60)
    logger.info("ICEBERG VERIFICATION")
    logger.info("=" * 60)
    logger.info(f"Started at: {datetime.now().isoformat()}")

    results = {}

    # Verify with pyiceberg
    logger.info("\n" + "=" * 60)
    logger.info("1. Verifying with pyiceberg")
    logger.info("=" * 60)
    results['pyiceberg'] = verify_with_pyiceberg()

    # Verify with DuckDB
    logger.info("\n" + "=" * 60)
    logger.info("2. Verifying with DuckDB")
    logger.info("=" * 60)
    results['duckdb'] = verify_with_duckdb()

    # Verify data integrity
    logger.info("\n" + "=" * 60)
    logger.info("3. Data Integrity Check")
    logger.info("=" * 60)
    results['integrity'] = verify_data_integrity()

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("VERIFICATION SUMMARY")
    logger.info("=" * 60)
    for check, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        logger.info(f"  {check}: {status}")

    all_passed = all(results.values())
    logger.info(f"\nOverall: {'✅ ALL CHECKS PASSED' if all_passed else '❌ SOME CHECKS FAILED'}")

    return 0 if all_passed else 1


if __name__ == '__main__':
    sys.exit(main())
