-- PostgreSQL Master Init Script
-- Setup replication user và configuration

-- Create replication user
CREATE ROLE replicator WITH REPLICATION ENCRYPTED PASSWORD 'replication_password_123';

-- Grant connect permission
GRANT CONNECT ON DATABASE fileshare_db TO replicator;

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create pg_hba.conf entry for replication (done via environment)
