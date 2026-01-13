"""
Simple test script to initialize PostgreSQL replication for specific tables
"""

import sys
import os

# Add pipeline directory to path
sys.path.insert(0, '/Users/tien.nguyen6/Desktop/Cake/nttien/lakehouse/dlt-iceberg/pipeline')

from pg_replication.helpers import init_replication

# PostgreSQL connection - use postgres superuser
credentials = "postgresql://postgres:postgres123@localhost:5432/dlt_data"

print("Initializing PostgreSQL replication...")
print(f"Credentials: {credentials}")
print("")

try:
    init_replication(
        slot_name="dlt_replication_slot",
        pub_name="dlt_publication",
        credentials=credentials,
        schema_name="public",
        table_names=["users", "orders"],  # Specific tables
        reset=True,  # Drop and recreate if exists
        persist_snapshots=False,  # CDC only
    )
    print("✓ Replication initialized successfully!")
    print("")
    print("You can now run the pipeline to capture changes!")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
