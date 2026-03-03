"""
Streamlit UI for querying Iceberg tables with DuckDB
Lightweight web interface for data exploration
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
try:
    from duckdb_query import IcebergDuckDB, get_duckdb
except ImportError:
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from duckdb_query import IcebergDuckDB, get_duckdb
import os
import subprocess
import time
from datetime import datetime


# Page config
st.set_page_config(
    page_title="Iceberg Data Explorer",
    page_icon="🦆",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
    <style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        margin-bottom: 1rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
    }
    </style>
""", unsafe_allow_html=True)


def init_session_state():
    """Initialize session state variables"""
    if 'duckdb' not in st.session_state:
        st.session_state.duckdb = None
    if 'query_history' not in st.session_state:
        st.session_state.query_history = []
    if 'current_table' not in st.session_state:
        st.session_state.current_table = None
    if 'auto_refresh_logs' not in st.session_state:
        st.session_state.auto_refresh_logs = False


@st.cache_resource
def get_cached_duckdb():
    """Get cached DuckDB connection"""
    return IcebergDuckDB(
        minio_endpoint=os.getenv("S3_ENDPOINT_URL", "http://minio:9000"),
        access_key=os.getenv("S3_ACCESS_KEY", "minio"),
        secret_key=os.getenv("S3_SECRET_KEY", "minio123"),
        bucket=os.getenv("S3_BUCKET", "dlt-warehouse")
    )


def get_dlt_logs():
    """Get DLT pipeline logs from shared volume"""
    try:
        # Try reading from shared volume first
        log_file = '/logs/pipeline.log'
        if os.path.exists(log_file):
            with open(log_file, 'r') as f:
                # Read last 1000 lines
                lines = f.readlines()
                return ''.join(lines[-1000:]) if len(lines) > 1000 else ''.join(lines)
        else:
            return "No pipeline logs found. Waiting for pipeline to run..."
    except Exception as e:
        return f"Error reading logs from shared volume: {str(e)}"


def get_gtid_logs():
    """Get GTID logs from shared volume"""
    try:
        # Try reading from shared volume
        gtid_file = '/logs/dlt_gtid.log'
        if os.path.exists(gtid_file):
            with open(gtid_file, 'r') as f:
                # Read last 50 entries
                lines = f.readlines()
                return ''.join(lines[-50:]) if len(lines) > 50 else ''.join(lines)
        else:
            return "No GTID logs available yet. The pipeline needs to run at least once."
    except Exception as e:
        return f"Error reading GTID logs from shared volume: {str(e)}"


