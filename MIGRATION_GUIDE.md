# Phase 4.3: Data Migration - SQLite to PostgreSQL

## Overview
Migrate FileShareSystem data from SQLite to PostgreSQL cluster with validation and rollback support.

## Prerequisites
- PostgreSQL 15+ cluster running (Phase 4.0-4.1)
- PgBouncer connection pooling (Phase 4.2)
- SQLite database with existing data (optional)
- Python 3.8+ with psycopg2

## Migration Architecture

### Components
1. **postgres_init_schema.sql** - PostgreSQL schema initialization
2. **migrate_sqlite_to_postgres.py** - Main migration script
3. **Validation logic** - Ensure data integrity post-migration

### Tables Migrated
- `files` - File metadata (file share records)
- `storage_nodes` - Storage cluster nodes
- `tasks` - Async processing jobs
- `replication_logs` - File replication history

## Step-by-Step Migration

### 1. Start PostgreSQL Cluster
```bash
docker-compose up -d postgres-master postgres-standby1 postgres-standby2 etcd
```

### 2. Verify PostgreSQL is Ready
```bash
# Check if PostgreSQL is accepting connections
docker-compose exec postgres-master pg_isready
```

### 3. Initialize Schema (if not auto-initialized)
```bash
# Run schema SQL on master
docker-compose exec postgres-master psql -U postgres -d fileshare -f /docker-entrypoint-initdb.d/schema.sql
```

### 4. Run Migration Script
```bash
# From project root directory
python scripts/migrate_sqlite_to_postgres.py
```

Expected output:
```
============================================================
SQLite to PostgreSQL Data Migration
============================================================
Status: completed
Total tables migrated: 4
Total rows migrated: 125

files:
  Total rows: 50
  Migrated: 50
  Status: completed

storage_nodes:
  Total rows: 3
  Migrated: 3
  Status: completed

tasks:
  Total rows: 45
  Migrated: 45
  Status: completed

replication_logs:
  Total rows: 27
  Migrated: 27
  Status: completed

============================================================
VALIDATION
============================================================
Validation status: completed
✓ files: SQLite=50, PostgreSQL=50
✓ storage_nodes: SQLite=3, PostgreSQL=3
✓ tasks: SQLite=45, PostgreSQL=45
✓ replication_logs: SQLite=27, PostgreSQL=27
============================================================
```

### 5. Start Full System
```bash
# Start all services including PgBouncer
docker-compose up -d
```

### 6. Verify Connection Pool
```bash
# Check pool statistics
curl http://localhost:5000/pool/summary
```

Expected response:
```json
{
  "status": "ok",
  "pool_mode": "transaction",
  "max_client_conn": 1000,
  "default_pool_size": 25,
  "reserve_pool_size": 5,
  "connected_clients": 3,
  "stats": [...],
  "pools": [...]
}
```

## Environment Variables

Set these before running migration:

```bash
# PostgreSQL connection (Master)
export DATABASE_URL=postgresql://postgres:postgres_secure_pass@postgres-master:5432/fileshare

# PostgreSQL credentials
export POSTGRES_USER=postgres
export POSTGRES_PASSWORD=postgres_secure_pass
export POSTGRES_DB=fileshare
export POSTGRES_PORT=5432

# SQLite path (optional, default: fileshare.db)
export SQLITE_PATH=/path/to/fileshare.db
```

## Rollback Strategy

### If Migration Fails
1. **Check logs** - Review migration script output for errors
2. **Verify PostgreSQL** - Ensure cluster is healthy
3. **Inspect SQLite** - Verify source data exists
4. **Drop tables** (if needed):
   ```bash
   docker-compose exec postgres-master psql -U postgres -d fileshare -c "
   DROP TABLE IF EXISTS replication_logs;
   DROP TABLE IF EXISTS tasks;
   DROP TABLE IF EXISTS files;
   DROP TABLE IF EXISTS storage_nodes;
   "
   ```
5. **Re-run migration** - Execute migration script again

### Backup Before Migration
```bash
# Backup PostgreSQL (on master)
docker-compose exec postgres-master pg_dump -U postgres fileshare > backup_fileshare.sql

# Backup SQLite
cp fileshare.db fileshare.db.backup
```

## Validation Queries

After migration, verify data:

```bash
# Connect to PostgreSQL
docker-compose exec postgres-master psql -U postgres -d fileshare

# Count rows per table
SELECT 'files' as table_name, COUNT(*) as row_count FROM files
UNION ALL
SELECT 'storage_nodes', COUNT(*) FROM storage_nodes
UNION ALL
SELECT 'tasks', COUNT(*) FROM tasks
UNION ALL
SELECT 'replication_logs', COUNT(*) FROM replication_logs;

# Check file distribution
SELECT primary_node, COUNT(*) as file_count 
FROM files 
WHERE is_deleted = FALSE 
GROUP BY primary_node;

# Verify replication status
SELECT status, COUNT(*) as count 
FROM replication_logs 
GROUP BY status;
```

## Performance Considerations

- **Batch size** - Migration processes rows sequentially (optimize if needed)
- **Connection pooling** - PgBouncer handles concurrent connections
- **Index creation** - Indexes are created before data import for optimal performance
- **Replication** - Streaming replication replicates all changes to standbys

## Monitoring Post-Migration

### Database Health
```bash
curl http://localhost:5000/db/health
```

### Replication Lag
```bash
curl http://localhost:5000/db/replication/lag
```

### Pool Statistics
```bash
curl http://localhost:5000/pool/summary
```

### Patroni Cluster Status
```bash
curl http://localhost:5000/patroni/cluster
```

## Troubleshooting

### Error: "Table already exists"
PostgreSQL tables exist from previous run. Drop and recreate:
```bash
python scripts/migrate_sqlite_to_postgres.py  # Will skip if tables exist
```

### Error: "Connection refused"
PostgreSQL not running or not ready:
```bash
docker-compose logs postgres-master
```

### Row count mismatch
If validation shows mismatch:
1. Check error logs in migration output
2. Manually verify specific tables
3. Re-run migration after cleanup

### Slow migration
If migration is slow:
1. Check PostgreSQL disk I/O
2. Monitor network if remote PostgreSQL
3. Consider batching in migration script

## Post-Migration Checklist

- [ ] Migration completed successfully
- [ ] Validation passed (all row counts match)
- [ ] Backup created
- [ ] Full system started (docker-compose up -d)
- [ ] API endpoints responding
- [ ] Pool statistics accessible
- [ ] Database health check passing
- [ ] Replication lag within acceptable range
- [ ] Failover testing successful

## Next Steps

After successful migration:
1. **Dashboard Integration** - Add replication status to UI
2. **Failover Testing** - Test automatic failover scenarios
3. **Performance Tuning** - Optimize pool settings
4. **Monitoring** - Set up alerts for replication lag
