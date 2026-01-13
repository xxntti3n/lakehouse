#!/bin/bash

echo "=== PostgreSQL CDC Pipeline Test ==="
echo ""

cd /Users/tien.nguyen6/Desktop/Cake/nttien/lakehouse/dlt-iceberg/pipeline

echo "1. Starting pipeline in background..."
source .venv/bin/activate
python pg_to_iceberg_simple.py > /tmp/pipeline.log 2>&1 &
PIPELINE_PID=$!
echo "   Pipeline started (PID: $PIPELINE_PID)"
echo "   Logs: tail -f /tmp/pipeline.log"
echo ""

sleep 10

echo "2. Making test changes in PostgreSQL..."
docker exec dlt-postgres psql -U postgres -d dlt_data << 'EOSQL'
INSERT INTO users (username, email) VALUES ('test_cdc_1', 'cdc1@test.com') RETURNING id;
INSERT INTO users (username, email) VALUES ('test_cdc_2', 'cdc2@test.com') RETURNING id;
UPDATE users SET email = 'updated@test.com' WHERE username = 'test_cdc_1';
SELECT 'Changes made!' AS result;
EOSQL

echo ""
echo "3. Waiting for CDC capture (15 seconds)..."
sleep 15

echo ""
echo "4. Checking MinIO for captured data..."
docker exec dlt-minio mc ls -r local/iceberg-data/cdc/ 2>/dev/null | head -50

echo ""
echo "5. Showing recent pipeline logs..."
tail -30 /tmp/pipeline.log

echo ""
echo "=== Test Complete ==="
echo ""
echo "To stop the pipeline:"
echo "   kill $PIPELINE_PID"
echo ""
echo "To view logs:"
echo "   tail -f /tmp/pipeline.log"
