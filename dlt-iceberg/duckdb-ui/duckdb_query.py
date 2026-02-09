"""
DuckDB helper to query DLT data from MinIO
Reads Parquet files written by DLT
"""

import os
import duckdb
from typing import List, Dict, Any


class IcebergDuckDB:
    """DuckDB wrapper for querying DLT data on MinIO"""

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
        self.minio_endpoint = minio_endpoint
        self.access_key = access_key
        self.secret_key = secret_key
        self.bucket = bucket

        # Initialize DuckDB connection
        self.con = duckdb.connect(':memory:')

        # Configure S3/MinIO connection
        self._configure_s3()

    def _configure_s3(self):
        """Configure DuckDB to work with MinIO/S3"""
        self.con.execute(f"""
            INSTALL httpfs;
            LOAD httpfs;

            SET s3_endpoint = '{self.minio_endpoint.replace('http://', '').replace('https://', '')}';
            SET s3_access_key_id = '{self.access_key}';
            SET s3_secret_access_key = '{self.secret_key}';
            SET s3_use_ssl = false;
            SET s3_url_style = 'path';
        """)

    def list_tables(self) -> List[str]:
        """List available tables (DLT datasets)"""
        # Since DLT writes data in a predictable structure and glob may not work well,
        # we'll return the known table names and verify they exist
        known_tables = ['products', 'sales']
        existing_tables = []

        for table in known_tables:
            try:
                # Test if we can read from this table
                result = self.con.execute(f"""
                    SELECT COUNT(*) as cnt
                    FROM read_json_auto('s3://{self.bucket}/warehouse/{table}/*.jsonl.gz', union_by_name=true)
                    LIMIT 1
                """).fetchone()
                if result and result[0] > 0:
                    existing_tables.append(table)
            except Exception as e:
                print(f"Could not access table {table}: {e}")
                continue

        return existing_tables

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

    def query_table(self, table_name: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Query a specific table (reads all JSONL files for that table)

        Args:
            table_name: Name of the table (e.g., 'products', 'sales')
            limit: Maximum number of rows to return

        Returns:
            List of dictionaries representing rows
        """
        # DLT writes to s3://bucket/dataset_name/table_name/*.jsonl.gz
        # where dataset_name is 'warehouse' by default
        sql = f"""
            SELECT *
            FROM read_json_auto('s3://{self.bucket}/warehouse/{table_name}/*.jsonl.gz', union_by_name=true)
            LIMIT {limit}
        """
        return self.query(sql)

    def get_table_schema(self, table_name: str) -> List[Dict[str, str]]:
        """
        Get schema information for a table

        Args:
            table_name: Name of the table

        Returns:
            List of column info dictionaries
        """
        sql = f"""
            DESCRIBE
            SELECT * FROM read_json_auto('s3://{self.bucket}/warehouse/{table_name}/*.jsonl.gz', union_by_name=true)
            LIMIT 1
        """
        try:
            result = self.con.execute(sql).fetchdf()
            return result.to_dict(orient='records')
        except Exception as e:
            raise Exception(f"Failed to get schema: {str(e)}")

    def get_row_count(self, table_name: str) -> int:
        """Get total row count for a table"""
        sql = f"""
            SELECT COUNT(*) as count
            FROM read_json_auto('s3://{self.bucket}/warehouse/{table_name}/*.jsonl.gz', union_by_name=true)
        """
        try:
            result = self.con.execute(sql).fetchone()
            return result[0] if result else 0
        except Exception as e:
            return 0

    def get_table_stats(self, table_name: str) -> Dict[str, Any]:
        """Get statistics for a table"""
        try:
            # Get row count
            row_count = self.get_row_count(table_name)

            # Get schema
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

    def execute_sql(self, sql: str, as_df=False):
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
            return result.fetchnumpy()
        except Exception as e:
            raise Exception(f"SQL execution failed: {str(e)}")


# Singleton instance
_duckdb_instance = None


def get_duckdb():
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
    # Test the connection
    print("Testing DuckDB connection to MinIO...")
    db = IcebergDuckDB()

    print("\n1. Testing S3 configuration...")
    print("✓ S3 configured")

    print("\n2. Listing available tables...")
    tables = db.list_tables()
    print(f"Found {len(tables)} tables: {tables}")

    if tables:
        print(f"\n3. Getting schema for first table: {tables[0]}")
        stats = db.get_table_stats(tables[0])
        print(f"Stats: {stats}")

        print(f"\n4. Querying first 5 rows from {tables[0]}...")
        rows = db.query_table(tables[0], limit=5)
        print(f"Rows: {rows}")
    else:
        print("\n⚠ No tables found. Make sure DLT has loaded data to MinIO.")
