#!/bin/bash
set -e

# Source environment variables
if [ -f /opt/ranger-admin/ranger-admin-env.sh ]; then
    source /opt/ranger-admin/ranger-admin-env.sh
fi

# Set up Ranger admin environment
export JAVA_HOME=/usr/lib/jvm/java-17-openjdk
export RANGER_ADMIN_HOME=${RANGER_ADMIN_HOME:-/opt/ranger-admin}
export RANGER_ADMIN_CONF_DIR="$RANGER_ADMIN_HOME/ews/webapp/WEB-INF/classes"

# Default database configuration (can be overridden by env file)
DB_HOST=${DB_HOST:-ranger-mysql}
DB_NAME=${DB_NAME:-ranger_db}
DB_USER=${DB_USER:-ranger}
DB_PASSWORD=${DB_PASSWORD:-ranger123}

# Wait for MySQL to be ready (with timeout)
echo "Waiting for MySQL to be ready..."
TIMEOUT=60
ELAPSED=0
until mysql -h "$DB_HOST" -u "$DB_USER" -p"$DB_PASSWORD" -e "SELECT 1" &> /dev/null; do
    if [ "$ELAPSED" -ge "$TIMEOUT" ]; then
        echo "ERROR: MySQL connection timeout after ${TIMEOUT}s"
        exit 1
    fi
    echo "MySQL is unavailable - sleeping ($((ELAPSED))/${TIMEOUT}s)"
    sleep 2
    ELAPSED=$((ELAPSED + 2))
done
echo "MySQL is ready!"

# Configure database connection
if [ -f "$RANGER_ADMIN_CONF_DIR/ranger-admin-site.xml" ]; then
    sed -i.bak "s|jdbc:mysql://localhost:3306/ranger|jdbc:mysql://${DB_HOST}:3306/${DB_NAME}|g" \
        "$RANGER_ADMIN_CONF_DIR/ranger-admin-site.xml"
    rm -f "$RANGER_ADMIN_CONF_DIR/ranger-admin-site.xml.bak"
else
    echo "WARNING: ranger-admin-site.xml not found, skipping configuration"
fi

# Start Ranger Admin
echo "Starting Ranger Admin..."
cd "$RANGER_ADMIN_HOME"
ews/ranger-admin-services.sh start

# Keep container running
echo "Ranger Admin started. Keeping container alive..."
tail -f /dev/null
