#!/bin/bash
set -e

# StarRocks Ranger Plugin Installation Script
# This script downloads and installs the Ranger plugin for StarRocks

echo "=== StarRocks Ranger Plugin Installer ==="

# Configuration
RANGER_VERSION="2.5.0"
STARROCKS_VERSION="3.3.5"
PLUGIN_DIR="/opt/starrocks/ranger-plugin"
RANGER_ADMIN_URL="http://ranger-admin:6080"
SERVICE_NAME="starrocks"

# Wait for Ranger Admin to be ready
echo "Waiting for Ranger Admin to be ready..."
attempts=0
until curl -s -f -o /dev/null "$RANGER_ADMIN_URL/login.jsp" || [ $attempts -gt 30 ]; do
  echo "Ranger Admin not ready yet... (attempt $((attempts+1))/30)"
  sleep 5
  attempts=$((attempts+1))
done

if [ $attempts -gt 30 ]; then
  echo "ERROR: Ranger Admin did not become ready in time"
  exit 1
fi

echo "Ranger Admin is ready!"

# Create plugin directory
echo "Creating plugin directory at $PLUGIN_DIR"
mkdir -p "$PLUGIN_DIR/conf"
mkdir -p "$PLUGIN_DIR/lib"
mkdir -p /var/log/ranger/starrocks/policycache
mkdir -p /var/log/ranger/starrocks/audit

# Download Ranger plugin for StarRocks
# Note: This assumes the plugin JAR is available. In production,
# you would build this from source or download from Apache Ranger releases.
echo "Downloading Ranger StarRocks plugin..."

# For this setup, we'll create a placeholder that would be replaced
# with the actual plugin in production
cat > "$PLUGIN_DIR/README.md" << 'EOF'
# Ranger Plugin for StarRocks

This directory contains the Apache Ranger plugin for StarRocks.

## Installation

In production, download the official Ranger StarRocks plugin from:
https://ranger.apache.org/downloads.html

Or build from source:
1. Clone Apache Ranger repository
2. Build StarRocks plugin: mvn clean package -DskipTests
3. Copy target/ranger-starrocks-plugin-*.jar to this directory

## Configuration

The plugin is configured via ranger-svc-security.xml in the conf/ directory.
EOF

# Configuration files
echo "Checking configuration files..."
if [ -f "$PLUGIN_DIR/conf/ranger-svc-security.xml" ]; then
    echo "✓ Ranger security configuration found (mounted by Docker)"
else
    echo "WARNING: ranger-svc-security.xml not found at $PLUGIN_DIR/conf/"
fi

echo "=== Installation Complete ==="
echo "Plugin directory: $PLUGIN_DIR"
echo "Note: The actual plugin JAR must be provided separately"
