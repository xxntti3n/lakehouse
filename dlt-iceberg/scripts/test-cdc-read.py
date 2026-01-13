"""
Simple test to read from PostgreSQL replication slot
"""

import sys
sys.path.insert(0, '/Users/tien.nguyen6/Desktop/Cake/nttien/lakehouse/dlt-iceberg/pipeline')

from pg_replication import replication_resource
import dlt

# Create a simple pipeline to read from replication slot
pipeline = dlt.pipeline(
    pipeline_name="test_cdc_pipeline",
    destination='filesystem',
    dataset_name="test_cdc",
    config={
        "filesystem_path": "s3://iceberg-data/test",
        "s3_endpoint_url": "http://localhost:9000",
        "s3_access_key_id": "minioadmin",
        "s3_secret_access_key": "minioadmin123",
        "s3_region": "us-east-1",
        "s3_allow_http": True,
    }
)

# Create replication resource
changes = replication_resource(
    slot_name="dlt_replication_slot",
    pub_name="dlt_publication",
    credentials="postgresql://replication_user:replication123@localhost:5432/dlt_data",
    target_batch_size=10,
    flush_slot=False,  # Don't flush for testing
)

print("Reading from replication slot...")
print("This will capture pending changes in the WAL log.")
print("")

try:
    # Run the pipeline to capture changes
    info = pipeline.run(changes, write_disposition="append")
    print(f"\nPipeline run completed: {info}")
    print(f"\nLoaded {info.loads_count} packages")
    if info.first_load_package:
        print(f"First package: {info.first_load_package}")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