def get_mysql_gtid_status():
    """Get current MySQL GTID status"""
    try:
        # Use docker command if available, else return message
        result = subprocess.run(
            ['docker', 'exec', 'mysql-source', 'mysql', '-uroot', '-prootpw',
             '-e', "SHOW VARIABLES LIKE '%gtid%'; SHOW MASTER STATUS;"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            return result.stdout
        return "Docker command not available. GTID status monitoring requires Docker CLI access."
    except FileNotFoundError:
        return "Docker CLI not found in container. GTID status monitoring requires Docker CLI."
    except Exception as e:
        return f"Error getting GTID status: {str(e)}"


def display_metrics(stats):
    """Display table statistics as metrics"""
    if stats and 'error' not in stats:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric(label="📊 Row Count", value=f"{stats.get('row_count', 0):,}")
        with col2:
            st.metric(label="📋 Column Count", value=stats.get('column_count', 0))
        with col3:
            st.metric(label="📁 Table Name", value=stats.get('table_name', 'N/A'))


def display_table_info(db, table_name):
    """Display detailed table information"""
    st.subheader(f"📋 Table: `{table_name}`")

    # Get schema
    try:
        schema = db.get_table_schema(table_name)
        if schema:
            st.write("**Schema:**")
            schema_df = pd.DataFrame(schema)
            st.dataframe(schema_df, use_container_width=True, hide_index=True)
    except Exception as e:
        st.warning(f"Could not load schema: {e}")


def display_results(df, table_name):
    """Display query results with visualizations"""
    st.subheader(f"📊 Query Results ({len(df)} rows)")

    # Display data
    st.dataframe(df, use_container_width=True, hide_index=True)

    # Automatic visualizations
    if len(df) > 0:
        st.subheader("📈 Visualizations")

        # Numeric columns
        numeric_cols = df.select_dtypes(include=['number']).columns.tolist()

        if len(numeric_cols) > 0:
            col1, col2 = st.columns(2)

            with col1:
                st.write("**Distribution of Numeric Columns**")
                for col in numeric_cols[:3]:  # Limit to first 3
                    fig = px.histogram(df, x=col, nbins=20, title=f"Distribution of {col}")
                    st.plotly_chart(fig, use_container_width=True)

            with col2:
                if len(numeric_cols) >= 2:
                    st.write("**Correlation: First Two Numeric Columns**")
                    fig = px.scatter(df, x=numeric_cols[0], y=numeric_cols[1],
                                   title=f"{numeric_cols[0]} vs {numeric_cols[1]}")
                    st.plotly_chart(fig, use_container_width=True)

        # Categorical columns
        categorical_cols = df.select_dtypes(include=['object']).columns.tolist()

        if len(categorical_cols) > 0:
            st.write("**Value Counts (Top Categories)**")
            for col in categorical_cols[:2]:  # Limit to first 2
                value_counts = df[col].value_counts().head(10)
                fig = px.bar(x=value_counts.index, y=value_counts.values,
                            title=f"Top 10: {col}")
                st.plotly_chart(fig, use_container_width=True)


def main():
    """Main Streamlit app"""
    init_session_state()

    # Header
    st.markdown('<h1 class="main-header">🦆 Iceberg Data Explorer</h1>', unsafe_allow_html=True)
    st.markdown("Query and explore Iceberg tables stored in MinIO using DuckDB")

    # Sidebar
    with st.sidebar:
        st.header("⚙️ Configuration")

        # Connection info (display only, using env vars)
        st.info(f"""
        **MinIO Endpoint:** `{os.getenv("S3_ENDPOINT_URL", "http://minio:9000")}`
        **Bucket:** `{os.getenv("S3_BUCKET", "dlt-warehouse")}`
        """)

        st.divider()

        # Initialize connection
        if st.button("🔄 Connect to DuckDB", type="primary"):
            with st.spinner("Connecting..."):
                try:
                    st.session_state.duckdb = get_cached_duckdb()
                    st.success("✓ Connected to DuckDB!")
                except Exception as e:
                    st.error(f"Connection failed: {e}")

        st.divider()

        # Tables section
        if st.session_state.duckdb:
            st.subheader("📁 Available Tables")

            try:
                tables = st.session_state.duckdb.list_tables()

                if not tables:
                    st.warning("No tables found. Load data with DLT first.")
                else:
                    # Table selection
                    selected_table = st.selectbox("Select a table", tables, key='table_selector')

                    if selected_table:
                        st.session_state.current_table = selected_table

                        # Quick stats
                        try:
                            stats = st.session_state.duckdb.get_table_stats(selected_table)
                            st.json(stats)
                        except:
                            pass

            except Exception as e:
                st.error(f"Error loading tables: {e}")

    # Main content area
    if not st.session_state.duckdb:
        st.info("👈 Click 'Connect to DuckDB' in the sidebar to start")
        return

    # Table view mode
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "📊 Table View", "🔍 Custom Query", "📜 Query History",
        "📋 Pipeline Logs", "📍 GTID Status", "✅ Verification"
    ])

    with tab1:
        """View table data"""
        if st.session_state.current_table:
            table_name = st.session_state.current_table

            # Display stats
            try:
                stats = st.session_state.duckdb.get_table_stats(table_name)
                display_metrics(stats)
            except Exception as e:
                st.warning(f"Could not load stats: {e}")

            st.divider()

            # Display schema
            display_table_info(st.session_state.duckdb, table_name)

            st.divider()

            # Row limit selector
            col1, col2 = st.columns([1, 3])
            with col1:
                limit = st.slider("Rows to display", 10, 1000, 100, 10)
            with col2:
                st.write("")

            # Query table
            try:
                rows = st.session_state.duckdb.query_table(table_name, limit=limit)
                if rows:
                    df = pd.DataFrame(rows)
                    display_results(df, table_name)
                else:
                    st.warning("No data in table")
            except Exception as e:
                st.error(f"Error querying table: {e}")
        else:
            st.info("👈 Select a table from the sidebar")

    with tab2:
        """Custom SQL query"""
        st.subheader("🔍 Custom SQL Query")

        # Query editor
        bucket = os.getenv('S3_BUCKET', 'dlt-warehouse')
        default_query = f"-- CDC events (latest state per table)\nSELECT * FROM read_json_auto('s3://{bucket}/debezium_cdc/cdc_events/*.jsonl.gz', union_by_name=true)\nWHERE _table = 'products'\nORDER BY _ts DESC LIMIT 100"

        if st.session_state.current_table:
            default_query = f"SELECT * FROM read_json_auto('s3://{bucket}/debezium_cdc/cdc_events/*.jsonl.gz', union_by_name=true)\nWHERE _table = '{st.session_state.current_table}'\nORDER BY _ts DESC LIMIT 100"

        query = st.text_area("SQL Query", value=default_query, height=150)

        col1, col2 = st.columns(2)
        with col1:
            if st.button("▶️ Run Query", type="primary"):
                if query.strip():
                    try:
                        with st.spinner("Executing query..."):
                            df = st.session_state.duckdb.execute_sql(query, as_df=True)

                        if df is not None and len(df) > 0:
                            st.success(f"✓ Query returned {len(df)} rows")

                            # Add to history
                            st.session_state.query_history.append({
                                'query': query,
                                'rows': len(df),
                                'timestamp': pd.Timestamp.now()
                            })

                            # Display results
                            st.dataframe(df, use_container_width=True, hide_index=True)
                        else:
                            st.warning("Query returned no results")
                    except Exception as e:
                        st.error(f"Query failed: {e}")
        with col2:
            if st.button("🗑️ Clear"):
                st.rerun()

    with tab3:
        """Query history"""
        st.subheader("📜 Query History")

        if not st.session_state.query_history:
            st.info("No queries executed yet")
        else:
            for i, item in enumerate(reversed(st.session_state.query_history[-10:])):
                with st.expander(f"Query {len(st.session_state.query_history) - i} - {item['rows']} rows - {item['timestamp']}"):
                    st.code(item['query'], language='sql')

    with tab4:
        """Real-time pipeline logs"""
        st.subheader("📋 DLT Pipeline Logs (Real-time)")

        # Auto-refresh toggle
        col1, col2, col3 = st.columns([2, 2, 3])
        with col1:
            auto_refresh = st.checkbox("🔄 Auto-refresh (5s)", value=False, key='auto_refresh_logs')
        with col2:
            if st.button("🔄 Refresh Now", type="primary"):
                st.rerun()
        with col3:
            st.write(f"Last updated: {datetime.now().strftime('%H:%M:%S')}")

        st.divider()

        # Get and display logs
        logs = get_dlt_logs()

        # Display logs in a code block with syntax highlighting
        st.code(logs, language="bash", line_numbers=True)

        # Auto-refresh if enabled
        if auto_refresh:
            time.sleep(5)
            st.rerun()

    with tab5:
        """GTID status and logs"""
        st.subheader("📍 MySQL GTID Configuration")

        # Current GTID status
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 Refresh GTID Status", type="primary"):
                st.rerun()
        with col2:
            st.write(f"Last updated: {datetime.now().strftime('%H:%M:%S')}")

        st.divider()

        # GTID configuration from MySQL
        st.write("**Current MySQL GTID Status:**")
        gtid_status = get_mysql_gtid_status()
        st.code(gtid_status, language="bash")

        st.divider()

        # GTID logs from pipeline
        st.write("**GTID Log from Pipeline Runs:**")
        gtid_logs = get_gtid_logs()

        if gtid_logs and "No GTID logs" not in gtid_logs:
            # Parse and display as JSON if possible
            try:
                log_lines = gtid_logs.strip().split('\n')
                for i, line in enumerate(reversed(log_lines[-20:])):  # Show last 20 entries
                    with st.expander(f"GTID Log Entry #{len(log_lines) - i}"):
                        import json
                        try:
                            log_data = json.loads(line)
                            st.json(log_data)
                        except:
                            st.code(line, language="json")
            except Exception as e:
                st.code(gtid_logs, language="json")
        else:
            st.info(gtid_logs)

        st.divider()

        # GTID explanation
        with st.expander("ℹ️ About GTID (Global Transaction Identifier)"):
            st.markdown("""
            **What is GTID?**
            - GTID = Global Transaction Identifier
            - Unique identifier for each transaction committed in MySQL
            - Format: `source_id:transaction_number`
            - Example: `3E11FA47-71CA-11E1-9E33-C80AA9429562:23`

            **Why is GTID important for CDC?**
            - Simplifies replication setup
            - Makes it easy to track which transactions have been processed
            - Prevents missing or duplicate transactions
            - Enables automatic failover and recovery

            **GTID Variables:**
            - `gtid_mode`: Enables/disables GTID transactions (ON/OFF)
            - `gtid_executed`: All GTIDs that have been executed on this server
            - `gtid_purged`: All GTIDs that have been purged from binlog
            - `gtid_owned`: GTIDs currently being processed by this server
            """)

    with tab6:
        """CDC data verification and consistency"""
        st.subheader("✅ CDC Data Verification")

        if st.button("🔄 Run verification", type="primary", key="run_verify"):
            try:
                summary = st.session_state.duckdb.get_gtid_summary()
                if isinstance(summary, list) and len(summary) > 0:
                    st.success("CDC events found in MinIO")
                    df = pd.DataFrame(summary)
                    st.dataframe(df, use_container_width=True, hide_index=True)
                elif isinstance(summary, dict) and 'error' in summary:
                    st.error(summary['error'])
                else:
                    st.info("No CDC events yet. Run the pipeline at least once.")
            except Exception as e:
                st.error(str(e))

        st.write("**Tip:** Use the DuckDB UI to query `debezium_cdc.cdc_events` and compare MySQL row counts with latest state in CDC.")


if __name__ == "__main__":
    main()
