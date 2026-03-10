# StarRocks + Apache Ranger on Colima - Design Spec

**Date:** 2026-03-10
**Status:** Approved

## Overview

Deploy a complete StarRocks data warehouse with Apache Ranger authorization on Colima for local development.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Colima VM (4CPU, 8GB, 60GB)              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │         Shared Network: lakehouse_network           │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │   │
│  │  │  MySQL   │──│  Ranger  │──│  StarRocks FE    │  │   │
│  │  │  :3306   │  │  :6080   │  │  :8030, :9030    │  │   │
│  │  └──────────┘  └──────────┘  │         │         │  │   │
│  │                               └─────────┼─────────┘  │   │
│  │                                         │             │   │
│  │                                   ┌─────┴─────┐      │   │
│  │                                   │StarRocks BE│      │   │
│  │                                   │  :8040     │      │   │
│  │                                   └───────────┘      │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## Services

| Service | Image | Ports | Purpose |
|---------|-------|-------|---------|
| MySQL | mysql:8.0 | 3306 (internal) | Ranger metadata store |
| Ranger Admin | custom build | 6080:6080 | Policy management UI |
| StarRocks FE | starrocks/fe:3.3-latest | 8030, 9030, 9020 | Query frontend |
| StarRocks BE | starrocks/be:3.3-latest | 8040 | Data backend |

## File Structure

```
infrastructure/
├── docker-compose.network.yml    # Shared network
├── docker-compose.mysql.yml      # MySQL for Ranger
├── docker-compose.ranger.yml     # Ranger Admin
├── docker-compose.starrocks.yml  # StarRocks FE + BE
├── deploy.sh                     # Orchestration script
├── ranger/                       # Existing configs
└── starrocks/                    # Existing configs
```

## Service Configurations

### MySQL
- Database: `ranger_db`
- User: `ranger` / `ranger123`
- Health check: TCP on 3306

### Ranger Admin
- UI: http://localhost:6080
- Default admin: admin/admin
- Depends on MySQL
- Mounts `starrocks-service.json`

### StarRocks FE
- MySQL protocol: localhost:9030
- HTTP UI: localhost:8030
- Loads Ranger plugin from `/opt/starrocks/fe/ranger-plugin`

### StarRocks BE
- HTTP: localhost:8040
- Connects to FE for registration

## Startup Orchestration

**Order:** Network → MySQL → Ranger → StarRocks FE → StarRocks BE

**deploy.sh commands:**
- `./deploy.sh start` - Start all services in order
- `./deploy.sh stop` - Stop all services
- `./deploy.sh status` - Show service health
- `./deploy.sh logs` - Show logs from all services
- `./deploy.sh restart` - Restart all services

## Access

- Ranger UI: http://localhost:6080 (admin/admin)
- StarRocks: `mysql -h 127.0.0.1 -P 9030 -u root`
- StarRocks UI: http://localhost:8030

## Verification

1. All containers running
2. MySQL accepting connections
3. Ranger UI accessible
4. StarRocks FE ready
5. StarRocks BE registered
6. Ranger plugin loaded

## Storage

Ephemeral (data lost when containers removed) - suitable for testing/development only.
