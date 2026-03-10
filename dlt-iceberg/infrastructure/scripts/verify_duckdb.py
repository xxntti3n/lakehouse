#!/usr/bin/env python3
"""
DuckDB Verification Script for Debezium CDC Data
Queries CDC events stored in MinIO (S3) and displays statistics.
Optionally compares row counts with MySQL for consistency.
Run from project root or: docker exec -it debezium-dlt-connector python /app/scripts/verify_duckdb.py
"""

import os
import sys
import json


def verify_cdc_with_duckdb():
    """Verify CDC data using DuckDB (read from S3/MinIO)"""

    try:
        import duckdb

        s3_endpoint = os.getenv('S3_ENDPOINT_URL', 'http://minio:9000')
        s3_endpoint = s3_endpoint.replace('http://', '').replace('https://', '').strip('/')
        s3_access_key = os.getenv('S3_ACCESS_KEY', 'minio')
        s3_secret_key = os.getenv('S3_SECRET_KEY', 'minio123')
        bucket = os.getenv('DEST_BUCKET', 'dlt-warehouse')
        cdc_path = f"s3://{bucket}/debezium_cdc/cdc_events/*.jsonl.gz"

        conn = duckdb.connect(':memory:')

        print("=" * 80)
        print("🔧 CONFIGURING DUCKDB WITH MINIO")
        print("=" * 80)

        conn.execute(f"""
            INSTALL httpfs;
            LOAD httpfs;
            SET s3_endpoint = '{s3_endpoint}';
            SET s3_access_key_id = '{s3_access_key}';
            SET s3_secret_access_key = '{s3_secret_key}';
            SET s3_use_ssl = false;
            SET s3_url_style = 'path';
        """)

        print(f"✅ MinIO endpoint: {s3_endpoint}")
        print(f"📦 CDC path: {cdc_path}\n")

        print("=" * 80)
        print("📊 ANALYZING CDC EVENTS FROM S3")
        print("=" * 80)

        try:
            conn.execute(f"""
                SELECT 1 FROM read_json_auto('{cdc_path}', union_by_name=true) LIMIT 1
            """).fetchone()
        except Exception as e:
            print(f"⚠️  Could not read CDC events from S3: {e}")
            print("   Ensure the pipeline has run at least once and MinIO is reachable.")
            return False

        # Count by operation
        op_counts = conn.execute(f"""
            SELECT _op AS op, COUNT(*) AS cnt
            FROM read_json_auto('{cdc_path}', union_by_name=true)
            GROUP BY _op
        """).fetchall()

        print("\n🔄 Events by operation:")
        op_names = {'c': 'CREATE', 'r': 'READ (snapshot)', 'u': 'UPDATE', 'd': 'DELETE'}
        for row in op_counts:
            name = op_names.get(row[0], row[0])
            print(f"  {name}: {row[1]}")

        # Count by table
        table_counts = conn.execute(f"""
            SELECT _table AS tbl, COUNT(*) AS cnt
            FROM read_json_auto('{cdc_path}', union_by_name=true)
            GROUP BY _table
        """).fetchall()

        print("\n📊 Events by table:")
        for row in table_counts:
            print(f"  {row[0]}: {row[1]}")

        # Latest row count (deduplicated by id, latest _ts)
        for table in ['products', 'sales']:
            try:
                latest_count = conn.execute(f"""
                    WITH ranked AS (
                        SELECT id, ROW_NUMBER() OVER (PARTITION BY id ORDER BY _ts DESC) AS rn
                        FROM read_json_auto('{cdc_path}', union_by_name=true)
                        WHERE _table = '{table}' AND _op != 'd'
                    )
                    SELECT COUNT(*) AS c FROM ranked WHERE rn = 1
                """).fetchone()[0]
                print(f"\n  📋 {table} (latest state rows): {latest_count}")
            except Exception:
                pass

        # GTIDs
        gtids = conn.execute(f"""
            SELECT DISTINCT _cdc_gtid FROM read_json_auto('{cdc_path}', union_by_name=true)
            WHERE _cdc_gtid IS NOT NULL AND _cdc_gtid != ''
        """).fetchall()
        print("\n📍 Distinct GTIDs in CDC data:", len(gtids))
        if gtids and len(gtids) <= 10:
            for (g,) in gtids:
                print(f"  {g}")
        elif gtids:
            for (g,) in gtids[:5]:
                print(f"  {g}")
            print(f"  ... and {len(gtids) - 5} more")

        # Optional: compare with MySQL
        mysql_host = os.getenv('MYSQL_HOST', 'mysql')
        if mysql_host:
            try:
                import pymysql
                m = pymysql.connect(
                    host=mysql_host,
                    port=int(os.getenv('MYSQL_PORT', '3306')),
                    user=os.getenv('MYSQL_USER', 'root'),
                    password=os.getenv('MYSQL_PASSWORD', 'rootpw'),
                    database=os.getenv('MYSQL_DATABASE', 'appdb')
                )
                cur = m.cursor()
                print("\n" + "=" * 80)
                print("📐 MYSQL vs CDC CONSISTENCY CHECK")
                print("=" * 80)
                for table in ['products', 'sales']:
                    cur.execute(f"SELECT COUNT(*) FROM {table}")
                    mysql_count = cur.fetchone()[0]
                    try:
                        cdc_count = conn.execute(f"""
                            WITH ranked AS (
                                SELECT id, ROW_NUMBER() OVER (PARTITION BY id ORDER BY _ts DESC) AS rn
                                FROM read_json_auto('{cdc_path}', union_by_name=true)
                                WHERE _table = '{table}' AND _op != 'd'
                            )
                            SELECT COUNT(*) FROM ranked WHERE rn = 1
                        """).fetchone()[0]
                        ok = "✅" if mysql_count == cdc_count else "⚠️"
                        print(f"  {table}: MySQL={mysql_count}, CDC(latest)={cdc_count} {ok}")
                    except Exception as e:
                        print(f"  {table}: MySQL={mysql_count}, CDC error={e}")
                m.close()
            except ImportError:
                pass
            except Exception as e:
                print(f"  (MySQL check skipped: {e})")

        print("\n" + "=" * 80)
        print("✅ VERIFICATION COMPLETE")
        print("=" * 80)
        return True

    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        return False
    except Exception as e:
        print(f"❌ Verification failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = verify_cdc_with_duckdb()
    sys.exit(0 if success else 1)
