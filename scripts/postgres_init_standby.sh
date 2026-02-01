#!/bin/bash
# PostgreSQL Standby initialization script
# Sets up streaming replication from master

set -e

POSTGRES_USER="postgres"
REPLICATION_USER="replicator"
REPLICATION_PASSWORD="replicator_pass_secure"
MASTER_HOST="postgres-master"
MASTER_PORT="5432"

echo "==============================================="
echo "PostgreSQL Standby Initialization"
echo "==============================================="

# Wait for master to be ready
echo "Waiting for master PostgreSQL at $MASTER_HOST:$MASTER_PORT..."
for i in {1..30}; do
  if pg_isready -h $MASTER_HOST -U $REPLICATION_USER -p $MASTER_PORT 2>/dev/null; then
    echo "✅ Master is ready"
    break
  fi
  echo "Attempt $i/30: Waiting for master..."
  sleep 2
done

# Check if standby already has data
if [ -f /var/lib/postgresql/data/PG_VERSION ]; then
  echo "✅ Standby database already initialized, skipping..."
else
  echo "Cloning master database using pg_basebackup..."
  
  # Use pg_basebackup to clone the master
  pg_basebackup \
    -h $MASTER_HOST \
    -D /var/lib/postgresql/data \
    -U $REPLICATION_USER \
    -v \
    -P \
    -W \
    --wal-method=stream \
    --slot=standby_slot
  
  echo "✅ Database cloned successfully"
  
  # Create recovery.conf (or postgresql.conf recovery settings for PG12+)
  echo "standby_mode = 'on'" > /var/lib/postgresql/data/recovery.conf
  echo "primary_conninfo = 'host=$MASTER_HOST port=$MASTER_PORT user=$REPLICATION_USER password=$REPLICATION_PASSWORD'" >> /var/lib/postgresql/data/recovery.conf
  echo "recovery_target_timeline = 'latest'" >> /var/lib/postgresql/data/recovery.conf
  
  chown postgres:postgres /var/lib/postgresql/data/recovery.conf
  chmod 600 /var/lib/postgresql/data/recovery.conf
  
  echo "✅ Recovery configuration created"
fi

echo ""
echo "==============================================="
echo "PostgreSQL Standby Setup Complete!"
echo "==============================================="
echo ""
echo "Standby Details:"
echo "  Host: postgres-standby1/postgres-standby2"
echo "  Port: 5432"
echo "  Replicating from: $MASTER_HOST:$MASTER_PORT"
echo ""
