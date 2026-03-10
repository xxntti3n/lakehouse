#!/bin/bash
# Apache Ranger Docker Entrypoint
# Handles database configuration and Ranger startup

set -e

# Wait for MySQL to be ready
echo "Waiting for MySQL at ${DB_HOST:-ranger-mysql}:3306..."
until mysqladmin ping -h"${DB_HOST:-ranger-mysql}" -P3306 -u"${DB_USER:-ranger}" -p"${DB_PASSWORD:-ranger123}" --silent 2>/dev/null; do
    echo "MySQL is unavailable - sleeping"
    sleep 2
done
echo "MySQL is ready!"

# Configure Ranger admin site XML
echo "Configuring Ranger Admin..."

# Create or update ranger-admin-site.xml
cat > /opt/ranger-admin/ews/webapp/WEB-INF/classes/ranger-admin-site.xml << 'XMLOE'
<?xml version="1.0"?>
<?xml-stylesheet type="text/xsl" href="configuration.xsl"?>
<configuration>
  <property>
    <name>ranger.jpa.jdbc.url</name>
    <value>jdbc:mysql://DB_HOST:3306/DB_NAME</value>
  </property>
  <property>
    <name>ranger.jpa.jdbc.driver</name>
    <value>com.mysql.cj.jdbc.Driver</value>
  </property>
  <property>
    <name>ranger.jpa.jdbc.user</name>
    <value>DB_USER</value>
  </property>
  <property>
    <name>ranger.jpa.jdbc.password</name>
    <value>DB_PASSWORD</value>
  </property>
  <property>
    <name>ranger.jpa.jdbc.credential.provider.path</name>
    <value>/etc/ranger/admin/conf/jceks/rangeradmin.jceks</value>
  </property>
</configuration>
XMLOE

# Replace placeholders with actual values
sed -i "s/DB_HOST/${DB_HOST:-ranger-mysql}/g" /opt/ranger-admin/ews/webapp/WEB-INF/classes/ranger-admin-site.xml
sed -i "s/DB_NAME/${DB_NAME:-ranger_db}/g" /opt/ranger-admin/ews/webapp/WEB-INF/classes/ranger-admin-site.xml
sed -i "s/DB_USER/${DB_USER:-ranger}/g" /opt/ranger-admin/ews/webapp/WEB-INF/classes/ranger-admin-site.xml
sed -i "s/DB_PASSWORD/${DB_PASSWORD:-ranger123}/g" /opt/ranger-admin/ews/webapp/WEB-INF/classes/ranger-admin-site.xml

# Start Ranger Admin based on command
case "$1" in
    start)
        echo "Starting Ranger Admin..."
        cd /opt/ranger-admin
        ./ews/ranger-admin-services.sh start
        echo "Ranger Admin started!"
        # Keep container running
        tail -f /dev/null
        ;;
    *)
        echo "Usage: $0 {start}"
        exit 1
        ;;
esac
