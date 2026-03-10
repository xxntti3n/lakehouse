# Apache Ranger Configuration

This directory contains configuration files for Apache Ranger integration with StarRocks.

## Files

- `starrocks-service.json` - Service definition for StarRocks in Ranger
- `docker-entrypoint.sh` - Entrypoint script for Ranger container
- `ranger-admin-env.sh` - Environment variables for Ranger

## Service Dependencies

The `starrocks-service.json` references the StarRocks FE service at `starrocks-fe:9030`.
This service is defined in `docker-compose.ranger.yml` which must be deployed before
using this service definition.

## Implementation Class

The service uses `org.apache.ranger.services.starrocks.RangerServiceStarRocks` as the
implementation class. For development purposes, this may be a custom implementation or
a generic stub. The actual plugin JAR must be provided separately.
