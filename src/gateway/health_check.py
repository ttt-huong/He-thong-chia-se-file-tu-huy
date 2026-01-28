"""
Health Check Monitor - Giám sát sức khỏe storage nodes
Chương 7: Fault Tolerance & Self-Healing
"""

import os
import time
import logging
from datetime import datetime, timedelta
from threading import Thread
from typing import List

from src.middleware.models import StorageNode
from src.config.settings import HEALTH_CHECK_INTERVAL

logger = logging.getLogger(__name__)


class HealthCheckMonitor:
    """
    Periodically check health of all storage nodes
    Auto-detect failures and trigger failover
    """
    
    def __init__(self, db_session, check_interval: int = HEALTH_CHECK_INTERVAL):
        self.db_session = db_session
        self.check_interval = check_interval
        self.running = False
        self.monitor_thread = None
    
    def start(self):
        """Start health check monitoring in background thread"""
        if self.running:
            logger.warning("Health check monitor already running")
            return
        
        self.running = True
        self.monitor_thread = Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        logger.info(f"Health check monitor started (interval: {self.check_interval}s)")
    
    def stop(self):
        """Stop health check monitoring"""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        logger.info("Health check monitor stopped")
    
    def _monitor_loop(self):
        """Main monitoring loop"""
        while self.running:
            try:
                self.check_all_nodes()
                time.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"Error in health check loop: {e}", exc_info=True)
                time.sleep(self.check_interval)
    
    def check_all_nodes(self) -> List[dict]:
        """
        Check health of all storage nodes
        
        Returns:
            List of node health status
        """
        try:
            nodes = self.db_session.query(StorageNode).all()
            health_results = []
            
            for node in nodes:
                health_status = self.check_node(node)
                health_results.append(health_status)
                
                # Update node status in database
                if health_status['healthy']:
                    node.is_online = True
                    node.last_heartbeat = datetime.utcnow()
                    # Reset error count if node is healthy
                    if node.error_count > 0:
                        node.error_count = max(0, node.error_count - 1)
                else:
                    node.error_count += 1
                    
                    # Mark offline if too many consecutive failures
                    if node.error_count >= 5:
                        if node.is_online:
                            logger.warning(f"Node {node.node_id} marked OFFLINE due to health check failures")
                            node.is_online = False
            
            self.db_session.commit()
            
            # Log summary
            healthy_count = sum(1 for r in health_results if r['healthy'])
            logger.info(f"Health check completed: {healthy_count}/{len(nodes)} nodes healthy")
            
            return health_results
        
        except Exception as e:
            logger.error(f"Error checking all nodes: {e}", exc_info=True)
            self.db_session.rollback()
            return []
    
    def check_node(self, node: StorageNode) -> dict:
        """
        Check health of a single storage node
        
        Args:
            node: StorageNode to check
        
        Returns:
            Dict with health status
        """
        try:
            # Check 1: Storage path exists and is accessible
            if not os.path.exists(node.path):
                logger.error(f"Node {node.node_id} path does not exist: {node.path}")
                return {
                    'node_id': node.node_id,
                    'healthy': False,
                    'reason': 'Path does not exist',
                    'checks': {
                        'path_exists': False,
                        'path_writable': False,
                        'space_available': False
                    }
                }
            
            # Check 2: Storage path is writable
            test_file = os.path.join(node.path, '.health_check')
            try:
                with open(test_file, 'w') as f:
                    f.write('health_check')
                os.remove(test_file)
                path_writable = True
            except Exception as e:
                logger.error(f"Node {node.node_id} path not writable: {e}")
                path_writable = False
            
            # Check 3: Sufficient space available (at least 1GB)
            try:
                stat = os.statvfs(node.path) if hasattr(os, 'statvfs') else None
                if stat:
                    available_space = stat.f_bavail * stat.f_frsize
                    space_available = available_space > (1024 ** 3)  # 1GB
                else:
                    # Windows: Use shutil
                    import shutil
                    total, used, free = shutil.disk_usage(node.path)
                    space_available = free > (1024 ** 3)
            except Exception as e:
                logger.error(f"Node {node.node_id} cannot check disk space: {e}")
                space_available = False
            
            # Check 4: Last heartbeat not too old (within 5 minutes)
            if node.last_heartbeat:
                heartbeat_age = datetime.utcnow() - node.last_heartbeat
                heartbeat_ok = heartbeat_age < timedelta(minutes=5)
            else:
                heartbeat_ok = False
            
            # Overall health
            healthy = path_writable and space_available
            
            checks = {
                'path_exists': True,
                'path_writable': path_writable,
                'space_available': space_available,
                'heartbeat_ok': heartbeat_ok
            }
            
            if healthy:
                logger.debug(f"Node {node.node_id} is healthy")
            else:
                failed_checks = [k for k, v in checks.items() if not v]
                logger.warning(f"Node {node.node_id} is unhealthy. Failed checks: {failed_checks}")
            
            return {
                'node_id': node.node_id,
                'healthy': healthy,
                'checks': checks,
                'error_count': node.error_count
            }
        
        except Exception as e:
            logger.error(f"Error checking node {node.node_id}: {e}", exc_info=True)
            return {
                'node_id': node.node_id,
                'healthy': False,
                'reason': str(e),
                'checks': {}
            }
    
    def trigger_failover(self, failed_node_id: str):
        """
        Trigger failover for a failed node
        Move files to other healthy nodes
        
        Args:
            failed_node_id: ID of the failed node
        """
        try:
            from src.middleware.models import File
            
            logger.warning(f"Triggering failover for node: {failed_node_id}")
            
            # Get all files where this node is primary
            files_to_migrate = self.db_session.query(File).filter(
                File.primary_node == failed_node_id
            ).all()
            
            if not files_to_migrate:
                logger.info(f"No files to migrate from node {failed_node_id}")
                return
            
            # Get healthy nodes
            healthy_nodes = self.db_session.query(StorageNode).filter(
                StorageNode.is_online == True,
                StorageNode.node_id != failed_node_id
            ).all()
            
            if not healthy_nodes:
                logger.error("No healthy nodes available for failover")
                return
            
            migrated_count = 0
            for file_record in files_to_migrate:
                try:
                    # Check if file exists on replica nodes
                    import json
                    replica_nodes = json.loads(file_record.replica_nodes)
                    
                    # Find a replica node that has the file
                    source_node = None
                    source_path = None
                    
                    for replica_node_id in replica_nodes:
                        replica_node = self.db_session.query(StorageNode).filter(
                            StorageNode.node_id == replica_node_id,
                            StorageNode.is_online == True
                        ).first()
                        
                        if replica_node:
                            potential_path = os.path.join(replica_node.path, file_record.filename)
                            if os.path.exists(potential_path):
                                source_node = replica_node
                                source_path = potential_path
                                break
                    
                    if not source_node:
                        logger.error(f"Cannot failover file {file_record.id}: no replica available")
                        continue
                    
                    # Promote replica to primary
                    logger.info(f"Promoting replica {source_node.node_id} to primary for file {file_record.id}")
                    file_record.primary_node = source_node.node_id
                    
                    # Remove failed node from replica list
                    replica_nodes = [n for n in replica_nodes if n != failed_node_id]
                    file_record.replica_nodes = json.dumps(replica_nodes)
                    
                    migrated_count += 1
                
                except Exception as e:
                    logger.error(f"Error migrating file {file_record.id}: {e}")
                    continue
            
            self.db_session.commit()
            logger.info(f"Failover completed: {migrated_count}/{len(files_to_migrate)} files migrated")
        
        except Exception as e:
            logger.error(f"Error during failover: {e}", exc_info=True)
            self.db_session.rollback()
