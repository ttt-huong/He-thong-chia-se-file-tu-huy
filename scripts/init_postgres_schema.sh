#!/bin/bash
# PostgreSQL Schema Initialization Script
# Initializes database schema for FileShareSystem in PostgreSQL cluster

set -e

POSTGRES_HOST="${POSTGRES_HOST:-postgres-master}"
POSTGRES_USER="${POSTGRES_USER:-postgres}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-postgres_secure_pass}"
POSTGRES_DB="${POSTGRES_DB:-fileshare}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"

echo "================================================"
echo "PostgreSQL Schema Initialization"
echo "================================================"
echo "Host: $POSTGRES_HOST"
echo "Port: $POSTGRES_PORT"
echo "Database: $POSTGRES_DB"
echo "User: $POSTGRES_USER"

# Function to run SQL
run_sql() {
    PGPASSWORD=$POSTGRES_PASSWORD psql -h $POSTGRES_HOST -U $POSTGRES_USER -d $POSTGRES_DB -p $POSTGRES_PORT -c "$1"
}

# Function to run SQL file
run_sql_file() {
    PGPASSWORD=$POSTGRES_PASSWORD psql -h $POSTGRES_HOST -U $POSTGRES_USER -d $POSTGRES_DB -p $POSTGRES_PORT -f "$1"
}

# Wait for PostgreSQL to be ready
echo ""
echo "Waiting for PostgreSQL to be ready..."
max_retries=30
retry_count=0

while [ $retry_count -lt $max_retries ]; do
    if PGPASSWORD=$POSTGRES_PASSWORD psql -h $POSTGRES_HOST -U $POSTGRES_USER -d $POSTGRES_DB -p $POSTGRES_PORT -c "SELECT 1" >/dev/null 2>&1; then
        echo "✓ PostgreSQL is ready"
        break
    fi
    retry_count=$((retry_count+1))
    echo "Attempt $retry_count/$max_retries: Waiting for PostgreSQL..."
    sleep 2
done

if [ $retry_count -eq $max_retries ]; then
    echo "✗ Failed to connect to PostgreSQL"
    exit 1
fi

# Check if schema already exists
echo ""
echo "Checking existing tables..."
TABLE_COUNT=$(run_sql "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE'" | grep -oE '[0-9]+' | head -1)

if [ "$TABLE_COUNT" -gt 0 ]; then
    echo "✓ Schema already exists with $TABLE_COUNT tables"
    echo "  Skipping schema initialization"
    exit 0
fi

# Initialize schema
echo ""
echo "Initializing schema from postgres_init_schema.sql..."

if [ -f "postgres_init_schema.sql" ]; then
    run_sql_file "postgres_init_schema.sql"
    echo "✓ Schema initialized successfully"
else
    echo "✗ postgres_init_schema.sql not found"
    exit 1
fi

# Verify schema
echo ""
echo "Verifying schema..."
run_sql "SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name"

echo ""
echo "================================================"
echo "Schema initialization completed successfully!"
echo "================================================"
