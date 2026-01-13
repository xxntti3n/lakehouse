"""
Initialize PostgreSQL replication for DLT-Iceberg pipeline
Creates replication slot and publication for CDC
"""

import os
import sys

# Add parent directory to path to import dlt
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from dlt.sources.pg_replication import init_replication

    # PostgreSQL connection
    credentials = "postgresql://replication_user:replication123@localhost:5432/dlt_data"

    print("Initializing PostgreSQL replication...")
    print(f"Slot: dlt_replication_slot")
    print(f"Publication: dlt_publication")
    print(f"Database: dlt_data")
    print("")

    # Initialize replication
    init_replication(
        slot_name="dlt_replication_slot",
        pub_name="dlt_publication",
        credentials=credentials,
        schema_name="public",
        table_names=None,  # All tables in schema
        reset=True,  # Drop and recreate if exists
        persist_snapshots=False,  # CDC only, no initial snapshot
    )

    print("")
    print("✓ Replication initialized successfully!")
    print("")
    print("You can now run the pipeline with:")
    print("  cd /Users/tien.nguyen6/Desktop/Cake/nttien/lakehouse/dlt-iceberg")
    print("  source .venv/bin/activate")
    print("  cd pipeline")
    print("  python pg_to_iceberg_pipeline.py")

except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
