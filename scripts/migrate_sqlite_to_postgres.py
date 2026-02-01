"""
Data Migration: SQLite to PostgreSQL
Phase 4.3: Migrate FileShareSystem data from SQLite to PostgreSQL cluster
"""

import sqlite3
import psycopg2
import os
import logging
from datetime import datetime
from typing import Dict, List, Tuple, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DataMigration:
    """Migrate data from SQLite to PostgreSQL"""
    
    def __init__(self, sqlite_path: str = "fileshare.db"):
        self.sqlite_path = sqlite_path
        self.pg_host = os.getenv("DATABASE_URL", "postgres-master")
        self.pg_user = os.getenv("POSTGRES_USER", "postgres")
        self.pg_password = os.getenv("POSTGRES_PASSWORD", "postgres_secure_pass")
        self.pg_db = os.getenv("POSTGRES_DB", "fileshare")
        self.pg_port = int(os.getenv("POSTGRES_PORT", 5432))
        
        self.sqlite_conn = None
        self.pg_conn = None
        self.migration_log = []
    
    def connect_sqlite(self) -> bool:
        """Connect to SQLite database"""
        try:
            if not os.path.exists(self.sqlite_path):
                logger.warning(f"SQLite database not found: {self.sqlite_path}")
                return False
            
            self.sqlite_conn = sqlite3.connect(self.sqlite_path)
            self.sqlite_conn.row_factory = sqlite3.Row
            logger.info(f"Connected to SQLite: {self.sqlite_path}")
            return True
        except Exception as e:
            logger.error(f"SQLite connection error: {e}")
            return False
    
    def connect_postgres(self) -> bool:
        """Connect to PostgreSQL database"""
        try:
            self.pg_conn = psycopg2.connect(
                host=self.pg_host,
                user=self.pg_user,
                password=self.pg_password,
                database=self.pg_db,
                port=self.pg_port,
                connect_timeout=10
            )
            logger.info(f"Connected to PostgreSQL: {self.pg_host}:{self.pg_port}/{self.pg_db}")
            return True
        except Exception as e:
            logger.error(f"PostgreSQL connection error: {e}")
            return False
    
    def close_connections(self):
        """Close both database connections"""
        if self.sqlite_conn:
            self.sqlite_conn.close()
        if self.pg_conn:
            self.pg_conn.close()
    
    def get_sqlite_table_count(self, table_name: str) -> int:
        """Get row count from SQLite table"""
        try:
            cursor = self.sqlite_conn.cursor()
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            return cursor.fetchone()[0]
        except Exception as e:
            logger.error(f"Error getting count from {table_name}: {e}")
            return 0
    
    def migrate_table(self, table_name: str, columns: List[str]) -> Dict[str, Any]:
        """Migrate a single table from SQLite to PostgreSQL"""
        logger.info(f"Migrating table: {table_name}")
        
        result = {
            "table": table_name,
            "status": "pending",
            "total_rows": 0,
            "migrated_rows": 0,
            "error": None
        }
        
        try:
            # Get data from SQLite
            sqlite_cursor = self.sqlite_conn.cursor()
            sqlite_cursor.execute(f"SELECT * FROM {table_name}")
            rows = sqlite_cursor.fetchall()
            result["total_rows"] = len(rows)
            
            if len(rows) == 0:
                logger.info(f"No rows to migrate in {table_name}")
                result["status"] = "completed"
                return result
            
            # Insert into PostgreSQL
            pg_cursor = self.pg_conn.cursor()
            placeholders = ", ".join(["%s"] * len(columns))
            insert_sql = f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({placeholders})"
            
            for row in rows:
                try:
                    # Convert SQLite row to tuple
                    values = tuple(row[col] for col in columns)
                    # Convert INTEGER columns 0/1 to boolean for PostgreSQL
                    values = self._convert_types(table_name, columns, values)
                    pg_cursor.execute(insert_sql, values)
                    result["migrated_rows"] += 1
                except Exception as e:
                    logger.warning(f"Error inserting row into {table_name}: {e}")
                    if result["migrated_rows"] == 0:
                        result["error"] = str(e)
                        result["status"] = "failed"
                        pg_cursor.close()
                        return result
            
            self.pg_conn.commit()
            pg_cursor.close()
            result["status"] = "completed"
            logger.info(f"Migrated {result['migrated_rows']}/{result['total_rows']} rows from {table_name}")
            
        except Exception as e:
            logger.error(f"Error migrating {table_name}: {e}")
            result["status"] = "failed"
            result["error"] = str(e)
        
        return result
    
    def _convert_types(self, table_name: str, columns: List[str], values: Tuple) -> Tuple:
        """Convert SQLite types to PostgreSQL types"""
        converted = []
        
        # Define boolean columns per table
        bool_columns = {
            "files": ["is_compressed", "has_thumbnail", "is_deleted"],
            "storage_nodes": ["is_online"]
        }
        
        bool_cols = bool_columns.get(table_name, [])
        
        for i, (col, val) in enumerate(zip(columns, values)):
            if col in bool_cols and isinstance(val, int):
                # Convert 0/1 to False/True
                converted.append(bool(val))
            else:
                converted.append(val)
        
        return tuple(converted)
    
    def migrate_all(self) -> Dict[str, Any]:
        """Execute full migration"""
        logger.info("Starting full data migration from SQLite to PostgreSQL")
        
        if not self.connect_sqlite():
            logger.error("Failed to connect to SQLite")
            return {"status": "failed", "error": "SQLite connection failed"}
        
        if not self.connect_postgres():
            logger.error("Failed to connect to PostgreSQL")
            self.close_connections()
            return {"status": "failed", "error": "PostgreSQL connection failed"}
        
        # Define tables and columns to migrate
        tables_to_migrate = {
            "storage_nodes": ["node_id", "host", "port", "path", "is_online", 
                            "total_space", "used_space", "file_count", 
                            "last_heartbeat", "error_count", "created_at", "updated_at"],
            "files": ["id", "filename", "original_name", "file_size", "mime_type",
                     "primary_node", "replica_nodes", "download_limit", "downloads_left",
                     "created_at", "expires_at", "checksum", "is_compressed", 
                     "has_thumbnail", "is_deleted", "deleted_at"],
            "tasks": ["id", "file_id", "task_type", "status", "result",
                     "error_message", "created_at", "started_at", "completed_at", "retry_count"],
            "replication_logs": ["id", "file_id", "source_node", "target_node",
                               "status", "error_message", "created_at", "completed_at", "duration_seconds"]
        }
        
        migration_results = []
        total_rows_migrated = 0
        
        for table_name, columns in tables_to_migrate.items():
            # Check if table exists in SQLite
            try:
                self.get_sqlite_table_count(table_name)
            except Exception:
                logger.warning(f"Table {table_name} not found in SQLite, skipping")
                continue
            
            result = self.migrate_table(table_name, columns)
            migration_results.append(result)
            total_rows_migrated += result["migrated_rows"]
        
        self.close_connections()
        
        return {
            "status": "completed",
            "timestamp": datetime.now().isoformat(),
            "total_tables_migrated": len(migration_results),
            "total_rows_migrated": total_rows_migrated,
            "tables": migration_results
        }
    
    def validate_migration(self) -> Dict[str, Any]:
        """Validate migration by comparing row counts"""
        logger.info("Validating migration...")
        
        if not self.connect_sqlite():
            return {"status": "failed", "error": "SQLite connection failed"}
        
        if not self.connect_postgres():
            self.close_connections()
            return {"status": "failed", "error": "PostgreSQL connection failed"}
        
        validation_results = []
        all_valid = True
        
        tables = ["storage_nodes", "files", "tasks", "replication_logs"]
        
        for table_name in tables:
            try:
                # Get SQLite count
                sqlite_cursor = self.sqlite_conn.cursor()
                sqlite_cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                sqlite_count = sqlite_cursor.fetchone()[0]
                
                # Get PostgreSQL count
                pg_cursor = self.pg_conn.cursor()
                pg_cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                pg_count = pg_cursor.fetchone()[0]
                pg_cursor.close()
                
                match = sqlite_count == pg_count
                validation_results.append({
                    "table": table_name,
                    "sqlite_count": sqlite_count,
                    "postgresql_count": pg_count,
                    "match": match
                })
                
                if not match:
                    all_valid = False
                    logger.warning(f"Row count mismatch for {table_name}: SQLite={sqlite_count}, PostgreSQL={pg_count}")
                else:
                    logger.info(f"✓ {table_name}: {pg_count} rows")
                
            except Exception as e:
                logger.error(f"Validation error for {table_name}: {e}")
                all_valid = False
        
        self.close_connections()
        
        return {
            "status": "completed" if all_valid else "warning",
            "all_valid": all_valid,
            "tables": validation_results
        }


