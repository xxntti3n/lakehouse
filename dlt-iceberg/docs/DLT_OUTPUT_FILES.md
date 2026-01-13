# DLT Output Files - What Gets Created When DLT Runs Successfully

When DLT runs a pipeline successfully, it creates several types of files in different locations. Here's a complete breakdown:

## 📁 File Structure Overview

```
your-project/
├── .dlt/                              # DLT configuration and state
│   ├── config.toml                    # Pipeline configuration
│   ├── secrets.toml                   # Encrypted secrets
│   ├── .sources                       # Verified sources metadata
│   └── pipelines/                     # Pipeline state (created after first run)
│       └── <pipeline_name>/           # Per-pipeline directory
│           ├── state/                 # Pipeline state files
│           │   ├── pipeline_state.json      # Overall pipeline state
│           │   └── load_ids/               # History of load IDs
│           ├── dataset_state/         # Destination dataset state
│           │   └── <dataset_name>/         # Per-dataset state
│           │       └── <table_name>.json   # Table version info
│           └── locks/                 # Pipeline locks (prevent concurrent runs)
│
└── data/                              # Default local working directory
    └── <pipeline_name>/               # Pipeline-specific data
        ├── extract/                   # Extracted data (before normalization)
        ├── normalize/                 # Normalized data (Arrow tables)
        └── load/                      # Loaded data packages
```

## 🗄️ Destination Files (MinIO/S3)

When using the filesystem destination with Iceberg format:

```
s3://iceberg-data/                     # Your bucket
└── iceberg_lakehouse/                 # Dataset name
    └── <table_name>/                  # e.g., users, orders
        ├── metadata/                  # Iceberg metadata
        │   ├── 00000-<uuid>.metadata.json   # Table schema
        │   ├── snap-<uuid>.avro              # Snapshot manifests
        │   └── ...                          # More metadata files
        └── data/                     # Actual data files
            ├── <partition_key>=<value>/    # Partitioned data
            │   └── part-00000-<uuid>.parquet  # Parquet files
            └── ...
```

## 📄 Key File Types Explained

### 1. **Pipeline State Files** (`pipeline_state.json`)

**Location**: `.dlt/pipelines/<pipeline_name>/state/pipeline_state.json`

**Purpose**: Tracks overall pipeline execution state

**Content**:
```json
{
  "pipeline_name": "pg_to_iceberg_cdc",
  "created_at": 1705087200.123,
  "last_run": 1705087265.456,
  "state_version": "1.0.0",
  "started_at": 1705087200.123,
  "finished_at": 1705087265.456
}
```

### 2. **Dataset State Files** (`<table_name>.json`)

**Location**: `.dlt/pipelines/<pipeline_name>/dataset_state/<dataset_name>/<table_name>.json`

**Purpose**: Tracks each table's state for incremental loading

**Content**:
```json
{
  "version": 4,
  "hex_version": "4",
  "schema_hash": "abc123...",
  "schema_name": "users",
  "table_name": "users",
  "write_disposition": "merge",
  "columns": {
    "id": {"name": "id", "data_type": "bigint", "nullable": false},
    "username": {"name": "username", "data_type": "text", "nullable": false},
    ...
  }
}
```

### 3. **Load Packages**

**Location**: In destination (MinIO) or local working directory

**Purpose**: Actual data files produced by the pipeline

**Structure**:
```
<load_id>/                           # Unique load ID (e.g., 1705087200123)
├── <table_name>/                    # Each table gets its own folder
│   ├── <table_name>_0.jsonl         # Data in JSONL format (line-delimited JSON)
│   ├── <table_name>_1.jsonl         # Multiple files for large datasets
│   └── <table_name>_2.jsonl
└── _metadata/
    └── <table_name>.jsonl           # Metadata about the load
```

**Example JSONL file content**:
```json
{"id": 1, "username": "john_doe", "email": "john@example.com", "extracted_at": "2025-01-12T10:30:45Z"}
{"id": 2, "username": "jane_smith", "email": "jane@example.com", "extracted_at": "2025-01-12T10:30:45Z"}
{"id": 3, "username": "bob_wilson", "email": "bob@example.com", "extracted_at": "2025-01-12T10:30:45Z"}
```

### 4. **Schema Files**

**Location**: Embedded in load packages

**Purpose**: Define table structure and evolution

