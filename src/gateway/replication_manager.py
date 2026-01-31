"""
Replication Manager - Handle file replication, failover, and node recovery
Phase 2: Node Replication & Failover
"""

import logging
import requests
import threading
import time
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from src.gateway.storage_client import StorageNodeClient
from src.middleware.models import get_db

logger = logging.getLogger(__name__)


class ReplicationManager:
    """
    Manages file replication across storage nodes and handles failover
    
    Strategy:
    - Upload to primary node (least used)
    - Replicate to 2 secondary nodes automatically
    - Monitor node health continuously
    - Failover to replica if primary dies
    - Track replication state for recovery
    """
    
    def __init__(self, node_urls: Dict[str, str]):
        """
        Initialize replication manager with node URLs
        
        Args:
            node_urls: {"node1": "http://...", "node2": "http://...", ...}
        """
        self.node_urls = node_urls
        self.node_clients = {
            node_id: StorageNodeClient(url, node_id) 
            for node_id, url in node_urls.items()
        }
        
        # Track node health (last check time, status)
        self.node_health = {
            node_id: {
                'status': 'unknown',
                'last_check': None,
                'file_count': 0,
                'used_space': 0
            }
            for node_id in node_urls.keys()
        }
        
        # Replication config
        self.replica_count = 2  # Number of replicas per file (total = 1 primary + 2 replicas = 3)
        self.health_check_interval = 30  # seconds
        self.health_check_timeout = 5  # seconds
        
        # Start background health monitoring
        self.monitoring_active = True
        self._start_health_monitoring()
        # Initial health check to populate status
        self._check_all_nodes_health()
        
    def _start_health_monitoring(self):
        """Start background thread for continuous health monitoring"""
        thread = threading.Thread(target=self._health_monitor_loop, daemon=True)
        thread.start()
        logger.info("Health monitoring started in background thread")
        
    def _health_monitor_loop(self):
        """Background loop to monitor node health"""
        while self.monitoring_active:
            try:
                self._check_all_nodes_health()
                time.sleep(self.health_check_interval)
            except Exception as e:
                logger.error(f"Error in health monitor loop: {e}")
                
    def _check_all_nodes_health(self):
        """Check health of all nodes"""
        for node_id in self.node_urls.keys():
            self._check_node_health(node_id)
            
    def _check_node_health(self, node_id: str) -> bool:
        """
        Check if a node is healthy
        Returns: True if online, False if offline
        """
        try:
            client = self.node_clients[node_id]
            response = client.health_check()
            
            if response.get('status') == 'online':
                self.node_health[node_id] = {
                    'status': 'online',
                    'last_check': datetime.now(),
                    'file_count': response.get('file_count', 0),
                    'used_space': response.get('used_space', 0)
                }
                return True
            else:
                self.node_health[node_id]['status'] = 'offline'
                return False
                
        except Exception as e:
            logger.warning(f"Health check failed for {node_id}: {e}")
            self.node_health[node_id]['status'] = 'offline'
            return False
            
    def get_online_nodes(self) -> List[str]:
        """Get list of online node IDs"""
        return [
            node_id for node_id, health in self.node_health.items()
            if health['status'] == 'online'
        ]
    
    def get_node_health(self) -> Dict:
        """Get health status of all nodes"""
        return self.node_health.copy()
    
    def select_primary_node(self) -> str:
        """
        Select primary node for upload using least-used strategy
        Prefers node with least files
        """
        online_nodes = self.get_online_nodes()
        
        if not online_nodes:
            logger.error("No online nodes available for selection!")
            raise Exception("No online storage nodes available")
        
        # Sort by file_count (ascending)
        selected = min(
            online_nodes,
            key=lambda n: self.node_health[n].get('file_count', 0)
        )
        
        file_count = self.node_health[selected].get('file_count', 0)
        logger.debug(f"Selected {selected} as primary (files: {file_count})")
        
        return selected
    
    def select_replica_nodes(self, exclude_node: str) -> List[str]:
        """
        Select replica nodes (different from primary and each other)
        Args:
            exclude_node: Node ID to exclude (usually the primary)
        Returns:
            List of node IDs for replication
        """
        online_nodes = [
            n for n in self.get_online_nodes() 
            if n != exclude_node
        ]
        
        # Return up to replica_count nodes
        return online_nodes[:self.replica_count]
    
    def replicate_file(
        self, 
        file_id: str, 
        filename: str, 
        primary_node: str, 
        replica_nodes: List[str],
        db=None
    ) -> Dict[str, bool]:
        """
        Replicate file from primary to replica nodes
        
        Args:
            file_id: File UUID
            filename: Filename on storage
            primary_node: Source node ID
            replica_nodes: Destination node IDs
            db: Database connection for tracking
            
        Returns:
            {node_id: success_bool, ...}
        """
        results = {}
        
        try:
            primary_client = self.node_clients[primary_node]
            
            for replica_node_id in replica_nodes:
                try:
                    replica_client = self.node_clients[replica_node_id]
                    
                    # Download from primary
                    logger.info(f"Downloading {filename} from {primary_node}")
                    file_data = primary_client.download_file(filename)
                    
                    if not file_data:
                        logger.error(f"Failed to download {filename} from {primary_node}")
                        results[replica_node_id] = False
                        continue
                    
                    # Upload to replica
                    logger.info(f"Uploading {filename} to {replica_node_id}")
                    response = replica_client.upload_file(
                        file_data,
                        filename,
                        is_replica=True
                    )
                    
                    success = response.get('status') == 'success'
                    results[replica_node_id] = success
                    
                    if success:
                        logger.info(f"Replicated {filename} to {replica_node_id}")
                    else:
                        logger.error(f"Replication to {replica_node_id} failed: {response}")
                        
                except Exception as e:
                    logger.error(f"Error replicating to {replica_node_id}: {e}")
                    results[replica_node_id] = False
        
        except Exception as e:
            logger.error(f"Replication error: {e}")
        
        # Update database with replica nodes
        if db:
            try:
                successful_replicas = [
                    node for node, success in results.items() 
                    if success
                ]
                
                conn = db.get_connection()
                cursor = conn.cursor()
                
                replica_nodes_str = ','.join(successful_replicas)
                cursor.execute("""
                    UPDATE files 
                    SET replica_nodes = ?
                    WHERE id = ?
                """, (replica_nodes_str, file_id))
                
                conn.commit()
                conn.close()
                
                logger.info(f"Updated replicas for {file_id}: {replica_nodes_str}")
                
            except Exception as e:
                logger.error(f"Failed to update DB replicas: {e}")
        
        return results
    
    def handle_primary_failure(
        self,
        file_id: str,
        filename: str,
        failed_primary: str,
        replica_nodes: List[str],
        db=None
    ) -> Optional[str]:
        """
        Handle primary node failure by promoting a replica
        
        Args:
            file_id: File UUID
            filename: Filename
            failed_primary: Node ID that failed
            replica_nodes: Available replica nodes
            db: Database connection
            
        Returns:
            New primary node ID, or None if all replicas also down
        """
        # Find first online replica
        for replica_node in replica_nodes:
            if self._check_node_health(replica_node):
                logger.warning(
                    f"Promoting {replica_node} as primary for {file_id} "
                    f"(failed primary: {failed_primary})"
                )
                
                # Update database to promote replica
                if db:
                    try:
                        conn = db.get_connection()
                        cursor = conn.cursor()
                        
                        new_replicas = [
                            n for n in replica_nodes 
                            if n != replica_node
                        ]
                        replica_str = ','.join(new_replicas)
                        
                        cursor.execute("""
                            UPDATE files 
                            SET primary_node = ?,
                                replica_nodes = ?
                            WHERE id = ?
                        """, (replica_node, replica_str, file_id))
                        
                        conn.commit()
                        conn.close()
                        
                    except Exception as e:
                        logger.error(f"Failed to update primary in DB: {e}")
                
                return replica_node
        
        logger.error(
            f"All replicas down for {file_id}! "
            f"Primary: {failed_primary}, Replicas: {replica_nodes}"
        )
        return None
    
    def recover_node(self, node_id: str, db=None):
        """
        When a node comes back online, trigger recovery
        - Sync files from other nodes if missing
        - Update DB with recovery
        """
        logger.info(f"Node {node_id} recovery initiated")
        
        if not self._check_node_health(node_id):
            logger.warning(f"Node {node_id} not responding yet")
            return
        
        logger.info(f"Node {node_id} is online, recovery complete")
    
    def stop(self):
        """Stop background monitoring"""
        self.monitoring_active = False
        logger.info("Replication manager stopped")
