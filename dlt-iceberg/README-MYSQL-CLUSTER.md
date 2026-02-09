# MySQL Replication Cluster with GTID

## 🎯 Overview

This setup creates a **3-node MySQL replication cluster** with GTID-based replication:

```
┌──────────────────┐
│  mysql-master    │ (Server ID: 1) - Port 3306
│  (Read-Write)    │
└────────┬─────────┘
         │ GTID Replication
    ┌────┴────┐
    │         │
┌───▼─────┐ ┌▼─────────┐
│ replica-1│ │ replica-2│
│ (Server 2)│ │ (Server 3)│
│ Port 3307│ │ Port 3308│
│(Read-Only)│ │(Read-Only)│
└──────────┘ └──────────┘
```

## 🚀 Quick Start

### Stop current single MySQL setup
```bash
docker-compose down
```

### Start MySQL Cluster
```bash
docker-compose -f docker-compose-mysql-cluster.yml up -d
```

### Wait for replication setup (30 seconds)
```bash
# Watch the replication setup
docker logs -f replication-setup

# Wait until you see "Replication Setup Complete!"
```

## 🔍 Verify Replication

### Check Cluster Status
```bash
# Master (read-write)
docker exec mysql-master mysql -uroot -prootpw -e "SELECT @@server_id, @@hostname, @@read_only;"

# Replica 1 (read-only)
docker exec mysql-replica-1 mysql -uroot -prootpw -e "SELECT @@server_id, @@hostname, @@read_only;"

# Replica 2 (read-only)
docker exec mysql-replica-2 mysql -uroot -prootpw -e "SELECT @@server_id, @@hostname, @@read_only;"
```

### Check Replication Status
```bash
# Check Replica 1
docker exec mysql-replica-1 mysql -uroot -prootpw -e "SHOW SLAVE STATUS\G" | grep -E "Slave_IO_Running|Slave_SQL_Running|Seconds_Behind_Master"

# Check Replica 2
docker exec mysql-replica-2 mysql -uroot -prootpw -e "SHOW SLAVE STATUS\G" | grep -E "Slave_IO_Running|Slave_SQL_Running|Seconds_Behind_Master"
```

You should see:
- `Slave_IO_Running: Yes`
- `Slave_SQL_Running: Yes`
- `Seconds_Behind_Master: 0`

### Test Replication
```bash
# Insert data on MASTER
docker exec mysql-master mysql -uroot -prootpw appdb -e "INSERT INTO products (name, price) VALUES ('Test Product', 99.99);"

# Check MASTER (should show the new row)
docker exec mysql-master mysql -uroot -prootpw appdb -e "SELECT * FROM products ORDER BY id DESC LIMIT 1;"

# Check REPLICA 1 (should also show the new row)
docker exec mysql-replica-1 mysql -uroot -prootpw appdb -e "SELECT * FROM products ORDER BY id DESC LIMIT 1;"

# Check REPLICA 2 (should also show the new row)
docker exec mysql-replica-2 mysql -uroot -prootpw appdb -e "SELECT * FROM products ORDER BY id DESC LIMIT 1;"
```

## 📊 Server Details

| Server | Container Name | Port | Server ID | Mode | Purpose |
|--------|---------------|------|-----------|------|---------|
| Master | mysql-master | 3306 | 1 | Read-Write | Accepts writes, replicates to replicas |
| Replica 1 | mysql-replica-1 | 3307 | 2 | Read-Only | Syncs from master via GTID |
| Replica 2 | mysql-replica-2 | 3308 | 3 | Read-Only | Syncs from master via GTID |

## 🔐 Replication Details

### GTID Configuration
- **GTID Mode**: ON on all servers
- **Replication User**: `repl_user` / `repl_password`
- **Replication Method**: GTID auto-positioning
- **Binlog Format**: ROW

### Master Information
- **Hostname**: mysql-master
- **Data Volume**: mysql_master_data
- **Config**: infrastructure/master.cnf

