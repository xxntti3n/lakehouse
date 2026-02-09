#!/bin/bash

echo "======================================"
echo "Setting up MySQL Replication Cluster"
echo "======================================"

# Wait for master to be ready
echo "Waiting for master to be ready..."
until mysql -h mysql-master -uroot -prootpw -e "SELECT 1" &> /dev/null
do
  echo "Master not ready yet... waiting"
  sleep 2
done
echo "Master is ready!"

# Create replication user on master
echo "Creating replication user on master..."
mysql -h mysql-master -uroot -prootpw << 'EOF'
CREATE USER IF NOT EXISTS 'repl_user'@'%' IDENTIFIED WITH mysql_native_password BY 'repl_password';
GRANT REPLICATION SLAVE ON *.* TO 'repl_user'@'%';
FLUSH PRIVILEGES;
EOF

# Get master GTID position
echo "Getting master GTID position..."
MASTER_GTID=$(mysql -h mysql-master -uroot -prootpw -e "SELECT @@GLOBAL.GTID_EXECUTED as gtid;" -s -N)
echo "Master GTID: $MASTER_GTID"

# Setup Replica 1 (Server ID: 2)
echo ""
echo "Setting up Replica 1 (Server ID: 2)..."
mysql -h mysql-replica-1 -uroot -prootpw << EOF
SET GLOBAL server_id = 2;
STOP SLAVE;
CHANGE MASTER TO
  MASTER_HOST='mysql-master',
  MASTER_USER='repl_user',
  MASTER_PASSWORD='repl_password',
  MASTER_AUTO_POSITION=1;
START SLAVE;
EOF

# Check Replica 1 status
echo "Replica 1 Status:"
mysql -h mysql-replica-1 -uroot -prootpw -e "SHOW SLAVE STATUS\G" | grep -E "Slave_IO_Running|Slave_SQL_Running|Last_Error|Retrieved_Gtid_Set|Executed_Gtid_Set"

# Setup Replica 2 (Server ID: 3)
echo ""
echo "Setting up Replica 2 (Server ID: 3)..."
mysql -h mysql-replica-2 -uroot -prootpw << EOF
SET GLOBAL server_id = 3;
STOP SLAVE;
CHANGE MASTER TO
  MASTER_HOST='mysql-master',
  MASTER_USER='repl_user',
  MASTER_PASSWORD='repl_password',
  MASTER_AUTO_POSITION=1;
START SLAVE;
EOF

# Check Replica 2 status
echo "Replica 2 Status:"
mysql -h mysql-replica-2 -uroot -prootpw -e "SHOW SLAVE STATUS\G" | grep -E "Slave_IO_Running|Slave_SQL_Running|Last_Error|Retrieved_Gtid_Set|Executed_Gtid_Set"

echo ""
echo "======================================"
echo "Replication Setup Complete!"
echo "======================================"
echo ""
echo "Cluster Status:"
echo "  Master (Server ID: 1)  - mysql-master:3306  (read-write)"
echo "  Replica 1 (Server ID: 2) - mysql-replica-1:3307  (read-only)"
echo "  Replica 2 (Server ID: 3) - mysql-replica-2:3308  (read-only)"
echo ""
echo "To verify replication, run:"
echo "  docker exec mysql-master mysql -uroot -prootpw appdb -e 'SELECT * FROM products;'"
echo "  docker exec mysql-replica-1 mysql -uroot -prootpw appdb -e 'SELECT * FROM products;'"
echo "  docker exec mysql-replica-2 mysql -uroot -prootpw appdb -e 'SELECT * FROM products;'"
