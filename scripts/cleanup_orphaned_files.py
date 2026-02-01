"""
Cleanup Orphaned Files Script
Dọn dẹp file thừa trên các node (file không có metadata trong database)
Chỉ giữ lại file có trong database (primary_node)
"""

import os
import sys
import logging
import requests
from typing import Dict, List, Set

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
NODE_URLS = {
    'node1': 'http://localhost:8001',
    'node2': 'http://localhost:8002',
    'node3': 'http://localhost:8003',
}

DATABASE_PATH = os.path.join(os.path.dirname(__file__), '..', 'fileshare.db')


def get_db_filenames() -> Dict[str, Set[str]]:
    """
    Get all filenames from database grouped by node
    Returns: {'node1': {'file1.jpg', 'file2.jpg'}, 'node2': {...}, ...}
    """
    try:
        import sqlite3
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Check if files table exists
        cursor.execute('''
            SELECT name FROM sqlite_master WHERE type='table' AND name='files'
        ''')
        
        if not cursor.fetchone():
            logger.warning("Files table does not exist in database. Database may not be initialized.")
            return {}
        
        # Query files grouped by primary_node
        cursor.execute('''
            SELECT primary_node, filename FROM files WHERE deleted_at IS NULL
        ''')
        
        db_files = {}
        for row in cursor.fetchall():
            node_id = row['primary_node']
            filename = row['filename']
            if node_id not in db_files:
                db_files[node_id] = set()
            db_files[node_id].add(filename)
        
        conn.close()
        logger.info(f"Database files: {db_files}")
        return db_files
    
    except Exception as e:
        logger.error(f"Failed to read database: {e}")
        return {}


def get_node_filenames(node_id: str, node_url: str) -> Set[str]:
    """
    Get all filenames from a storage node via API
    Returns: {'file1.jpg', 'file2.jpg', ...}
    """
    try:
        response = requests.get(f"{node_url}/files", timeout=10)
        response.raise_for_status()
        data = response.json()
        
        filenames = set()
        if 'files' in data:
            for file_info in data['files']:
                filenames.add(file_info['filename'])
        
        logger.info(f"{node_id} files: {len(filenames)} files - {filenames}")
        return filenames
    
    except Exception as e:
        logger.error(f"Failed to get files from {node_id}: {e}")
        return set()


def delete_orphaned_file(node_id: str, node_url: str, filename: str) -> bool:
    """
    Delete orphaned file from a storage node
    """
    try:
        response = requests.delete(f"{node_url}/delete/{filename}", timeout=10)
        response.raise_for_status()
        logger.info(f"Deleted orphaned file from {node_id}: {filename}")
        return True
    
    except Exception as e:
        logger.error(f"Failed to delete file {filename} from {node_id}: {e}")
        return False


def cleanup_orphaned_files(dry_run: bool = True) -> None:
    """
    Main cleanup function
    dry_run: True = only print what would be deleted, False = actually delete
    """
    logger.info(f"Starting cleanup (dry_run={dry_run})...")
    
    # Get database files
    db_files = get_db_filenames()
    
    # If database is empty or not initialized, ask user confirmation
    if not db_files:
        logger.warning("Database has no file metadata. This could mean:")
        logger.warning("1. Database is not initialized")
        logger.warning("2. No files have been uploaded yet")
        logger.warning("Skipping cleanup to prevent accidental data loss.")
        logger.info("Please check your database and try again.")
        return
    
    # Check each node
    total_deleted = 0
    for node_id, node_url in NODE_URLS.items():
        logger.info(f"\n--- Checking {node_id} ---")
        
        # Get files from node
        node_files = get_node_filenames(node_id, node_url)
        
        # Find orphaned files (in node but not in database)
        db_node_files = db_files.get(node_id, set())
        orphaned_files = node_files - db_node_files
        
        if orphaned_files:
            logger.warning(f"Found {len(orphaned_files)} orphaned files on {node_id}: {orphaned_files}")
            
            for filename in orphaned_files:
                if dry_run:
                    logger.info(f"[DRY RUN] Would delete: {node_id}/{filename}")
                else:
                    success = delete_orphaned_file(node_id, node_url, filename)
                    if success:
                        total_deleted += 1
        else:
            logger.info(f"No orphaned files found on {node_id}")
    
    logger.info(f"\n--- Cleanup complete ---")
    if dry_run:
        logger.info("Dry run completed. No files were actually deleted.")
    else:
        logger.info(f"Deleted {total_deleted} orphaned files.")


if __name__ == '__main__':
    # Default: dry_run = True (only print)
    # To actually delete: python cleanup_orphaned_files.py --delete
    dry_run = '--delete' not in sys.argv
    
    if dry_run:
        logger.info("Running in DRY RUN mode. Pass --delete flag to actually delete files.")
    
    cleanup_orphaned_files(dry_run=dry_run)
