-- ==========================================
-- PHASE 5: Schema Reconciliation
-- Merge Phase 1 and Phase 5 files tables
-- ==========================================

-- Create users table for Phase 5
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(255) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Extend files table with Phase 5 columns (keeping Phase 1 id as TEXT)
ALTER TABLE files
ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id) ON DELETE SET NULL;

ALTER TABLE files
ADD COLUMN IF NOT EXISTS is_public BOOLEAN DEFAULT FALSE;

ALTER TABLE files
ADD COLUMN IF NOT EXISTS accessed_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL;

-- Rename/add new columns for Phase 5 compatibility
-- If file_type doesn't exist, it should be derived from mime_type
ALTER TABLE files
ADD COLUMN IF NOT EXISTS file_type VARCHAR(100);

-- If upload_date doesn't exist, map from created_at
ALTER TABLE files
ADD COLUMN IF NOT EXISTS upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

-- If modified_date doesn't exist, map from updated_at
ALTER TABLE files
ADD COLUMN IF NOT EXISTS modified_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

-- If download_count doesn't exist, track it
ALTER TABLE files
ADD COLUMN IF NOT EXISTS download_count INTEGER DEFAULT 0;

-- If deleted doesn't exist (separate from is_deleted)
ALTER TABLE files
ADD COLUMN IF NOT EXISTS deleted BOOLEAN DEFAULT FALSE;

-- Storage node mapping for file operations
ALTER TABLE files
ADD COLUMN IF NOT EXISTS storage_node VARCHAR(10);

ALTER TABLE files
ADD COLUMN IF NOT EXISTS file_path TEXT;

-- Create audit log table for Phase 5 file access tracking
CREATE TABLE IF NOT EXISTS file_access_logs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    file_id TEXT REFERENCES files(id) ON DELETE CASCADE,
    action VARCHAR(50),
    access_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ip_address VARCHAR(45),
    details TEXT
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_files_user_id ON files(user_id);
CREATE INDEX IF NOT EXISTS idx_files_is_public ON files(is_public);
CREATE INDEX IF NOT EXISTS idx_files_storage_node ON files(storage_node);
CREATE INDEX IF NOT EXISTS idx_files_file_id ON files(id);
CREATE INDEX IF NOT EXISTS idx_access_logs_user_id ON file_access_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_access_logs_file_id ON file_access_logs(file_id);
CREATE INDEX IF NOT EXISTS idx_access_logs_action ON file_access_logs(action);
CREATE INDEX IF NOT EXISTS idx_access_logs_date ON file_access_logs(access_date);

-- Grant permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO postgres;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO postgres;
