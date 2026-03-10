#!/usr/bin/env python3
"""
Configure Nessie warehouse and register Iceberg tables
This script configures the warehouse in Nessie and registers DLT Iceberg tables
"""

import os
import sys
import logging
import json
import requests

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def configure_nessie_warehouse(
    nessie_api_uri: str = "http://nessie:19120/api/v2",
    warehouse_location: str = "s3://dlt-warehouse",
    s3_endpoint: str = "http://minio:9000",
    access_key: str = "minio",
    secret_key: str = "minio123"
):
    """
    Configure warehouse in Nessie via REST API

    Nessie needs to know about the warehouse location before tables can be registered.
    """
    try:
        # Get current Nessie config
        config_url = f"{nessie_api_uri}/config"
        resp = requests.get(config_url, timeout=30)

        if resp.status_code == 200:
            logger.info(f"✅ Nessie is accessible at {nessie_api_uri}")
        else:
            logger.error(f"❌ Nessie returned {resp.status_code}")
            return False

        # Note: In Nessie, warehouses are implicitly created when the first table is created
        # We don't need to explicitly create a warehouse - just create namespaces and tables
        logger.info(f"ℹ️  Warehouse location: {warehouse_location}")
        logger.info(f"ℹ️  Tables will be registered under this warehouse")

        return True

    except Exception as e:
        logger.error(f"Failed to configure Nessie: {e}")
        return False


