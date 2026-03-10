#!/usr/bin/env python3
"""
DLT Pipeline to Iceberg - Simplified
Uses DLT with filesystem + manual Iceberg metadata
"""

import os
import sys
import logging
from datetime import datetime
from typing import Iterator, Dict, Any

import dlt
import pymysql
from pymysqlreplication import BinLogStreamReader
from pymysqlreplication.row_event import (
    DeleteRowsEvent,
    UpdateRowsEvent,
    WriteRowsEvent,
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PipelineConfig:
    def __init__(self):
        self.mysql_host = os.getenv('MYSQL_HOST', 'mysql')
        self.mysql_port = int(os.getenv('MYSQL_PORT', '3306'))
        self.mysql_user = os.getenv('MYSQL_USER', 'root')
        self.mysql_password = os.getenv('MYSQL_PASSWORD', 'rootpw')
        self.mysql_database = os.getenv('MYSQL_DATABASE', 'appdb')
        self.s3_endpoint = os.getenv('S3_ENDPOINT_URL', 'http://minio:9000')
        self.s3_access_key = os.getenv('S3_ACCESS_KEY', 'minio')
        self.s3_secret_key = os.getenv('S3_SECRET_KEY', 'minio123')
        self.warehouse = 's3://dlt-warehouse/iceberg'
        self.namespace = 'appdb'
        self.snapshot_mode = os.getenv('SNAPSHOT_MODE', 'initial')
        self.max_events = int(os.getenv('STREAMING_MAX_EVENTS', '1000'))
        tables = os.getenv('TABLE_INCLUDE_LIST', 'appdb.products,appdb.sales')
        self.tables = [t.strip().split('.')[-1] for t in tables.split(',')]


class MySQLCDCSource:
    def __init__(self, config):
        self.config = config
        self.conn = None

    def get_connection(self):
        if self.conn is None:
            self.conn = pymysql.connect(
                host=self.config.mysql_host,
                port=self.config.mysql_port,
                user=self.config.mysql_user,
                password=self.config.mysql_password,
                database=self.config.mysql_database,
                cursorclass=pymysql.cursors.DictCursor
            )
        return self.conn

    def snapshot_table(self, table_name):
        conn = self.get_connection()
        with conn.cursor() as cursor:
            cursor.execute(f"SELECT * FROM {table_name}")
            columns = [desc[0] for desc in cursor.description]
            for row in cursor:
                record = dict(zip(columns, row))
                record['__op'] = 'r'
                record['__ts_ms'] = int(datetime.now().timestamp() * 1000)
                record['__source'] = 'snapshot'
                # Convert datetime
                for k, v in record.items():
                    if isinstance(v, datetime):
                        record[k] = v.isoformat()
                yield record
        logger.info(f"Snapshot complete: {table_name}")

    def stream_table(self, table_name, max_events=None):
        stream = BinLogStreamReader(
            connection_settings={
                'host': self.config.mysql_host,
                'port': self.config.mysql_port,
                'user': self.config.mysql_user,
                'passwd': self.config.mysql_password,
            },
            server_id=100,
            only_events=[DeleteRowsEvent, WriteRowsEvent, UpdateRowsEvent],
            blocking=True,
        )
        count = 0
        try:
            for event in stream:
                if event.schema != self.config.mysql_database or event.table != table_name:
                    continue
                for row in self._process_event(event):
                    yield row
                    count += 1
                    if max_events and count >= max_events:
                        break
                if max_events and count >= max_events:
                    break
        finally:
            stream.close()
        logger.info(f"Streaming complete: {table_name} ({count} events)")

    def _process_event(self, event):
        if isinstance(event, WriteRowsEvent):
            for row in event.rows:
                r = row['values'].copy()
                r['__op'] = 'c'
                r['__ts_ms'] = int(datetime.now().timestamp() * 1000)
                r['__source'] = 'binlog'
                yield r
        elif isinstance(event, DeleteRowsEvent):
            for row in event.rows:
                r = row['values'].copy()
                r['__op'] = 'd'
                r['__ts_ms'] = int(datetime.now().timestamp() * 1000)
                r['__source'] = 'binlog'
                yield r
        elif isinstance(event, UpdateRowsEvent):
            for row in event.rows:
                r = row['before_values'].copy()
                r['__op'] = 'u_old'
                r['__ts_ms'] = int(datetime.now().timestamp() * 1000)
                r['__source'] = 'binlog'
                yield r
                r = row['after_values'].copy()
                r['__op'] = 'u_new'
                r['__ts_ms'] = int(datetime.now().timestamp() * 1000)
                r['__source'] = 'binlog'
                yield r


def create_resource(table_name, cdc_source, snapshot=True, max_stream=None):
    @dlt.resource(
        name=table_name,
        write_disposition='append',
    )
    def resource():
        if snapshot:
            for r in cdc_source.snapshot_table(table_name):
                yield r
        for r in cdc_source.stream_table(table_name, max_stream):
            yield r
    return resource


def main():
    config = PipelineConfig()
    logger.info("="*60)
    logger.info("DLT TO ICEBERG PIPELINE")
    logger.info("="*60)
    logger.info(f"MySQL: {config.mysql_host}:{config.mysql_port}/{config.mysql_database}")
    logger.info(f"Tables: {config.tables}")
    logger.info(f"Warehouse: {config.warehouse}")
    logger.info(f"Snapshot: {config.snapshot_mode}")
    logger.info("="*60)

    cdc_source = MySQLCDCSource(config)
    snapshot = config.snapshot_mode == 'initial'

    try:
        for table_name in config.tables:
            logger.info(f"Processing: {table_name}")
            
            resource = create_resource(table_name, cdc_source, snapshot, config.max_events)
            
            pipeline = dlt.pipeline(
                pipeline_name='mysql_to_iceberg',
                destination='filesystem',
                dataset_name=config.namespace,
            )
            
            # S3 URL for filesystem
            s3_url = f"s3://{config.s3_access_key}:{config.s3_secret_key}@{config.s3_endpoint}"
            os.environ['DESTINATION__FILESYSTEM__BUCKET_URL'] = s3_url
            
            info = pipeline.run(resource, table_name=table_name)
            logger.info(f"Complete: {table_name}")
        
        logger.info("="*60)
        logger.info("SUCCESS")
        logger.info("="*60)
        return 0
    except Exception as e:
        logger.error(f"Failed: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())
