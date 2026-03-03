"""
DuckDB helper to query CDC data from MinIO
Reads JSONL (DLT cdc_events) and Parquet (Iceberg-style) written by the pipeline
"""

import os
import duckdb
from typing import List, Dict, Any, Optional


# DLT CDC dataset path (connector uses dataset_name=debezium_cdc, table_name=cdc_events)
CDC_EVENTS_PATH = "debezium_cdc/cdc_events"
ICEBERG_PREFIX = "iceberg"


class IcebergDuckDB:
    """DuckDB wrapper for querying CDC/DLT data on MinIO"""

    def __init__(self,
                 minio_endpoint: str = "http://minio:9000",
                 access_key: str = "minio",
                 secret_key: str = "minio123",
                 bucket: str = "dlt-warehouse"):
        """
        Initialize DuckDB with MinIO/S3 configuration

        Args:
            minio_endpoint: MinIO/S3 endpoint URL
            access_key: S3 access key
            secret_key: S3 secret key
            bucket: S3 bucket name
        """
        self.minio_endpoint = minio_endpoint.replace('http://', '').replace('https://', '').strip('/')
        self.access_key = access_key
        self.secret_key = secret_key
        self.bucket = bucket
        self._base = f"s3://{bucket}"

        # Initialize DuckDB connection
        self.con = duckdb.connect(':memory:')

        # Configure S3/MinIO connection
        self._configure_s3()

    def _configure_s3(self):
        """Configure DuckDB to work with MinIO/S3"""
        self.con.execute(f"""
            INSTALL httpfs;
            LOAD httpfs;

            SET s3_endpoint = '{self.minio_endpoint}';
            SET s3_access_key_id = '{self.access_key}';
            SET s3_secret_access_key = '{self.secret_key}';
            SET s3_use_ssl = false;
            SET s3_url_style = 'path';
        """)

    def _cdc_events_glob(self) -> str:
        """Path to CDC events JSONL (DLT output)"""
        return f"{self._base}/{CDC_EVENTS_PATH}/*.jsonl.gz"

    def _parquet_glob(self, table: str) -> str:
        """Path to Parquet for a logical table (appdb.products or appdb.sales)"""
        return f"{self._base}/{ICEBERG_PREFIX}/appdb.{table}/**/*.parquet"

    def list_tables(self) -> List[str]:
        """List available logical tables (products, sales) from CDC events or Parquet"""
        known = ['products', 'sales']
        existing = []

        # Prefer CDC events path (single source of truth)
        try:
            q = f"""
                SELECT DISTINCT _table AS t
                FROM read_json_auto('{self._cdc_events_glob()}', union_by_name=true)
                WHERE _table IS NOT NULL
            """
            rows = self.con.execute(q).fetchall()
            if rows:
                return [r[0] for r in rows]
        except Exception:
            pass

        # Fallback: check Parquet per table
        for table in known:
            try:
                self.con.execute(f"""
                    SELECT 1 FROM '{self._parquet_glob(table)}' LIMIT 1
                """).fetchone()
                existing.append(table)
            except Exception:
                try:
                    self.con.execute(f"""
                        SELECT 1 FROM read_json_auto('{self._base}/{CDC_EVENTS_PATH}/*.jsonl.gz', union_by_name=true)
                        WHERE _table = '{table}' LIMIT 1
                    """).fetchone()
                    existing.append(table)
                except Exception:
                    continue
        return existing if existing else known

    def query(self, sql: str) -> List[Dict[str, Any]]:
        """
        Execute SQL query and return results

        Args:
            sql: SQL query string

        Returns:
            List of dictionaries representing rows
        """
        try:
            result_df = self.con.execute(sql).fetchdf()
            return result_df.to_dict(orient='records')
        except Exception as e:
            raise Exception(f"Query failed: {str(e)}")

    def query_table(self, table_name: str, limit: int = 100, latest_only: bool = True) -> List[Dict[str, Any]]:
        """
        Query a logical table (products or sales).
        Reads from CDC events and returns latest state per primary key when latest_only=True.
        """
        events_path = self._cdc_events_glob()
        # Latest state: take row with max _ts per id (or per primary key)
        if latest_only and table_name in ('products', 'sales'):
            sql = f"""
                WITH ranked AS (
                    SELECT *,
                           ROW_NUMBER() OVER (PARTITION BY id ORDER BY _ts DESC NULLS LAST) AS rn
                    FROM read_json_auto('{events_path}', union_by_name=true)
                    WHERE _table = '{table_name}'
                )
                SELECT * EXCLUDE (rn, _op, _ts, _db, _table)
                FROM ranked
                WHERE rn = 1 AND _op != 'd'
                LIMIT {limit}
            """
        else:
            sql = f"""
                SELECT *
                FROM read_json_auto('{events_path}', union_by_name=true)
                WHERE _table = '{table_name}'
                ORDER BY _ts DESC
                LIMIT {limit}
            """
        return self.query(sql)

    def query_cdc_events(self, table_name: Optional[str] = None, limit: int = 200) -> List[Dict[str, Any]]:
        """Raw CDC events (with _op, _ts, _cdc_gtid, etc.) for verification"""
        where = f"WHERE _table = '{table_name}'" if table_name else ""
        sql = f"""
            SELECT _op, _ts, _db, _table, _cdc_gtid, _cdc_binlog_file, _cdc_binlog_pos, id, *
            FROM read_json_auto('{self._cdc_events_glob()}', union_by_name=true)
            {where}
            ORDER BY _ts DESC
            LIMIT {limit}
        """
        return self.query(sql)

    def get_table_schema(self, table_name: str) -> List[Dict[str, str]]:
        """Get schema from CDC events (data columns; CDC _* columns included for transparency)"""
        sql = f"""
            DESCRIBE SELECT * FROM read_json_auto('{self._cdc_events_glob()}', union_by_name=true)
            WHERE _table = '{table_name}' LIMIT 1
        """
        try:
            result = self.con.execute(sql).fetchdf()
            return [
                {'column_name': r['column_name'], 'column_type': str(r['column_type'])}
                for _, r in result.iterrows()
            ]
        except Exception as e:
            raise Exception(f"Failed to get schema: {str(e)}")

    def get_row_count(self, table_name: str, latest_only: bool = True) -> int:
        """Total row count (latest state only when latest_only=True)"""
        events_path = self._cdc_events_glob()
        if latest_only:
            sql = f"""
                WITH ranked AS (
                    SELECT id, ROW_NUMBER() OVER (PARTITION BY id ORDER BY _ts DESC) AS rn
                    FROM read_json_auto('{events_path}', union_by_name=true)
                    WHERE _table = '{table_name}' AND _op != 'd'
                )
                SELECT COUNT(*) FROM ranked WHERE rn = 1
            """
        else:
            sql = f"""
                SELECT COUNT(*) FROM read_json_auto('{events_path}', union_by_name=true)
                WHERE _table = '{table_name}'
            """
        try:
            r = self.con.execute(sql).fetchone()
            return r[0] if r else 0
        except Exception:
            return 0

    def get_table_stats(self, table_name: str) -> Dict[str, Any]:
        """Get statistics for a table"""
        try:
            row_count = self.get_row_count(table_name)
            schema = self.get_table_schema(table_name)
            return {
                'table_name': table_name,
                'row_count': row_count,
                'column_count': len(schema),
                'columns': [col['column_name'] for col in schema]
            }
        except Exception as e:
            return {
                'table_name': table_name,
                'error': str(e)
            }

    def execute_sql(self, sql: str, as_df: bool = False):
        """
        Execute custom SQL query

        Args:
            sql: SQL query
            as_df: Return as pandas DataFrame if True

        Returns:
            Query results (DataFrame or list of dicts)
        """
        try:
            result = self.con.execute(sql)
            if as_df:
                return result.fetchdf()
            return result.fetchall()
        except Exception as e:
            raise Exception(f"SQL execution failed: {str(e)}")

    def get_gtid_summary(self) -> Dict[str, Any]:
        """Summary of GTIDs and event counts from CDC events for verification"""
        try:
            q = f"""
                SELECT
                    _table,
                    _op,
                    COUNT(*) AS cnt,
                    MIN(_ts) AS min_ts,
                    MAX(_ts) AS max_ts,
                    COUNT(DISTINCT _cdc_gtid) AS distinct_gtids
                FROM read_json_auto('{self._cdc_events_glob()}', union_by_name=true)
                GROUP BY _table, _op
                ORDER BY _table, _op
            """
            rows = self.con.execute(q).fetchdf()
            return rows.to_dict(orient='records') if rows is not None and len(rows) > 0 else []
        except Exception as e:
            return {'error': str(e)}


