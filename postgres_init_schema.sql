-- PostgreSQL Schema Initialization for FileShareSystem
-- Phase 4: Database High Availability

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Files table - Store file metadata
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
    deleted_at TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_files_primary_node ON files(primary_node);
CREATE INDEX IF NOT EXISTS idx_files_created_at ON files(created_at);
CREATE INDEX IF NOT EXISTS idx_files_expires_at ON files(expires_at);
CREATE INDEX IF NOT EXISTS idx_files_is_deleted ON files(is_deleted);

-- Storage nodes table - Track storage cluster nodes
CREATE TABLE IF NOT EXISTS storage_nodes (
    node_id TEXT PRIMARY KEY,
    host TEXT NOT NULL,
    port INTEGER NOT NULL,
    path TEXT NOT NULL,
    is_online BOOLEAN DEFAULT TRUE,
    total_space BIGINT DEFAULT 0,
    used_space BIGINT DEFAULT 0,
    file_count INTEGER DEFAULT 0,
    last_heartbeat TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    error_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_storage_nodes_is_online ON storage_nodes(is_online);
CREATE INDEX IF NOT EXISTS idx_storage_nodes_last_heartbeat ON storage_nodes(last_heartbeat);

-- Tasks table - Async job tracking (image processing, replication)
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    file_id TEXT NOT NULL,
    task_type TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    result TEXT,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    retry_count INTEGER DEFAULT 0,
    FOREIGN KEY (file_id) REFERENCES files(id)
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_tasks_file_id ON tasks(file_id);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_task_type ON tasks(task_type);

-- Replication logs table - Track file replication events
CREATE TABLE IF NOT EXISTS replication_logs (
    id TEXT PRIMARY KEY,
    file_id TEXT NOT NULL,
    source_node TEXT NOT NULL,
    target_node TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    duration_seconds NUMERIC(10, 2),
    FOREIGN KEY (file_id) REFERENCES files(id),
    FOREIGN KEY (source_node) REFERENCES storage_nodes(node_id),
    FOREIGN KEY (target_node) REFERENCES storage_nodes(node_id)
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_replication_logs_file_id ON replication_logs(file_id);
CREATE INDEX IF NOT EXISTS idx_replication_logs_status ON replication_logs(status);
CREATE INDEX IF NOT EXISTS idx_replication_logs_created_at ON replication_logs(created_at);

-- Migration status tracking
CREATE TABLE IF NOT EXISTS migration_status (
    id SERIAL PRIMARY KEY,
    table_name TEXT NOT NULL,
    total_rows INTEGER,
    migrated_rows INTEGER DEFAULT 0,
    status TEXT DEFAULT 'pending',
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT
);

-- Grant permissions to postgres user
GRANT ALL PRIVILEGES ON DATABASE fileshare TO postgres;