def register_table_with_nessie(
    table_name: str,
    namespace: str,
    metadata_location: str,
    nessie_api_uri: str = "http://nessie:19120/api/v2",
    ref: str = "main"
):
    """
    Register an Iceberg table with Nessie catalog

    This creates a table reference in Nessie pointing to existing Iceberg metadata
    """
    try:
        # First, ensure namespace exists
        namespace_url = f"{nessie_api_uri}/namespaces/{namespace}"
        create_namespace_url = f"{nessie_api_uri}/namespaces"

        # Check if namespace exists
        resp = requests.get(namespace_url, params={"ref": ref}, timeout=30)

        if resp.status_code == 404:
            # Create namespace
            logger.info(f"Creating namespace: {namespace}")
            create_resp = requests.post(
                create_namespace_url,
                params={"ref": ref},
                json={"name": [namespace]},
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            if create_resp.status_code in (200, 201):
                logger.info(f"✅ Created namespace: {namespace}")
            else:
                logger.warning(f"Could not create namespace: {create_resp.text}")
        elif resp.status_code == 200:
            logger.info(f"ℹ️  Namespace exists: {namespace}")

        # Now register the table using Nessie's Iceberg REST API
        # The table endpoint follows Iceberg REST spec
        iceberg_base = nessie_api_uri.replace('/api/v2', '/iceberg/v1')
        table_url = f"{iceberg_base}/namespaces/{namespace}/tables"

        # Create table request with metadata location
        payload = {
            "name": table_name,
            "location": metadata_location,
            "properties": {
                "metadata_location": metadata_location
            }
        }

        logger.info(f"Registering table: {namespace}.{table_name}")
        logger.info(f"  Metadata: {metadata_location}")

        # Try to create table reference
        create_resp = requests.post(
            table_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )

        if create_resp.status_code in (200, 201):
            logger.info(f"✅ Registered table: {namespace}.{table_name}")
            return True
        elif create_resp.status_code == 409:
            logger.info(f"ℹ️  Table already exists: {namespace}.{table_name}")
            return True
        else:
            logger.warning(f"Failed to register table: {create_resp.status_code} - {create_resp.text}")

            # Try alternative approach: Use PUT with table identifier
            # Some Nessie versions use different endpoints
            put_url = f"{iceberg_base}/namespaces/{namespace}/tables/{table_name}"
            put_resp = requests.put(
                put_url,
                json={"metadataLocation": metadata_location},
                headers={"Content-Type": "application/json"},
                timeout=30
            )

            if put_resp.status_code in (200, 201):
                logger.info(f"✅ Registered table (PUT): {namespace}.{table_name}")
                return True

        return False

    except Exception as e:
        logger.error(f"Failed to register table: {e}")
        return False


def find_latest_metadata(
    dataset_name: str = "debezium_cdc",
    table_name: str = "cdc_events",
    s3_endpoint: str = "http://minio:9000"
) -> str:
    """Find the latest metadata.json file for a DLT table"""
    try:
        # Use MinIO API to list metadata files
        # s3://dlt-warehouse/debezium_cdc/cdc_events/metadata/
        list_url = f"{s3_endpoint}/dlt-warehouse/{dataset_name}/{table_name}/metadata/?list-type=2"

        resp = requests.get(list_url, timeout=30)

        if resp.status_code != 200:
            logger.warning(f"Could not list metadata files: {resp.status_code}")
            return f"s3://dlt-warehouse/{dataset_name}/{table_name}/metadata/v1.metadata.json"

        # Parse XML response to find .metadata.json files
        import xml.etree.ElementTree as ET
        root = ET.fromstring(resp.text)

        metadata_files = []
        for contents in root.findall('.//Contents'):
            key = contents.find('Key')
            if key is not None and key.text.endswith('.metadata.json'):
                metadata_files.append(key.text)

        if metadata_files:
            # Sort by version number (v1, v2, etc.)
            metadata_files.sort(key=lambda x: int(x.split('/')[-1].replace('v', '').replace('.metadata.json', '')), reverse=True)
            latest = metadata_files[0]
            return f"s3://dlt-warehouse/{latest}"

        return f"s3://dlt-warehouse/{dataset_name}/{table_name}/metadata/v1.metadata.json"

    except Exception as e:
        logger.warning(f"Error finding metadata: {e}")
        return f"s3://dlt-warehouse/{dataset_name}/{table_name}/metadata/v1.metadata.json"


def list_nessie_tables(
    namespace: str,
    nessie_api_uri: str = "http://nessie:19120/api/v2"
):
    """List all tables in a Nessie namespace"""
    try:
        iceberg_base = nessie_api_uri.replace('/api/v2', '/iceberg/v1')
        url = f"{iceberg_base}/namespaces/{namespace}/tables"

        resp = requests.get(url, timeout=30)

        if resp.status_code == 200:
            data = resp.json()
            tables = data.get('identifiers', [])
            return tables
        else:
            logger.warning(f"Could not list tables: {resp.status_code}")
            return []

    except Exception as e:
        logger.error(f"Failed to list tables: {e}")
        return []


def main():
    """Main entry point"""
    logger.info("=" * 60)
    logger.info("NESSIE WAREHOUSE CONFIGURATION AND TABLE REGISTRATION")
    logger.info("=" * 60)

    # Configuration from environment
    nessie_api = os.getenv('NESSIE_URI', 'http://nessie:19120/api/v2')
    warehouse = os.getenv('ICEBERG_WAREHOUSE', 's3://dlt-warehouse/iceberg')
    s3_endpoint = os.getenv('S3_ENDPOINT_URL', 'http://minio:9000')
    access_key = os.getenv('S3_ACCESS_KEY', 'minio')
    secret_key = os.getenv('S3_SECRET_KEY', 'minio123')
    dataset_name = os.getenv('DATASET_NAME', 'debezium_cdc')
    namespace = dataset_name  # Use dataset name as namespace

    logger.info(f"Nessie API: {nessie_api}")
    logger.info(f"Warehouse: {warehouse}")
    logger.info(f"Dataset: {dataset_name}")
    logger.info("")

    # Step 1: Configure Nessie warehouse
    logger.info("Step 1: Configuring Nessie warehouse...")
    if not configure_nessie_warehouse(nessie_api, warehouse, s3_endpoint, access_key, secret_key):
        logger.error("Failed to configure Nessie warehouse")
        return 1

    # Step 2: Find latest metadata
    logger.info("\nStep 2: Finding latest Iceberg metadata...")
    metadata_location = find_latest_metadata(dataset_name, "cdc_events", s3_endpoint)
    logger.info(f"  Latest metadata: {metadata_location}")

    # Step 3: Register table
    logger.info("\nStep 3: Registering table with Nessie...")
    success = register_table_with_nessie(
        table_name="cdc_events",
        namespace=namespace,
        metadata_location=metadata_location,
        nessie_api_uri=nessie_api
    )

    if success:
        logger.info("\n" + "=" * 60)
        logger.info("✅ SUCCESS")
        logger.info("=" * 60)

        # List registered tables
        tables = list_nessie_tables(namespace, nessie_api)
        logger.info(f"\nRegistered tables in '{namespace}':")
        for t in tables:
            logger.info(f"  - {t}")

        return 0
    else:
        logger.error("\n" + "=" * 60)
        logger.info("❌ FAILED to register table")
        logger.info("=" * 60)
        logger.info("\nNote: Tables are still in Iceberg format at:")
        logger.info(f"  {warehouse.replace('/iceberg', '')}/{dataset_name}/")
        return 1


if __name__ == "__main__":
    sys.exit(main())
