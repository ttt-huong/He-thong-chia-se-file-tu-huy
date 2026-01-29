"""
Initialize Storage Nodes in Database
Simple script using sqlite3 directly
"""

import sqlite3
import os
import sys
from datetime import datetime

# Add parent directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

DB_PATH = "fileshare.db"


def init_storage_nodes():
    """Initialize 3 storage nodes in database"""
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Storage node configurations
    nodes = [
        {
            'node_id': 'node1',
            'host': 'localhost',
            'port': 8001,
            'path': 'storage/node1',
            'total_space': 107374182400,  # 100GB in bytes
        },
        {
            'node_id': 'node2',
            'host': 'localhost',
            'port': 8002,
            'path': 'storage/node2',
            'total_space': 107374182400,  # 100GB in bytes
        },
        {
            'node_id': 'node3',
            'host': 'localhost',
            'port': 8003,
            'path': 'storage/node3',
            'total_space': 107374182400,  # 100GB in bytes
        }
    ]
    
    print("=" * 60)
    print("Initializing Storage Nodes...")
    print("=" * 60)
    
    for node in nodes:
        # Create storage directory
        node_path = node['path']
        os.makedirs(node_path, exist_ok=True)
        print(f"✓ Created directory: {node_path}")
        
        # Check if node exists
        cursor.execute("SELECT node_id FROM storage_nodes WHERE node_id = ?", (node['node_id'],))
        existing = cursor.fetchone()
        
        if existing:
            # Update existing node
            cursor.execute("""
                UPDATE storage_nodes 
                SET is_online = 1,
                    last_heartbeat = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE node_id = ?
            """, (node['node_id'],))
            print(f"✓ Updated node: {node['node_id']} (already exists)")
        else:
            # Insert new node
            cursor.execute("""
                INSERT INTO storage_nodes 
                (node_id, host, port, path, is_online, total_space, used_space, file_count, 
                 last_heartbeat, error_count, created_at, updated_at)
                VALUES (?, ?, ?, ?, 1, ?, 0, 0, CURRENT_TIMESTAMP, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """, (node['node_id'], node['host'], node['port'], node['path'], node['total_space']))
            print(f"✓ Created node: {node['node_id']} ({node['host']}:{node['port']})")
    
    conn.commit()
    
    # Print summary
    cursor.execute("SELECT node_id, host, port, path, is_online, total_space, used_space FROM storage_nodes")
    all_nodes = cursor.fetchall()
    
    print("\n" + "=" * 60)
    print(f"Storage Nodes Summary ({len(all_nodes)} nodes)")
    print("=" * 60)
    for row in all_nodes:
        node_id, host, port, path, is_online, total_space, used_space = row
        status = "🟢 ONLINE" if is_online else "🔴 OFFLINE"
        free_gb = (total_space - used_space) / (1024**3)
        print(f"{status} {node_id:10} {host}:{port:5}  Free: {free_gb:.1f}GB  Path: {path}")
    print("=" * 60)
    
    conn.close()
    print("\n✅ Storage nodes initialized successfully!\n")


if __name__ == '__main__':
    init_storage_nodes()
