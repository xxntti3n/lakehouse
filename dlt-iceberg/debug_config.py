"""
Debug script to verify DLT configuration for PyIceberg
"""
import os
os.environ['AWS_ACCESS_KEY_ID'] = 'minio'
os.environ['AWS_SECRET_ACCESS_KEY'] = 'minio123'
os.environ['AWS_ENDPOINT_URL'] = 'http://minio:9000'
os.environ['AWS_REGION'] = 'us-east-1'
os.environ['AWS_S3_ALLOW_HTTP'] = 'true'
os.environ['AWS_S3_ADDRESSING_STYLE'] = 'path'

# Import DLT's AwsCredentials
from dlt.common.configuration.specs.aws_credentials import AwsCredentials

# Create credentials object
creds = AwsCredentials()
creds.aws_access_key_id = 'minio'
creds.aws_secret_access_key = 'minio123'
creds.region_name = 'us-east-1'
creds.endpoint_url = 'http://minio:9000'

print("=" * 60)
print("Testing AwsCredentials.to_pyiceberg_fileio_config()")
print("=" * 60)

# Get the PyIceberg FileIO configuration
config = creds.to_pyiceberg_fileio_config()

print("\nGenerated configuration:")
for key, value in sorted(config.items()):
    print(f"  {key}: {value}")

print("\n" + "=" * 60)
print("Expected configuration for PyIceberg:")
print("=" * 60)
expected = {
    "s3.access-key-id": "minio",
    "s3.secret-access-key": "minio123",
    "s3.region": "us-east-1",
    "s3.endpoint": "minio:9000",  # Without http:// prefix
    "s3.scheme": "http",  # Added this
    "s3.path-style-access": "true",  # Added this
    "s3.connect-timeout": 300,
}
for key, value in sorted(expected.items()):
    print(f"  {key}: {value}")
