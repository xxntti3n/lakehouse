#!/bin/bash
# Set server_id for MySQL 3 instance
# This script runs after the MySQL data directory is initialized
# but before the server starts for the first time

# Ensure server_id is set to 3
sed -i 's/server-id = 3/server-id = 3/' /var/lib/mysql/auto.cnf 2>/dev/null || true

# Create a marker file to track which server this is
echo "mysql-server-3" > /var/lib/mysql/server_marker.txt
echo "Server ID: 3 configured at $(date)" >> /var/lib/mysql/server_marker.txt
