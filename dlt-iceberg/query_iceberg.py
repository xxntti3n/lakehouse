#!/usr/bin/env python3
"""
Simple query interface for DLT Iceberg tables
Usage: python query_iceberg.py "SELECT COUNT(*) FROM table"
"""

import sys
import duckdb
from datetime import datetime

def get_connection():
    """Create DuckDB connection configured for MinIO"""
    con = duckdb.connect()
    con.execute("INSTALL iceberg; LOAD iceberg")
    con.execute("SET s3_endpoint = 'minio:9000'")
    con.execute("SET s3_access_key_id = 'minio'")
    con.execute("SET s3_secret_access_key = 'minio123'")
    con.execute("SET s3_use_ssl = false")
    con.execute("SET s3_url_style = 'path'")
    return con

def get_iceberg_table_info():
    """Get information about available Iceberg tables"""
    con = get_connection()

    info = {
        'table': 'debezium_cdc.cdc_events',
        'metadata_location': 's3://dlt-warehouse/debezium_cdc/cdc_events/metadata/00022-324a4122-8719-461c-9ad7-ddff7d45de01.metadata.json',
        'data_location': 's3://dlt-warehouse/debezium_cdc/cdc_events/data/',
    }

    # Get row count
    result = con.execute(f"""
        SELECT COUNT(*) as row_count
        FROM iceberg_scan('{info['metadata_location']}')
    """).fetchone()
    info['row_count'] = result[0]

    # Get table schema
    schema = con.execute(f"""
        DESCRIBE SELECT * FROM iceberg_scan('{info['metadata_location']}')
    """).fetchall()
    info['columns'] = [(col[0], col[1]) for col in schema]

    # Get sample data
    sample = con.execute(f"""
        SELECT * FROM iceberg_scan('{info['metadata_location']}')
        LIMIT 5
    """).fetchall()
    info['sample'] = sample

    return info

def query_iceberg(sql_query):
    """Execute a SQL query on the Iceberg table"""
    con = get_connection()

    metadata = 's3://dlt-warehouse/debezium_cdc/cdc_events/metadata/00022-324a4122-8719-461c-9ad7-ddff7d45de01.metadata.json'

    # If query doesn't specify FROM clause, add it
    if 'FROM' not in sql_query.upper():
        # Simple projection or aggregate - add FROM
        full_query = f"{sql_query} FROM iceberg_scan('{metadata}') AS t"
    else:
        # Replace table references with Iceberg scan
        full_query = sql_query.replace('FROM cdc_events', f"FROM iceberg_scan('{metadata}')")
        full_query = full_query.replace('FROM debezium_cdc', f"FROM iceberg_scan('{metadata}')")
        full_query = full_query.replace('FROM t', "FROM iceberg_scan('{metadata}') AS t")

    return con.execute(full_query).fetchall()

def main():
    if len(sys.argv) > 1:
        # Execute custom query
        sql = ' '.join(sys.argv[1:])
        print(f"Executing: {sql}")
        print("-" * 50)

        try:
            results = query_iceberg(sql)

            # Get column names
            con = get_connection()
            desc = con.description
            if desc:
                headers = [d[0] for d in desc]
                print(" | ".join(headers))
                print("-" * 50)
                for row in results:
                    print(" | ".join(str(v)[:20] for v in row))
            else:
                for row in results:
                    print(row)

        except Exception as e:
            print(f"Error: {e}")
    else:
        # Show table info
        info = get_iceberg_table_info()

        print("╔═══════════════════════════════════════════════════════════════╗")
        print(f"║  ICEBERG TABLE: {info['table']}")
        print("╚═══════════════════════════════════════════════════════════════╝")
        print()
        print(f"  Rows:     {info['row_count']:,}")
        print(f"  Metadata: {info['metadata_location']}")
        print(f"  Data:     {info['data_location']}")
        print()
        print("  Columns:")
        for col_name, col_type in info['columns'][:15]:
            print(f"    {col_name:<25} {col_type}")
        if len(info['columns']) > 15:
            print(f"    ... and {len(info['columns']) - 15} more")
        print()
        print("  Sample Data:")
        for row in info['sample'][:5]:
            print(f"    {row}")
        print()
        print("Usage:")
        print("  python query_iceberg.py \"SELECT * LIMIT 10\"")
        print("  python query_iceberg.py \"SELECT _table, COUNT(*) GROUP BY _table\"")

if __name__ == "__main__":
    main()
