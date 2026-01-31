"""
Storage Node Client - Gateway sử dụng để giao tiếp với Storage Nodes
Thay thế việc ghi file trực tiếp bằng HTTP requests
"""

import requests
import logging
from typing import Optional, Dict, BinaryIO

logger = logging.getLogger(__name__)


class StorageNodeClient:
    """Client để giao tiếp với Storage Node Services"""
    
    def __init__(self, node_url: str, node_id: str, timeout: int = 30):
        """
        Initialize storage node client
        
        Args:
            node_url: Base URL of storage node (e.g. http://storage-node1:8000)
            node_id: Node identifier (e.g. node1)
            timeout: Request timeout in seconds
        """
        self.node_url = node_url.rstrip('/')
        self.node_id = node_id
        self.timeout = timeout
        logger.info(f"Storage Node Client initialized: {node_id} @ {node_url}")
    
    def health_check(self) -> Dict:
        """
        Check if storage node is online
        
        Returns:
            Dict with node status
        """
        try:
            response = requests.get(
                f"{self.node_url}/health",
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Health check failed for {self.node_id}: {e}")
            return {'status': 'offline', 'error': str(e)}
    
    def upload_file(self, file_content: bytes, filename: str, is_replica: bool = False) -> Dict:
        """
        Upload file to storage node
        
        Args:
            file_content: File binary content
            filename: Target filename
            is_replica: Flag indicating replica upload
        
        Returns:
            Dict with upload result {'status': 'success', ...} or {'status': 'error', ...}
        """
        try:
            files = {'file': (filename, file_content)}
            data = {'filename': filename, 'is_replica': 'true' if is_replica else 'false'}
            
            response = requests.post(
                f"{self.node_url}/upload",
                files=files,
                data=data,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            result = response.json()
            logger.info(f"File uploaded to {self.node_id}: {filename}")
            return result  # Returns {'status': 'success', 'filename': ..., 'size': ...}
            
        except Exception as e:
            logger.error(f"Upload failed to {self.node_id}: {e}")
            return {'status': 'error', 'error': str(e)}  # Return error dict instead of raising
    
    def download_file(self, filename: str) -> bytes:
        """
        Download file from storage node
        
        Args:
            filename: File to download
        
        Returns:
            File binary content
        """
        try:
            response = requests.get(
                f"{self.node_url}/download/{filename}",
                timeout=self.timeout
            )
            response.raise_for_status()
            
            logger.info(f"File downloaded from {self.node_id}: {filename}")
            return response.content
            
        except Exception as e:
            logger.error(f"Download failed from {self.node_id}: {e}")
            raise Exception(f"Failed to download from {self.node_id}: {str(e)}")
    
    def delete_file(self, filename: str) -> Dict:
        """
        Delete file from storage node
        
        Args:
            filename: File to delete
        
        Returns:
            Dict with delete result
        """
        try:
            response = requests.delete(
                f"{self.node_url}/delete/{filename}",
                timeout=self.timeout
            )
            response.raise_for_status()
            
            result = response.json()
            logger.info(f"File deleted from {self.node_id}: {filename}")
            return result
            
        except Exception as e:
            logger.error(f"Delete failed from {self.node_id}: {e}")
            raise Exception(f"Failed to delete from {self.node_id}: {str(e)}")
    
    def list_files(self) -> Dict:
        """
        List all files on storage node
        
        Returns:
            Dict with file list
        """
        try:
            response = requests.get(
                f"{self.node_url}/files",
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
            
        except Exception as e:
            logger.error(f"List files failed for {self.node_id}: {e}")
            return {'files': [], 'error': str(e)}
    
    def get_stats(self) -> Dict:
        """
        Get storage node statistics
        
        Returns:
            Dict with storage stats
        """
        try:
            response = requests.get(
                f"{self.node_url}/stats",
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
            
        except Exception as e:
            logger.error(f"Get stats failed for {self.node_id}: {e}")
            return {'error': str(e)}


class StorageNodeManager:
    """Quản lý nhiều Storage Node Clients"""
    
    def __init__(self):
        self.nodes = {}
        logger.info("Storage Node Manager initialized")
    
    def register_node(self, node_id: str, node_url: str) -> StorageNodeClient:
        """
        Register a storage node
        
        Args:
            node_id: Node identifier
            node_url: Node URL
        
        Returns:
            StorageNodeClient instance
        """
        client = StorageNodeClient(node_url, node_id)
        self.nodes[node_id] = client
        logger.info(f"Registered node: {node_id}")
        return client
    
    def get_node(self, node_id: str) -> Optional[StorageNodeClient]:
        """Get storage node client by ID"""
        return self.nodes.get(node_id)
    
    def get_all_nodes(self) -> Dict[str, StorageNodeClient]:
        """Get all registered nodes"""
        return self.nodes
    
    def check_all_health(self) -> Dict[str, Dict]:
        """
        Check health of all registered nodes
        
        Returns:
            Dict mapping node_id to health status
        """
        results = {}
        for node_id, client in self.nodes.items():
            results[node_id] = client.health_check()
        return results
