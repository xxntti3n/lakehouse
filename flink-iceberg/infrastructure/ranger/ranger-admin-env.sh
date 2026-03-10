#!/bin/bash
# Ranger Admin Environment Variables
export RANGER_ADMIN_HOME=/opt/ranger-admin
export RANGER_ADMIN_LOG_DIR=/var/log/ranger
export RANGER_ADMIN_CONF_DIR=$RANGER_ADMIN_HOME/ews/webapp/WEB-INF/classes

# Database Configuration
export DB_HOST=ranger-mysql
export DB_NAME=ranger_db
export DB_USER=ranger
export DB_PASSWORD=ranger123

# Audit Configuration (use MySQL for audit storage)
export AUDIT_STORE=jdbc
