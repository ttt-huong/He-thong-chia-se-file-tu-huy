"""
src/middleware/models.py - Simple Database Models (No SQLAlchemy)
Using sqlite3 directly to avoid Python 3.13 + SQLAlchemy compatibility issues
"""

import sqlite3
import uuid
from datetime import datetime, timedelta
import json
import os
from typing import Optional, Dict, List, Tuple


# Database path
DB_PATH = "fileshare.db"


# Compatibility classes for legacy code that expects SQLAlchemy-like objects
class File:
    """Fake File class for compatibility"""
    checksum = None  # Class attribute for compatibility
    
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)
    
    def to_dict(self):
        return {k: v for k, v in self.__dict__.items()}


class StorageNode:
    """Fake StorageNode class for compatibility"""
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class Task:
    """Fake Task class for compatibility"""
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class ReplicationLog:
    """Fake ReplicationLog class for compatibility"""
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class Database:
    """Simple database wrapper using sqlite3"""
    
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.init_tables()
    
    def get_connection(self):
        """Get a new database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Return rows as dictionaries
        return conn
    
    def init_tables(self):
        """Create all tables"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Files table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS files (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                original_name TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                mime_type TEXT NOT NULL,
                primary_node TEXT NOT NULL,
                replica_nodes TEXT DEFAULT '',
                download_limit INTEGER DEFAULT 3,
                downloads_left INTEGER DEFAULT 3,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                expires_at TEXT NOT NULL,
                checksum TEXT,
                is_compressed INTEGER DEFAULT 0,
                has_thumbnail INTEGER DEFAULT 0,
                is_deleted INTEGER DEFAULT 0,
                deleted_at TEXT
            )
        """)
        
        # Storage nodes table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS storage_nodes (
                node_id TEXT PRIMARY KEY,
                host TEXT NOT NULL,
                port INTEGER NOT NULL,
                path TEXT NOT NULL,
                is_online INTEGER DEFAULT 1,
                total_space INTEGER DEFAULT 0,
                used_space INTEGER DEFAULT 0,
                file_count INTEGER DEFAULT 0,
                last_heartbeat TEXT DEFAULT CURRENT_TIMESTAMP,
                error_count INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Tasks table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                file_id TEXT NOT NULL,
                task_type TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                result TEXT,
                error_message TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                started_at TEXT,
                completed_at TEXT,
                retry_count INTEGER DEFAULT 0
            )
        """)
        
        # Replication logs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS replication_logs (
                id TEXT PRIMARY KEY,
                file_id TEXT NOT NULL,
                source_node TEXT NOT NULL,
                target_node TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                error_message TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                completed_at TEXT,
                duration_seconds REAL
            )
        """)
        
        conn.commit()
        conn.close()
    
    # File operations
    def add_file(self, file_id: str, filename: str, original_name: str, 
                 file_size: int, mime_type: str, primary_node: str, expires_at: str) -> bool:
        """Add a new file record"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            print(f"[DEBUG] Adding file: id={file_id}, primary_node={primary_node}, filename={filename}")
            cursor.execute("""
                INSERT INTO files (id, filename, original_name, file_size, mime_type, 
                                  primary_node, expires_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (file_id, filename, original_name, file_size, mime_type, primary_node, expires_at))
            conn.commit()
            print(f"[DEBUG] File added successfully: {file_id} -> {primary_node}")
            return True
        except Exception as e:
            print(f"[DEBUG] Error adding file: {e}")
            return False
        finally:
            conn.close()
    
    def get_file(self, file_id: str) -> Optional[Dict]:
        """Get file by ID"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM files WHERE id = ?", (file_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None
    
    def get_all_files(self, limit: int = 100) -> List[Dict]:
        """Get all non-deleted files"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM files WHERE is_deleted = 0 ORDER BY created_at DESC LIMIT ?", 
                      (limit,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    def update_file_downloads(self, file_id: str) -> bool:
        """Decrement downloads_left"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                UPDATE files 
                SET downloads_left = downloads_left - 1
                WHERE id = ?
            """, (file_id,))
            conn.commit()
            return True
        except Exception as e:
            print(f"Error updating file downloads: {e}")
            return False
        finally:
            conn.close()
    
    # Task operations
    def add_task(self, file_id: str, task_type: str) -> str:
        """Add a new background task"""
        task_id = str(uuid.uuid4())
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO tasks (id, file_id, task_type)
                VALUES (?, ?, ?)
            """, (task_id, file_id, task_type))
            conn.commit()
            return task_id
        except Exception as e:
            print(f"Error adding task: {e}")
            return ""
        finally:
            conn.close()
    
    def get_pending_tasks(self) -> List[Dict]:
        """Get all pending tasks"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tasks WHERE status = 'pending' ORDER BY created_at ASC")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    def update_task_status(self, task_id: str, status: str, result: str = None, 
                          error_message: str = None) -> bool:
        """Update task status"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            if status == "processing":
                cursor.execute("""
                    UPDATE tasks 
                    SET status = ?, started_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (status, task_id))
            elif status in ["completed", "failed"]:
                cursor.execute("""
                    UPDATE tasks 
                    SET status = ?, completed_at = CURRENT_TIMESTAMP, result = ?, error_message = ?
                    WHERE id = ?
                """, (status, result, error_message, task_id))
            conn.commit()
            return True
        except Exception as e:
            print(f"Error updating task: {e}")
            return False
        finally:
            conn.close()
    
    # Storage node operations
    def add_storage_node(self, node_id: str, host: str, port: int, path: str) -> bool:
        """Add a storage node"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO storage_nodes (node_id, host, port, path)
                VALUES (?, ?, ?, ?)
            """, (node_id, host, port, path))
            conn.commit()
            return True
        except Exception as e:
            print(f"Error adding storage node: {e}")
            return False
        finally:
            conn.close()
    
    def get_storage_nodes(self) -> List[Dict]:
        """Get all storage nodes"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM storage_nodes")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    def get_online_nodes(self) -> List[Dict]:
        """Get all online storage nodes"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM storage_nodes WHERE is_online = 1")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]


# Global database instance
_db_instance = None
_session_instance = None


class Session:
    """Fake SQLAlchemy Session wrapper using sqlite3 Database"""
    def __init__(self, database: 'Database'):
        self.db = database
        self._pending_adds = []
    
    def query(self, model_class):
        """Fake query builder for SQLAlchemy compatibility"""
        return QueryBuilder(self.db, model_class)
    
    def add(self, obj):
        """Add object to pending adds"""
        self._pending_adds.append(obj)
    
    def commit(self):
        """Process all pending adds"""
        for obj in self._pending_adds:
            if isinstance(obj, File):
                self.db.add_file(
                    obj.id, obj.filename, obj.original_name,
                    obj.file_size, obj.mime_type, obj.primary_node, obj.expires_at
                )
            elif isinstance(obj, Task):
                if hasattr(obj, 'id') and hasattr(obj, 'file_id'):
                    conn = self.db.get_connection()
                    cursor = conn.cursor()
                    cursor.execute("""
                        INSERT OR REPLACE INTO tasks (id, file_id, task_type, status)
                        VALUES (?, ?, ?, ?)
                    """, (obj.id, obj.file_id, getattr(obj, 'task_type', 'process'), getattr(obj, 'status', 'pending')))
                    conn.commit()
                    conn.close()
        self._pending_adds = []
    
    def close(self):
        """Close session"""
        self._pending_adds = []


class QueryBuilder:
    """Fake SQLAlchemy QueryBuilder"""
    def __init__(self, db: 'Database', model_class):
        self.db = db
        self.model_class = model_class
        self.filters = []
    
    def filter(self, condition):
        """Add filter condition (simplified)"""
        self.filters.append(condition)
        return self
    
    def order_by(self, column):
        """Add order by (ignored - simplified)"""
        # Simplified: ignore ordering in fake implementation
        return self
    
    def first(self):
        """Get first result"""
        if self.model_class == File:
            # Handle File.checksum == value condition
            for f in self.filters:
                if hasattr(f, 'left') and hasattr(f.left, 'name') and f.left.name == 'checksum':
                    checksum_value = f.right.value if hasattr(f.right, 'value') else str(f.right)
                    conn = self.db.get_connection()
                    cursor = conn.cursor()
                    cursor.execute("SELECT * FROM files WHERE checksum = ?", (checksum_value,))
                    row = cursor.fetchone()
                    conn.close()
                    if row:
                        return File(**dict(row))
        return None
    
    def all(self):
        """Get all results"""
        return self.db.get_all_files()


def get_db() -> Database:
    """Get global database instance"""
    global _db_instance
    if _db_instance is None:
        _db_instance = Database()
    return _db_instance


def get_session() -> Session:
    """Get global session instance"""
    global _session_instance
    if _session_instance is None:
        _session_instance = Session(get_db())
    return _session_instance


def init_db(database_url: str = None) -> Tuple[Database, Session]:
    """Initialize database (for compatibility with old code)"""
    db = Database(DB_PATH)
    session = Session(db)
    return db, session


if __name__ == "__main__":
    db = get_db()
    print("[MODELS] Database initialized successfully")