**Content**:
```json
{
  "version": 4,
  "hex_version": "4",
  "name": "users",
  "columns": {
    "id": {
      "name": "id",
      "data_type": "bigint",
      "nullable": false,
      "primary_key": true,
      "unique": true,
      "sort": false
    },
    "username": {
      "name": "username",
      "data_type": "text",
      "nullable": false
    },
    "extracted_at": {
      "name": "extracted_at",
      "data_type": "timestamp",
      "nullable": false,
      "metadata": {
        "description": "Timestamp when record was extracted from source"
      }
    }
  }
}
```

### 5. **Trace Files** (Optional)

**Location**: `.dlt/pipelines/<pipeline_name>/traces/`

**Purpose**: Detailed execution traces for debugging

**Content**:
```json
{
  "step": "normalize",
  "status": "success",
  "started_at": 1705087200.123,
  "finished_at": 1705087205.456,
  "duration": 5.333,
  "rows_count": 150,
  "tables": ["users", "orders"]
}
```

## 🔍 How to Check DLT Run Success

### Method 1: Command Line

```bash
# Show pipeline state
dlt pipeline <pipeline_name> show

# Show detailed state
dlt pipeline <pipeline_name> state

# Show last trace
dlt pipeline <pipeline_name> trace
```

### Method 2: Check File Existence

```bash
# Check if pipeline state exists
ls -la .dlt/pipelines/<pipeline_name>/state/

# Check latest load
ls -lt .dlt/pipelines/<pipeline_name>/state/load_ids/ | head -5
```

### Method 3: Inspect State Files

```python
import dlt

# Load pipeline
pipeline = dlt.pipeline("<pipeline_name>")

# Check state
print(pipeline.state)
print(pipeline.last_trace)
print(pipeline.last_load_id)
```

## 📊 What to Look For in a Successful Run

### ✅ Indicators of Success:

1. **Pipeline state file created/updated**
   ```bash
   .dlt/pipelines/<pipeline_name>/state/pipeline_state.json exists
   ```

2. **No error in traces**
   - All steps show `"status": "success"`

3. **Data files created in destination**
   ```bash
   # In MinIO
   mc ls local/iceberg-data/iceberg_lakehouse/users/data/
   ```

4. **Load ID registered**
   ```bash
   .dlt/pipelines/<pipeline_name>/state/load_ids/<timestamp> exists
   ```

5. **Dataset state updated**
   ```bash
   .dlt/pipelines/<pipeline_name>/dataset_state/<dataset_name>/*.json updated
   ```

### ❌ Indicators of Failure:

1. **Error traces**
   ```json
   {
     "step": "load",
     "status": "failed",
     "exception": "ConnectionError: ..."
   }
   ```

2. **Incomplete loads**
   - Load ID folder exists but incomplete

3. **No data in destination**
   - MinIO bucket empty or missing expected files

4. **Stale state**
   - State files not updated despite pipeline run

## 🧪 Example: Inspect a Successful Run

```bash
# 1. Check if pipeline ran
dlt pipeline pg_to_iceberg_cdc show

# 2. View detailed state
dlt pipeline pg_to_iceberg_cdc state

# 3. Check destination files
docker exec dlt-minio mc ls -r local/iceberg-data/iceberg_lakehouse/

# 4. Inspect specific table data
python -c "
import dlt
pipeline = dlt.pipeline('pg_to_iceberg_cdc')
print('Last load ID:', pipeline.last_load_id)
print('Last trace:', pipeline.last_trace)
"
```

## 📝 Summary

When DLT runs successfully, it creates:

| File Type | Location | Purpose |
|-----------|----------|---------|
| **Pipeline State** | `.dlt/pipelines/<name>/state/` | Overall pipeline status |
| **Dataset State** | `.dlt/pipelines/<name>/dataset_state/` | Table schemas & versions |
| **Load Packages** | Destination (MinIO) | Actual data files |
| **Traces** | `.dlt/pipelines/<name>/traces/` | Execution details |
| **Locks** | `.dlt/pipelines/<name>/locks/` | Prevent concurrent runs |
| **Iceberg Metadata** | `s3://.../metadata/` | Iceberg table metadata |

All these files together ensure:
- ✅ Data integrity
- ✅ Incremental loading
- ✅ Schema evolution
- ✅ Reproducibility
- ✅ Debugging capability
