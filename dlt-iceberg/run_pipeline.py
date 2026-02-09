#!/usr/bin/env python3
"""
MySQL to MinIO Pipeline using DLT
Loads data from MySQL to MinIO S3 in Parquet format
"""

import dlt
import os
import pymysql

# Configure S3 filesystem destination
os.environ['DESTINATION__FILESYSTEM__BUCKET_URL'] = 's3://dlt-warehouse'
os.environ['DESTINATION__FILESYSTEM__CREDENTIALS__AWS_ACCESS_KEY_ID'] = 'minio'
os.environ['DESTINATION__FILESYSTEM__CREDENTIALS__AWS_SECRET_ACCESS_KEY'] = 'minio123'
os.environ['DESTINATION__FILESYSTEM__CREDENTIALS__ENDPOINT_URL'] = 'http://minio:9000'
os.environ['DESTINATION__FILESYSTEM__CREDENTIALS__REGION_NAME'] = 'us-east-1'

@dlt.source(
    name="mysql_source",
    max_table_nesting=0
)
def mysql_source():
    @dlt.resource(
        name="products",
        write_disposition="replace",
        primary_key="id"
    )
    def products_resource():
        conn = pymysql.connect(
            host='mysql-source',
            user='root',
            password='rootpw',
            database='appdb'
        )
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        cursor.execute("SELECT * FROM products")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        yield rows

    @dlt.resource(
        name="sales",
        write_disposition="replace",
        primary_key="id"
    )
    def sales_resource():
        conn = pymysql.connect(
            host='mysql-source',
            user='root',
            password='rootpw',
            database='appdb'
        )
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        cursor.execute("SELECT * FROM sales")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        yield rows

    return products_resource, sales_resource

def main():
    print("🚀 Starting MySQL to MinIO Pipeline...")

    # Create pipeline to filesystem destination
    pipeline = dlt.pipeline(
        pipeline_name="mysql_to_minio",
        destination='filesystem',
        dataset_name="warehouse"
    )

    # Run pipeline
    print("📦 Loading data from MySQL to MinIO...")
    load_info = pipeline.run(mysql_source())

    print("✅ Pipeline completed!")
    print(f"📊 Load info: {load_info}")
    print(f"📦 Data stored in: s3://dlt-warehouse/")
    print(f"   MinIO Console: http://localhost:9001")

    return load_info

if __name__ == "__main__":
    main()
