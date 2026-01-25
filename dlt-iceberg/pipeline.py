"""
DLT Pipeline: MySQL to Iceberg (MinIO S3)
Loads products and sales data from MySQL to MinIO S3 in Iceberg/Parquet format
Based on: https://dlthub.com/docs/dlt-ecosystem/destinations/iceberg
"""

import dlt
from dlt.sources.sql_database import sql_database, sql_table

# MySQL connection string
MYSQL_CONNECTION_STRING = "mysql+pymysql://root:rootpw@mysql:3306/appdb"


@dlt.resource(
    table_format="iceberg",  # Set Iceberg table format at resource level
    write_disposition="merge",
    primary_key="id"
)
def products_resource():
    """Load products table from MySQL"""
    # Configure SQL database source for products table
    source = sql_database(
        credentials=MYSQL_CONNECTION_STRING,
        schema="appdb",
        table_names=["products"]
    )
    yield from source.with_resources("products")


@dlt.resource(
    table_format="iceberg",  # Set Iceberg table format at resource level
    write_disposition="merge",
    primary_key="id"
)
def sales_resource():
    """Load sales table from MySQL"""
    # Configure SQL database source for sales table
    source = sql_database(
        credentials=MYSQL_CONNECTION_STRING,
        schema="appdb",
        table_names=["sales"]
    )
    yield from source.with_resources("sales")


@dlt.source
def mysql_source():
    """DLT source combining products and sales"""
    return products_resource, sales_resource


def main():
    """Main pipeline execution"""
    print("=" * 60)
    print("DLT Pipeline: MySQL to Iceberg (MinIO)")
    print("=" * 60)
    print()

    # Create pipeline with filesystem destination (S3-compatible MinIO)
    pipeline = dlt.pipeline(
        pipeline_name="mysql_to_iceberg",
        destination="filesystem",
        dataset_name="warehouse",
    )

    print("Loading data from MySQL to Iceberg/MinIO...")
    print("  - Products table")
    print("  - Sales table")
    print()

    # Run the pipeline with Iceberg table format
    # Note: table_format is set at resource level via @dlt.resource decorator
    load_info = pipeline.run(mysql_source())

    print("=" * 60)
    print("✓ Pipeline completed successfully!")
    print("=" * 60)
    print()
    print("Load info:")
    for package in load_info.load_packages:
        print(f"  Load ID: {package.load_id}")
        print(f"  Tables updated: {len(package.schema_update)}")
        for table_name in package.schema_update.keys():
            print(f"  ✓ {table_name}")
    print()
    print("Data location: s3://dlt-warehouse/")
    print("Table format: Apache Iceberg")
    print("File format: Parquet")
    print("Catalog: SQLite (ephemeral)")


if __name__ == "__main__":
    main()
