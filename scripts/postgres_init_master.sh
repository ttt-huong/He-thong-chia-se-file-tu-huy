#!/bin/bash
# PostgreSQL Master initialization script
# Sets up streaming replication

set -e

POSTGRES_DB="fileshare"
POSTGRES_USER="postgres"
REPLICATION_USER="replicator"
REPLICATION_PASSWORD="replicator_pass_secure"

echo "==============================================="
echo "PostgreSQL Master Initialization"
echo "==============================================="

# Wait for postgres to be ready
until pg_isready -h localhost -U $POSTGRES_USER; do
  echo 'Waiting for PostgreSQL...'
  sleep 1
done

echo "✅ PostgreSQL is ready"

# Create replication user
echo "Creating replication user: $REPLICATION_USER"
psql -U $POSTGRES_USER -h localhost <<EOF
CREATE USER $REPLICATION_USER WITH REPLICATION ENCRYPTED PASSWORD '$REPLICATION_PASSWORD';
EOF

echo "✅ Replication user created"

# Create main database
echo "Creating database: $POSTGRES_DB"
psql -U $POSTGRES_USER -h localhost <<EOF
CREATE DATABASE $POSTGRES_DB OWNER $POSTGRES_USER;
EOF

echo "✅ Database created"

# Create tables
psql -U $POSTGRES_USER -h localhost -d $POSTGRES_DB <<EOF

-- Files table
CREATE TABLE IF NOT EXISTS files (
    id TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    original_name TEXT NOT NULL,
    file_size BIGINT NOT NULL,
    mime_type TEXT NOT NULL,
    primary_node TEXT NOT NULL,
    replica_nodes TEXT DEFAULT '',
    download_limit INTEGER DEFAULT 3,
    downloads_left INTEGER DEFAULT 3,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    checksum TEXT,
    is_compressed BOOLEAN DEFAULT FALSE,
    has_thumbnail BOOLEAN DEFAULT FALSE,
    is_deleted BOOLEAN DEFAULT FALSE,
    deleted_at TIMESTAMP
);

-- Storage nodes table
CREATE TABLE IF NOT EXISTS storage_nodes (
    node_id TEXT PRIMARY KEY,
    host TEXT NOT NULL,
    port INTEGER NOT NULL,
    path TEXT NOT NULL,
    used_space BIGINT DEFAULT 0,
    free_space BIGINT DEFAULT 0,
    file_count INTEGER DEFAULT 0,
    is_online BOOLEAN DEFAULT TRUE,
    last_heartbeat TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Background tasks table
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    file_id TEXT NOT NULL,
    task_type TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    result TEXT,
    error_message TEXT,
    FOREIGN KEY (file_id) REFERENCES files(id)
);

-- Replication log table
CREATE TABLE IF NOT EXISTS replication_log (
    id TEXT PRIMARY KEY,
    file_id TEXT NOT NULL,
    source_node TEXT NOT NULL,
    target_node TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT,
    FOREIGN KEY (file_id) REFERENCES files(id)
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_files_created_at ON files(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_files_primary_node ON files(primary_node);
CREATE INDEX IF NOT EXISTS idx_files_expires_at ON files(expires_at);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_file_id ON tasks(file_id);
CREATE INDEX IF NOT EXISTS idx_replication_log_status ON replication_log(status);

GRANT ALL PRIVILEGES ON DATABASE $POSTGRES_DB TO $POSTGRES_USER;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO $POSTGRES_USER;

EOF

echo "✅ Tables created with indexes"

# Configure pg_hba.conf for replication
echo ""
echo "Configuring pg_hba.conf for replication..."

# Add replication entry if not exists
if ! grep -q "replication.*$REPLICATION_USER" /var/lib/postgresql/data/pg_hba.conf; then
  echo "host    replication     $REPLICATION_USER    0.0.0.0/0    md5" >> /var/lib/postgresql/data/pg_hba.conf
  echo "✅ Replication entry added to pg_hba.conf"
fi

# Reload PostgreSQL to apply changes
psql -U $POSTGRES_USER -h localhost -c "SELECT pg_reload_conf();"

echo ""
echo "==============================================="
echo "PostgreSQL Master Setup Complete!"
echo "==============================================="
echo ""
echo "Master Details:"
echo "  Host: postgres-master"
echo "  Port: 5432"
echo "  Database: $POSTGRES_DB"
echo "  Admin User: $POSTGRES_USER"
echo "  Replication User: $REPLICATION_USER"
echo ""
