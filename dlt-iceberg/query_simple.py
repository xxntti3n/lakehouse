#!/usr/bin/env python3
"""Simple Iceberg table query tool"""
import sys
import duckdb

# Connection setup
con = duckdb.connect()
con.execute("INSTALL iceberg; LOAD iceberg")
con.execute("SET s3_endpoint = 'minio:9000'")
con.execute("SET s3_access_key_id = 'minio'")
con.execute("SET s3_secret_access_key = 'minio123'")
con.execute("SET s3_use_ssl = false")
con.execute("SET s3_url_style = 'path'")

METADATA = "s3://dlt-warehouse/debezium_cdc/cdc_events/metadata/00022-324a4122-8719-461c-9ad7-ddff7d45de01.metadata.json"

if len(sys.argv) > 1:
    # Custom query - user must use full syntax with alias
    sql = sys.argv[1]
    print(f"Query: {sql}")

    # Wrap query to use Iceberg table
    if 'iceberg_scan' not in sql:
        if 'FROM' in sql.upper():
            # Replace FROM clause
            base_sql = sql
        else:
            base_sql = f"{sql} FROM iceberg_scan('{METADATA}')"
    else:
        base_sql = sql

    con.execute(base_sql)

    # Print results
    if con.description:
        headers = [d[0] for d in con.description]
        print(" | ".join(headers))
        print("-" * 60)
        for row in con.fetchall():
            print(" | ".join(str(v)[:20] for v in row))
    else:
        for row in con.fetchall():
            print(row)
else:
    # Show table info
    con.execute(f"SELECT COUNT(*) FROM iceberg_scan('{METADATA}')")
    row_count = con.fetchone()[0]

    con.execute(f"SELECT _table, _op, COUNT(*) FROM iceberg_scan('{METADATA}') GROUP BY _table, _op")

    print("Iceberg Table: debezium_cdc.cdc_events")
    print("=" * 50)
    print(f"Total Rows: {row_count:,}")
    print()
    print("By Table:")
    print(f"{'Table':<15} {'Op':<4} {'Rows':>8}")
    print("-" * 30)
    for row in con.fetchall():
        print(f"{row[0]:<15} {row[1]:<4} {row[2]:>8}")
    print()
    print("Sample Data:")
    con.execute(f"SELECT _table, name, price, sale_date FROM iceberg_scan('{METADATA}') LIMIT 3")
    for row in con.fetchall():
        print(f"  {row[0]}: {row[1]} - ${row[2]} - {row[3]}")
    print()
    print("Usage:")
    print("  python query_simple.py \"SELECT * LIMIT 10\"")
