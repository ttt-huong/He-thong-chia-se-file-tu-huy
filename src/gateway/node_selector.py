"""
Node Selector - Chọn Storage Node tối ưu
Chương 7: Replication & Fault Tolerance
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict
from src.middleware.models import StorageNode

logger = logging.getLogger(__name__)


class NodeSelector:
    """
    Chọn storage node tốt nhất dựa trên:
    - Available space
    - Node health status
    - Last heartbeat
    - Error count
    """
    
    def __init__(self, db_session):
        self.db_session = db_session
    
    def get_healthy_nodes(self, min_free_space_mb: int = 100) -> List[StorageNode]:
        """
        Lấy danh sách các node khỏe mạnh
        
        Args:
            min_free_space_mb: Minimum free space required (MB)
        
        Returns:
            List of healthy storage nodes
        """
        try:
            # Node considered healthy if:
            # 1. is_online = True
            # 2. last_heartbeat within 60 seconds
            # 3. error_count < 10
            # 4. available space > min_free_space_mb
            
            heartbeat_threshold = datetime.utcnow() - timedelta(seconds=60)
            min_free_space_bytes = min_free_space_mb * 1024 * 1024
            
            nodes = self.db_session.query(StorageNode).filter(
                StorageNode.is_online == True,
                StorageNode.last_heartbeat >= heartbeat_threshold,
                StorageNode.error_count < 10,
                (StorageNode.total_space - StorageNode.used_space) >= min_free_space_bytes
            ).order_by(
                StorageNode.error_count.asc(),  # Prefer nodes with fewer errors
                (StorageNode.total_space - StorageNode.used_space).desc()  # Prefer nodes with more space
            ).all()
            
            logger.info(f"Found {len(nodes)} healthy nodes")
            return nodes
        
        except Exception as e:
            logger.error(f"Error getting healthy nodes: {e}")
            return []
    
    def select_primary_node(self, file_size: int) -> Optional[StorageNode]:
        """
        Chọn node chính để lưu file
        
        Args:
            file_size: Size of file in bytes
        
        Returns:
            Selected StorageNode or None if no suitable node
        """
        try:
            # Get nodes with enough space for the file
            min_space_mb = (file_size / (1024 * 1024)) + 50  # File size + 50MB buffer
            healthy_nodes = self.get_healthy_nodes(min_free_space_mb=int(min_space_mb))
            
            if not healthy_nodes:
                logger.error("No healthy nodes available for file storage")
                # Try with all nodes and update heartbeat
                all_nodes = self.db_session.query(StorageNode).all()
                for node in all_nodes:
                    node.last_heartbeat = datetime.utcnow()
                self.db_session.commit()
                # Try again
                healthy_nodes = self.get_healthy_nodes(min_free_space_mb=int(min_space_mb))
                if not healthy_nodes:
                    logger.error("Still no healthy nodes after heartbeat update")
                    return None
            
            # Select node with most available space and lowest error count
            selected_node = healthy_nodes[0]
            
            # Update heartbeat on selected node
            selected_node.last_heartbeat = datetime.utcnow()
            self.db_session.commit()
            
            logger.info(f"Selected primary node: {selected_node.node_id} "
                       f"(available: {(selected_node.total_space - selected_node.used_space) / (1024**3):.2f} GB)")
            
            return selected_node
        
        except Exception as e:
            logger.error(f"Error selecting primary node: {e}")
            return None
    
    def select_replica_nodes(self, primary_node: StorageNode, count: int, file_size: int) -> List[StorageNode]:
        """
        Chọn các node để replicate file
        
        Args:
            primary_node: The primary storage node
            count: Number of replicas needed
            file_size: Size of file in bytes
        
        Returns:
            List of replica StorageNodes
        """
        try:
            min_space_mb = (file_size / (1024 * 1024)) + 50
            healthy_nodes = self.get_healthy_nodes(min_free_space_mb=int(min_space_mb))
            
            # Exclude primary node
            replica_candidates = [node for node in healthy_nodes if node.node_id != primary_node.node_id]
            
            # Select up to 'count' nodes
            selected_replicas = replica_candidates[:count]
            
            logger.info(f"Selected {len(selected_replicas)} replica nodes for file")
            return selected_replicas
        
        except Exception as e:
            logger.error(f"Error selecting replica nodes: {e}")
            return []
    
    def get_node_by_id(self, node_id: str) -> Optional[StorageNode]:
        """
        Get node by ID
        
        Args:
            node_id: Storage node identifier
        
        Returns:
            StorageNode or None
        """
        try:
            node = self.db_session.query(StorageNode).filter(
                StorageNode.node_id == node_id
            ).first()
            return node
        except Exception as e:
            logger.error(f"Error getting node by ID {node_id}: {e}")
            return None
    
    def mark_node_error(self, node_id: str):
        """
        Increment error count for a node
        Mark node as offline if too many errors
        
        Args:
            node_id: Storage node identifier
        """
        try:
            node = self.get_node_by_id(node_id)
            if node:
                node.error_count += 1
                
                # Mark offline if too many errors
                if node.error_count >= 10:
                    node.is_online = False
                    logger.warning(f"Node {node_id} marked offline due to errors")
                
                self.db_session.commit()
                logger.info(f"Node {node_id} error count: {node.error_count}")
        
        except Exception as e:
            logger.error(f"Error marking node error: {e}")
            self.db_session.rollback()
    
    def update_node_stats(self, node_id: str, used_space: int, file_count: int):
        """
        Update node statistics after file operation
        
        Args:
            node_id: Storage node identifier
            used_space: New used space value
            file_count: New file count
        """
        try:
            node = self.get_node_by_id(node_id)
            if node:
                node.used_space = used_space
                node.file_count = file_count
                node.last_heartbeat = datetime.utcnow()
                self.db_session.commit()
                logger.debug(f"Updated stats for node {node_id}")
        
        except Exception as e:
            logger.error(f"Error updating node stats: {e}")
            self.db_session.rollback()
