"""
DLT Pipeline: PostgreSQL Replication to Iceberg (MinIO)
Reads from PostgreSQL replication slot and writes to Iceberg table format with metadata enrichment.
"""

import os
from datetime import datetime, timezone
from typing import Dict, Any

import dlt
from pg_replication import replication_resource
from pg_replication.helpers import init_replication

# Configuration from environment variables
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_DB = os.getenv("POSTGRES_DB", "dlt_data")
POSTGRES_USER = os.getenv("POSTGRES_USER", "replication_user")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "replication123")

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "http://localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin123")
ICEBERG_BUCKET = os.getenv("ICEBERG_BUCKET", "iceberg-data")

SLOT_NAME = os.getenv("SLOT_NAME", "dlt_replication_slot")
PUB_NAME = os.getenv("PUB_NAME", "dlt_publication")

# Construct PostgreSQL connection string
PG_CREDENTIALS = (
    f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}"
    f"@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
)


@dlt.resource(
    table_format="iceberg",
    columns={
        # Partition by extraction timestamp
        "extracted_at": {"partition": True},
        "deleted_at": {"data_type": "timestamp"}
    }
)
def enrich_with_metadata(items):
    """
    Add metadata fields to each record.

    Adds:
    - extracted_at: Timestamp when record was extracted from PostgreSQL
    - deleted_at: Timestamp for soft deletes (None for active records)
    """
    current_time = datetime.now(timezone.utc).isoformat()

    for item in items:
        # Extract change type from metadata if available
        change_type = item.get("_change_type", "insert")

        enriched = {
            **item,
            "extracted_at": current_time,
            "deleted_at": current_time if change_type == "delete" else None,
            "pipeline_run_id": current_time,  # Track this run
        }

        yield enriched


def initialize_replication_slot():
    """
    Initialize PostgreSQL replication slot and publication.
    """
    print(
        f"Initializing replication slot: {SLOT_NAME}, publication: {PUB_NAME}")

    try:
        init_replication(
            slot_name=SLOT_NAME,
            pub_name=PUB_NAME,
            credentials=PG_CREDENTIALS,
            schema_name="public",
            table_names=["users", "orders"],  # Specific tables
            reset=False,  # Don't reset if slot already exists
            persist_snapshots=False,  # We only want CDC, not initial snapshot
        )
        print("Replication initialized successfully")
    except Exception as e:
        print(f"Replication slot may already exist: {e}")
        print("Continuing with existing slot...")


def run_replication_pipeline():
    """
    Main pipeline execution function.

    1. Initializes PostgreSQL replication
    2. Creates replication resource
    3. Enriches data with metadata
    4. Writes to Iceberg table format (Parquet + metadata in MinIO/S3)
    """
    print("=" * 60)
    print("PostgreSQL to Iceberg CDC Pipeline")
    print("=" * 60)
    print(f"PostgreSQL: {POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}")
    print(f"Destination: {MINIO_ENDPOINT}/{ICEBERG_BUCKET}")
    print(f"Table Format: Iceberg (Parquet + metadata)")
    print(f"Partitioning: extracted_at (timestamp)")
    print("")

    # Step 1: Initialize replication slot
    initialize_replication_slot()

    # Step 2: Create pipeline with filesystem destination
    # Note: Iceberg is a table format, still uses filesystem destination
    pipeline = dlt.pipeline(
        pipeline_name="pg_to_iceberg_cdc",
        destination="filesystem",
        dataset_name="cdc_iceberg",
    )

    # Step 3: Create replication resource
    print("Creating replication resource...")
    replication = replication_resource(
        slot_name=SLOT_NAME,
        pub_name=PUB_NAME,
        credentials=PG_CREDENTIALS,
        target_batch_size=100,
        flush_slot=True,  # Remove processed messages from slot
    )

    # Step 4: Add metadata transformation and run
    print("Starting replication pipeline...")
    print("Listening for changes in PostgreSQL...")
    print("(Press Ctrl+C to stop)")
    print("-" * 60)

    # Apply transformation to the resource (already has @dlt.resource decorator with table_format)
    enriched_replication = enrich_with_metadata(replication)

    # Run pipeline - table_format is set in the @dlt.resource decorator
    info = pipeline.run(
        enriched_replication,
        write_disposition="append",
    )

    print("")
    print("=" * 60)
    print("Pipeline run completed!")
    print(f"Load info: {info}")
    print("=" * 60)


if __name__ == "__main__":
    # Set up logging
    import logging

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    try:
        # Run the pipeline
        run_replication_pipeline()
    except KeyboardInterrupt:
        print("\nPipeline stopped by user")
    except Exception as e:
        print(f"\nPipeline failed: {e}")
        import traceback
        traceback.print_exc()
