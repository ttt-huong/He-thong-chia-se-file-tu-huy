"""
Database Initialization Script
Create tables and seed initial storage nodes
"""

import os
import sys
from datetime import datetime

# Add parent directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.middleware.models import Base, StorageNode, init_db
from src.config.settings import STORAGE_NODES, DATABASE_URL
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def init_database():
    """
    Initialize database schema and seed data
    """
    try:
        logger.info("Initializing database...")
        
        # Create engine and session
        engine, Session = init_db(DATABASE_URL)
        session = Session()
        
        # Create all tables
        Base.metadata.create_all(engine)
        logger.info("Database tables created successfully")
        
        # Seed storage nodes
        logger.info("Seeding storage nodes...")
        
        for node_id, node_config in STORAGE_NODES.items():
            # Check if node already exists
            existing_node = session.query(StorageNode).filter(
                StorageNode.node_id == node_id
            ).first()
            
            if existing_node:
                logger.info(f"Node {node_id} already exists, skipping")
                continue
            
            # Create storage directory if not exists
            node_path = node_config['path']
            os.makedirs(node_path, exist_ok=True)
            logger.info(f"Created storage directory: {node_path}")
            
            # Get disk space (estimate 100GB per node)
            total_space = 100 * (1024 ** 3)  # 100GB in bytes
            
            # Create node record
            new_node = StorageNode(
                node_id=node_id,
                host=node_config['host'],
                port=node_config['port'],
                path=str(node_path),  # Convert WindowsPath to string
                is_online=True,
                total_space=total_space,
                used_space=0,
                file_count=0,
                last_heartbeat=datetime.utcnow()  # Set current timestamp
            )
            
            session.add(new_node)
            logger.info(f"Added storage node: {node_id} ({node_config['host']}:{node_config['port']})")
        
        session.commit()
        logger.info("Storage nodes seeded successfully")
        
        # Print summary
        all_nodes = session.query(StorageNode).all()
        logger.info(f"\n{'='*50}")
        logger.info(f"Database initialized successfully!")
        logger.info(f"Total storage nodes: {len(all_nodes)}")
        for node in all_nodes:
            logger.info(f"  - {node.node_id}: {node.host}:{node.port} ({node.path})")
        logger.info(f"{'='*50}\n")
        
    except Exception as e:
        logger.error(f"Error initializing database: {e}", exc_info=True)
        raise


if __name__ == '__main__':
    init_database()
