"""
Database Abstraction Layer
Hỗ trợ cả SQLite (legacy) và PostgreSQL (Phase 4)
Cho phép read-write splitting với master-slave
"""

import os
import logging
import sqlite3
import psycopg2
from psycopg2 import pool
from typing import Optional, Dict, List, Tuple
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class DatabaseConnection:
    """Wrapper chung cho kết nối database"""
    
    def __init__(self, db_type: str, connection):
        self.db_type = db_type
        self.connection = connection
    
    def execute(self, query: str, params: tuple = None):
        """Execute query"""
        try:
            cursor = self.connection.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            self.connection.commit()
            return cursor
        except Exception as e:
            logger.error(f"Database execute error: {e}")
            raise
    
    def fetch_one(self, query: str, params: tuple = None) -> Optional[Dict]:
        """Fetch one row"""
        try:
            cursor = self.connection.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            if self.db_type == 'postgresql':
                columns = [desc[0] for desc in cursor.description]
                row = cursor.fetchone()
                return dict(zip(columns, row)) if row else None
            else:
                return cursor.fetchone()
        except Exception as e:
            logger.error(f"Database fetch_one error: {e}")
            return None
    
    def fetch_all(self, query: str, params: tuple = None) -> List[Dict]:
        """Fetch all rows"""
        try:
            cursor = self.connection.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            if self.db_type == 'postgresql':
                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()
                return [dict(zip(columns, row)) for row in rows]
            else:
                return cursor.fetchall()
        except Exception as e:
            logger.error(f"Database fetch_all error: {e}")
            return []
    
    def close(self):
        """Close connection"""
        if self.connection:
            self.connection.close()


class DatabaseManager:
    """Quản lý database connections với read-write splitting"""
    
    def __init__(self):
        self.db_type = self._detect_db_type()
        self.master_conn = None
        self.read_conn = None
        self.pg_pool_master = None
        self.pg_pool_read = None
        
        self._initialize()
    
    def _detect_db_type(self) -> str:
        """Detect database type từ environment"""
        db_url = os.getenv('DATABASE_URL', '')
        
        if db_url.startswith('postgresql'):
            return 'postgresql'
        else:
            return 'sqlite'
    
    def _initialize(self):
        """Initialize database connections"""
        if self.db_type == 'postgresql':
            self._init_postgresql()
        else:
            self._init_sqlite()
    
    def _init_sqlite(self):
        """Initialize SQLite connections"""
        db_path = os.getenv('DATABASE_URL', 'sqlite:////app/data/fileshare.db').replace('sqlite:///', '')
        
        try:
            self.master_conn = sqlite3.connect(db_path)
            self.master_conn.row_factory = sqlite3.Row
            self.read_conn = sqlite3.connect(db_path)
            self.read_conn.row_factory = sqlite3.Row
            logger.info(f"✅ SQLite initialized: {db_path}")
        except Exception as e:
            logger.error(f"Failed to initialize SQLite: {e}")
            raise
    
    def _init_postgresql(self):
        """Initialize PostgreSQL connections with connection pooling"""
        master_url = os.getenv('DATABASE_URL')
        read_url = os.getenv('DATABASE_READ_URL', master_url)
        
        try:
            # Parse PostgreSQL URLs
            master_params = self._parse_postgres_url(master_url)
            read_params = self._parse_postgres_url(read_url)
            
            # Create connection pools
            self.pg_pool_master = psycopg2.pool.SimpleConnectionPool(
                1, 10,
                **master_params
            )
            self.pg_pool_read = psycopg2.pool.SimpleConnectionPool(
                1, 20,  # More read connections
                **read_params
            )
            
            logger.info(f"✅ PostgreSQL initialized with master-slave replication")
            logger.info(f"  Master: {master_params.get('host')}:{master_params.get('port')}")
            logger.info(f"  Read: {read_params.get('host')}:{read_params.get('port')}")
        except Exception as e:
            logger.error(f"Failed to initialize PostgreSQL: {e}")
            raise
    
    def _parse_postgres_url(self, url: str) -> Dict:
        """Parse PostgreSQL URL to params"""
        # postgresql://user:password@host:port/database
        from urllib.parse import urlparse
        
        parsed = urlparse(url)
        return {
            'user': parsed.username or 'postgres',
            'password': parsed.password or 'postgres',
            'host': parsed.hostname or 'localhost',
            'port': parsed.port or 5432,
            'database': parsed.path.lstrip('/') or 'fileshare'
        }
    
    @contextmanager
    def get_master_connection(self):
        """Get master connection for writes"""
        try:
            if self.db_type == 'postgresql':
                conn = self.pg_pool_master.getconn()
            else:
                conn = self.master_conn
            
            yield DatabaseConnection(self.db_type, conn)
        finally:
            if self.db_type == 'postgresql' and conn:
                self.pg_pool_master.putconn(conn)
    
    @contextmanager
    def get_read_connection(self):
        """Get read connection (can be slave in master-slave setup)"""
        try:
            if self.db_type == 'postgresql':
                conn = self.pg_pool_read.getconn()
            else:
                conn = self.read_conn
            
            yield DatabaseConnection(self.db_type, conn)
        finally:
            if self.db_type == 'postgresql' and conn:
                self.pg_pool_read.putconn(conn)
    
    def execute_write(self, query: str, params: tuple = None) -> bool:
        """Execute write query on master"""
        try:
            with self.get_master_connection() as conn:
                conn.execute(query, params)
            return True
        except Exception as e:
            logger.error(f"Write execution failed: {e}")
            return False
    
    def execute_read(self, query: str, params: tuple = None) -> List[Dict]:
        """Execute read query on replica (slave)"""
        try:
            with self.get_read_connection() as conn:
                return conn.fetch_all(query, params)
        except Exception as e:
            logger.error(f"Read execution failed: {e}")
            return []
    
    def get_replication_status(self) -> Dict:
        """Get database replication status"""
        try:
            if self.db_type != 'postgresql':
                return {'status': 'sqlite', 'replication': 'N/A'}
            
            with self.get_master_connection() as master:
                # Query master status
                master_info = master.fetch_one("""
                    SELECT 
                        pg_is_in_recovery() as in_recovery,
                        now() as master_time,
                        pg_current_wal_lsn() as wal_lsn
                """)
            
            with self.get_read_connection() as read:
                # Query replica status
                read_info = read.fetch_one("""
                    SELECT 
                        pg_is_in_recovery() as in_recovery,
                        now() as replica_time,
                        pg_last_wal_receive_lsn() as wal_receive_lsn,
                        pg_last_wal_replay_lsn() as wal_replay_lsn
                """)
            
            return {
                'status': 'healthy',
                'master': master_info,
                'replica': read_info,
                'db_type': 'postgresql'
            }
        except Exception as e:
            logger.error(f"Error getting replication status: {e}")
            return {'status': 'error', 'message': str(e)}
    
    def close(self):
        """Close all connections"""
        if self.db_type == 'postgresql':
            if self.pg_pool_master:
                self.pg_pool_master.closeall()
            if self.pg_pool_read:
                self.pg_pool_read.closeall()
        else:
            if self.master_conn:
                self.master_conn.close()
            if self.read_conn:
                self.read_conn.close()
        
        logger.info("Database connections closed")


# Global database manager instance
_db_manager = None


def get_db_manager() -> DatabaseManager:
    """Get or create global database manager"""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager


def init_db() -> DatabaseManager:
    """Initialize database manager"""
    return get_db_manager()