### Replica Information
- **Hostnames**: mysql-replica-1, mysql-replica-2
- **Data Volumes**: mysql_replica1_data, mysql_replica2_data
- **Config**: infrastructure/replica.cnf
- **Read-Only**: YES

## 🛠️ Management Commands

### View All Server Status
```bash
echo "=== MASTER ===" && \
docker exec mysql-master mysql -uroot -prootpw -e "SHOW MASTER STATUS\G" && \
echo -e "\n=== REPLICA 1 ===" && \
docker exec mysql-replica-1 mysql -uroot -prootpw -e "SHOW SLAVE STATUS\G" | grep -E "Master_Host|Slave_IO_Running|Slave_SQL_Running|Retrieved_Gtid_Set|Executed_Gtid_Set" && \
echo -e "\n=== REPLICA 2 ===" && \
docker exec mysql-replica-2 mysql -uroot -prootpw -e "SHOW SLAVE STATUS\G" | grep -E "Master_Host|Slave_IO_Running|Slave_SQL_Running|Retrieved_Gtid_Set|Executed_Gtid_Set"
```

### Stop/Start Replica
```bash
# Stop replica
docker exec mysql-replica-1 mysql -uroot -prootpw -e "STOP SLAVE;"

# Start replica
docker exec mysql-replica-1 mysql -uroot -prootpw -e "START SLAVE;"

# Reset replica (break replication)
docker exec mysql-replica-1 mysql -uroot -prootpw -e "STOP SLAVE; RESET SLAVE ALL;"
```

### Monitor Replication Lag
```bash
watch -n 1 'docker exec mysql-replica-1 mysql -uroot -prootpw -e "SHOW SLAVE STATUS\G" | grep Seconds_Behind_Master'
```

## 🔄 Switch Back to Single MySQL

To revert to the original single-server setup:

```bash
# Stop cluster
docker-compose -f docker-compose-mysql-cluster.yml down

# Remove volumes (optional - deletes all data)
docker volume rm dlt-iceberg_mysql_master_data
docker volume rm dlt-iceberg_mysql_replica1_data
docker volume rm dlt-iceberg_mysql_replica2_data

# Start single server setup
docker-compose up -d
```

## 📈 GTID Tracking

Each server tracks GTIDs independently:

```bash
# Master GTID
docker exec mysql-master mysql -uroot -prootpw -e "SELECT @@GLOBAL.GTID_EXECUTED as Master_GTID;"

# Replica 1 GTID
docker exec mysql-replica-1 mysql -uroot -prootpw -e "SELECT @@GLOBAL.GTID_EXECUTED as Replica1_GTID;"

# Replica 2 GTID
docker exec mysql-replica-2 mysql -uroot -prootpw -e "SELECT @@GLOBAL.GTID_EXECUTED as Replica2_GTID;"
```

All three should show the same GTID set when replication is working correctly.

## 🔧 Troubleshooting

### Replication Not Working
```bash
# Check replica status
docker exec mysql-replica-1 mysql -uroot -prootpw -e "SHOW SLAVE STATUS\G"

# Look for errors in:
# - Last_IO_Error
# - Last_SQL_Error
```

### Restart Replication
```bash
# On replica
docker exec mysql-replica-1 mysql -uroot -prootpw << EOF
STOP SLAVE;
RESET SLAVE;
CHANGE MASTER TO
  MASTER_HOST='mysql-master',
  MASTER_USER='repl_user',
  MASTER_PASSWORD='repl_password',
  MASTER_AUTO_POSITION=1;
START SLAVE;
EOF
```

### Skip Replication Error (Testing Only)
```bash
docker exec mysql-replica-1 mysql -uroot -prootpw << EOF
STOP SLAVE;
SET GLOBAL sql_slave_skip_counter = 1;
START SLAVE;
EOF
```

---

**Status**: Ready to deploy ✅
**Servers**: 3 (1 Master + 2 Replicas)
**Replication**: GTID-based