# Singleton instance
_duckdb_instance: Optional[IcebergDuckDB] = None


def get_duckdb() -> IcebergDuckDB:
    """Get or create DuckDB instance"""
    global _duckdb_instance
    if _duckdb_instance is None:
        _duckdb_instance = IcebergDuckDB(
            minio_endpoint=os.getenv("S3_ENDPOINT_URL", "http://minio:9000"),
            access_key=os.getenv("S3_ACCESS_KEY", "minio"),
            secret_key=os.getenv("S3_SECRET_KEY", "minio123"),
            bucket=os.getenv("S3_BUCKET", "dlt-warehouse")
        )
    return _duckdb_instance


if __name__ == "__main__":
    print("Testing DuckDB connection to MinIO...")
    db = IcebergDuckDB()

    print("\n1. Testing S3 configuration...")
    print("✓ S3 configured")

    print("\n2. Listing available tables...")
    tables = db.list_tables()
    print(f"Found {len(tables)} tables: {tables}")

    if tables:
        t = tables[0]
        print(f"\n3. Getting schema for {t}")
        stats = db.get_table_stats(t)
        print(f"Stats: {stats}")

        print(f"\n4. Querying first 5 rows from {t}...")
        rows = db.query_table(t, limit=5)
        print(f"Rows: {rows}")

        print("\n5. GTID summary:")
        print(db.get_gtid_summary())
    else:
        print("\n⚠ No tables found. Run the CDC pipeline first.")