def main():
    """Main migration execution"""
    migrator = DataMigration()
    
    # Execute migration
    logger.info("=" * 60)
    logger.info("SQLite to PostgreSQL Data Migration")
    logger.info("=" * 60)
    
    result = migrator.migrate_all()
    
    logger.info("\n" + "=" * 60)
    logger.info("MIGRATION RESULTS")
    logger.info("=" * 60)
    logger.info(f"Status: {result['status']}")
    logger.info(f"Total tables migrated: {result['total_tables_migrated']}")
    logger.info(f"Total rows migrated: {result['total_rows_migrated']}")
    
    for table in result['tables']:
        logger.info(f"\n{table['table']}:")
        logger.info(f"  Total rows: {table['total_rows']}")
        logger.info(f"  Migrated: {table['migrated_rows']}")
        logger.info(f"  Status: {table['status']}")
        if table['error']:
            logger.info(f"  Error: {table['error']}")
    
    # Validate migration
    logger.info("\n" + "=" * 60)
    logger.info("VALIDATION")
    logger.info("=" * 60)
    
    validation = migrator.validate_migration()
    logger.info(f"Validation status: {validation['status']}")
    
    for table_val in validation['tables']:
        match_symbol = "✓" if table_val['match'] else "✗"
        logger.info(f"{match_symbol} {table_val['table']}: SQLite={table_val['sqlite_count']}, "
                   f"PostgreSQL={table_val['postgresql_count']}")
    
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
