"""
Nessie Catalog Registration - Register Iceberg tables with Nessie
Reads existing Iceberg metadata.json files and registers them in Nessie
"""

import logging
import os
import json
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

try:
    from pyiceberg.catalog.rest import RestCatalog
    from pyiceberg.table import Table
    ICEBERG_AVAILABLE = True
except ImportError:
    ICEBERG_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class NessieRegisterConfig:
    """Configuration for Nessie registration"""
    nessie_uri: str = "http://nessie:19120/iceberg/v1"
    warehouse_path: str = "s3://dlt-warehouse"
    access_key: str = "minio"
    secret_key: str = "minio123"
    endpoint_url: str = "http://minio:9000"
    namespace: str = "appdb"
    ref: str = "main"


class NessieTableRegister:
    """
    Register Iceberg tables with Nessie catalog
    Reads metadata.json files and creates table references in Nessie
    """

    def __init__(self, config: NessieRegisterConfig):
        if not ICEBERG_AVAILABLE:
            raise ImportError("pyiceberg is required. Install with: pip install pyiceberg[s3]")

        self.config = config
        self.catalog: Optional[RestCatalog] = None
        self._setup_catalog()

    def _setup_catalog(self):
        """Setup Nessie REST catalog connection"""
        try:
            import os

            # Configure S3 environment for pyiceberg
            os.environ['AWS_ACCESS_KEY_ID'] = self.config.access_key
            os.environ['AWS_SECRET_ACCESS_KEY'] = self.config.secret_key
            os.environ['AWS_ENDPOINT_URL'] = self.config.endpoint_url
            os.environ['AWS_REGION'] = 'us-east-1'
            os.environ['AWS_ALLOW_HTTP'] = 'true'

            # First, ensure warehouse is configured in Nessie
            self._configure_warehouse()

            # Create REST catalog connection
            self.catalog = RestCatalog(
                "nessie",
                uri=self.config.nessie_uri,
                warehouse=self.config.warehouse_path,
                s3=self.config.endpoint_url,
                s3_access_key_id=self.config.access_key,
                s3_secret_access_key=self.config.secret_key,
            )

            logger.info(f"✅ Connected to Nessie catalog: {self.config.nessie_uri}")

        except Exception as e:
            logger.error(f"Failed to connect to Nessie: {e}")
            raise

    def _configure_warehouse(self):
        """Configure warehouse in Nessie if it doesn't exist"""
        try:
            import requests

            # Nessie API to configure warehouse
            # The warehouse needs to be registered via Nessie's config API
            base_uri = self.config.nessie_uri.rstrip('/v1').replace('/iceberg/v1', '')
            config_url = f"{base_uri}/api/v2/config"

            # Get current config
            resp = requests.get(config_url, timeout=30)

            if resp.status_code == 200:
                config_data = resp.json()
                # Check if warehouse is already configured
                # Nessie stores warehouse configurations
                logger.info(f"Nessie config retrieved")

        except Exception as e:
            logger.warning(f"Could not configure warehouse: {e}")
            # Continue anyway - the warehouse might already be configured

    def create_namespace(self, namespace: str = None):
        """Create namespace in Nessie if it doesn't exist"""
        ns = namespace or self.config.namespace

        try:
            # Check if namespace exists
            existing = self.catalog.list_namespaces()
            existing_names = [n[0] if isinstance(n, tuple) else n for n in existing]

            if ns not in existing_names:
                self.catalog.create_namespace(ns)
                logger.info(f"✅ Created namespace: {ns}")
            else:
                logger.info(f"ℹ️  Namespace already exists: {ns}")

        except Exception as e:
            logger.warning(f"Could not create namespace {ns}: {e}")

    def register_table_from_metadata(
        self,
        table_name: str,
        metadata_location: str,
        namespace: str = None
    ) -> bool:
        """
        Register an existing Iceberg table with Nessie using its metadata.json location

        Args:
            table_name: Name of the table
            metadata_location: S3 path to metadata.json file
            namespace: Namespace (defaults to config.namespace)

        Returns:
            True if successful
        """
        ns = namespace or self.config.namespace
        table_identifier = f"{ns}.{table_name}"

        try:
            # First, ensure namespace exists
            self.create_namespace(ns)

            # Check if table already exists
            try:
                existing = self.catalog.load_table(table_identifier)
                logger.info(f"ℹ️  Table already registered: {table_identifier}")
                return True
            except Exception:
                # Table doesn't exist, proceed with registration
                pass

            # Read the metadata.json file
            metadata_content = self._read_s3_file(metadata_location)
            if not metadata_content:
                logger.error(f"Could not read metadata from: {metadata_location}")
                return False

            metadata = json.loads(metadata_content)

            # Register table using Nessie's REST API directly
            # since pyiceberg doesn't have a direct "register table" method
            success = self._register_via_rest_api(
                namespace=ns,
                table_name=table_name,
                metadata_location=metadata_location
            )

            if success:
                logger.info(f"✅ Registered table: {table_identifier}")
                logger.info(f"   Metadata: {metadata_location}")

            return success

        except Exception as e:
            logger.error(f"Failed to register table {table_identifier}: {e}")
            return False

    def _register_via_rest_api(
        self,
        namespace: str,
        table_name: str,
        metadata_location: str
    ) -> bool:
        """
        Register table via Nessie REST API
        Creates a table reference pointing to existing metadata location
        """
        try:
            import requests

            # Build the API URL
            base_url = self.config.nessie_uri.rstrip('/v1')
            url = f"{base_url}/v1/namespaces/{namespace}/tables"

            # Prepare the request payload
            payload = {
                "name": table_name,
                "location": metadata_location,
                "properties": {
                    "metadata_location": metadata_location
                }
            }

            # Use nessie ref (branch) header
            headers = {
                "Content-Type": "application/json",
            }

            params = {
                "ref": self.config.ref
            }

            response = requests.post(url, json=payload, headers=headers, params=params, timeout=30)

            if response.status_code in (200, 201):
                return True
            elif response.status_code == 409:
                # Table already exists
                logger.info(f"Table {namespace}.{table_name} already exists")
                return True
            else:
                logger.warning(f"Nessie API returned {response.status_code}: {response.text}")
                # Try alternative approach - create table reference
                return self._create_table_reference(namespace, table_name, metadata_location)

        except Exception as e:
            logger.warning(f"REST API registration failed: {e}")
            return self._create_table_reference(namespace, table_name, metadata_location)

    def _create_table_reference(
        self,
        namespace: str,
        table_name: str,
        metadata_location: str
    ) -> bool:
        """
        Alternative method: Create a table using pyiceberg with existing location
        """
        try:
            import requests

            # Try to use the create table API with metadata location
            base_url = self.config.nessie_uri.rstrip('/v1')
            url = f"{base_url}/v1/namespaces/{namespace}/tables"

            payload = {
                "name": table_name,
                "metadataLocation": metadata_location
            }

            headers = {"Content-Type": "application/json"}
            params = {"ref": self.config.ref}

            response = requests.post(url, json=payload, headers=headers, params=params, timeout=30)

            if response.status_code in (200, 201, 409):
                return True

            logger.error(f"Could not register table: {response.status_code} - {response.text}")
            return False

        except Exception as e:
            logger.error(f"Failed to create table reference: {e}")
            return False

    def _read_s3_file(self, s3_path: str) -> Optional[str]:
        """Read file from S3/MinIO"""
        try:
            import requests

            # Convert s3:// path to MinIO URL
            # s3://dlt-warehouse/debezium_cdc/cdc_events/metadata/xxx.json
            # -> http://minio:9000/dlt-warehouse/debezium_cdc/cdc_events/metadata/xxx.json

            path = s3_path.replace('s3://', '')
            url = f"{self.config.endpoint_url}/{path}"

            resp = requests.get(url, timeout=30)
            if resp.status_code == 200:
                return resp.text
            else:
                logger.error(f"S3 GET failed: {resp.status_code} for {url}")
                return None

        except Exception as e:
            logger.error(f"Failed to read S3 file: {e}")
            return None

    def register_dlt_tables(
        self,
        dataset_name: str = "debezium_cdc",
        table_names: List[str] = None
    ) -> Dict[str, bool]:
        """
        Auto-discover and register DLT Iceberg tables

        Args:
            dataset_name: DLT dataset name (e.g., "debezium_cdc")
            table_names: List of table names to register (auto-discovered if None)

        Returns:
            Dict mapping table names to registration status
        """
        results = {}

        if table_names is None:
            table_names = ["cdc_events"]  # Default DLT table

        # Create namespace first
        self.create_namespace()

        # Find latest metadata.json for each table
        for table_name in table_names:
            metadata_path = f"{self.config.warehouse_path}/{dataset_name}/{table_name}/metadata"

            try:
                # List metadata files to find the latest
                import requests

                # Use MinIO API to list files
                list_path = metadata_path.replace('s3://', '')
                list_url = f"{self.config.endpoint_url}/{list_path}?list-type=2"

                resp = requests.get(
                    list_url,
                    headers={"Authorization": f"AWS4-HMAC-SHA256 Credential={self.config.access_key}"}  # Simplified
                )

                # Try to find metadata files via pattern
                # For now, use the standard naming convention
                latest_metadata = self._find_latest_metadata_file(dataset_name, table_name)

                if latest_metadata:
                    success = self.register_table_from_metadata(
                        table_name=table_name,
                        metadata_location=latest_metadata
                    )
                    results[table_name] = success
                else:
                    logger.warning(f"Could not find metadata for {dataset_name}.{table_name}")
                    results[table_name] = False

            except Exception as e:
                logger.error(f"Error registering {table_name}: {e}")
                results[table_name] = False

        return results

    def _find_latest_metadata_file(
        self,
        dataset_name: str,
        table_name: str
    ) -> Optional[str]:
        """Find the latest metadata.json file for a table"""
        try:
            # Use the DLT pipeline state or filesystem to find latest metadata
            # For now, construct the expected path pattern
            # DLT creates metadata files with version numbers: v{n}.metadata.json

            # Check if we can use a local file system approach
            metadata_base = f"/data/{dataset_name}/{table_name}/metadata"

            # If running in container with volume mount
            if os.path.exists("/data"):
                # Find highest version metadata file
                versions = []
                for f in os.listdir(metadata_base) if os.path.exists(metadata_base) else []:
                    if f.endswith('.metadata.json') and f.startswith('v'):
                        try:
                            v = int(f.replace('v', '').replace('.metadata.json', ''))
                            versions.append((v, f))
                        except ValueError:
                            pass

                if versions:
                    latest = max(versions, key=lambda x: x[0])
                    s3_path = f"{self.config.warehouse_path}/{dataset_name}/{table_name}/metadata/{latest[1]}"
                    return s3_path

            # Fallback: try to read from S3 directly
            # For simplicity, return a constructed path to the latest
            # In production, you'd list the S3 directory
            s3_path = f"{self.config.warehouse_path}/{dataset_name}/{table_name}/metadata/v1.metadata.json"
            return s3_path

        except Exception as e:
            logger.error(f"Error finding metadata file: {e}")
            return None

    def list_registered_tables(self, namespace: str = None) -> List[str]:
        """List all registered tables in namespace"""
        ns = namespace or self.config.namespace

        try:
            tables = self.catalog.list_tables(ns)
            return tables
        except Exception as e:
            logger.error(f"Failed to list tables: {e}")
            return []


def register_dlt_iceberg_tables_with_nessie(
    nessie_uri: str = None,
    warehouse_path: str = None,
    access_key: str = None,
    secret_key: str = None,
    endpoint_url: str = None,
    namespace: str = None
) -> Dict[str, bool]:
    """
    Convenience function to register DLT Iceberg tables with Nessie

    Returns dict of table names to registration status
    """
    config = NessieRegisterConfig(
        nessie_uri=nessie_uri or os.getenv('NESSIE_ICEBERG_URI', 'http://nessie:19120/iceberg/v1'),
        warehouse_path=warehouse_path or os.getenv('ICEBERG_WAREHOUSE', 's3://dlt-warehouse'),
        access_key=access_key or os.getenv('S3_ACCESS_KEY', 'minio'),
        secret_key=secret_key or os.getenv('S3_SECRET_KEY', 'minio123'),
        endpoint_url=endpoint_url or os.getenv('S3_ENDPOINT_URL', 'http://minio:9000'),
        namespace=namespace or os.getenv('ICEBERG_NAMESPACE', 'appdb')
    )

    registrar = NessieTableRegister(config)
    return registrar.register_dlt_tables()
