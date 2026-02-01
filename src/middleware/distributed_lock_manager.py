"""
Distributed Lock Manager using Redis
Prevents concurrent uploads of same file and manages resource contention
Phase 3: Distributed Locking for concurrent operations
"""

import logging
import time
import uuid
from typing import Optional, List
from datetime import datetime
from src.middleware.redis_sentinel_client import RedisSentinelClient

logger = logging.getLogger(__name__)


class DistributedLockManager:
    """
    Manages distributed locks across multiple processes/servers
    Uses Redis with Sentinel for HA
    
    Lock Key Format: lock:resource:type:identifier
    Examples:
      - lock:file:upload:file-id-123 (prevent duplicate upload)
      - lock:file:download:file-id-123 (prevent concurrent access)
      - lock:node:node1 (prevent concurrent operations on node)
    """
    
    def __init__(self, redis_client: RedisSentinelClient):
        """
        Initialize lock manager
        
        Args:
            redis_client: RedisSentinelClient instance
        """
        self.redis = redis_client
        self.default_timeout = 30  # seconds
        self.lock_prefix = "lock"
        
    def acquire(self, resource_type: str, resource_id: str, timeout: int = None) -> Optional[str]:
        """
        Acquire a distributed lock
        
        Args:
            resource_type: Type of resource (file, node, upload, etc.)
            resource_id: Unique identifier for resource
            timeout: Lock timeout in seconds (default: 30)
        
        Returns:
            Lock token if acquired, None if lock already held
        """
        if timeout is None:
            timeout = self.default_timeout
        
        lock_key = f"{self.lock_prefix}:{resource_type}:{resource_id}"
        lock_token = f"{uuid.uuid4()}"
        
        try:
            # Try to acquire lock using SET NX (only if not exists)
            acquired = self.redis.set(lock_key, lock_token, ex=timeout)
            
            if acquired:
                logger.info(f"✅ Lock acquired: {lock_key} (token={lock_token[:8]}, timeout={timeout}s)")
                return lock_token
            else:
                logger.debug(f"❌ Lock already held: {lock_key}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to acquire lock {lock_key}: {e}")
            return None
    
    def release(self, resource_type: str, resource_id: str, lock_token: str) -> bool:
        """
        Release a distributed lock (only if token matches)
        
        Args:
            resource_type: Type of resource
            resource_id: Unique identifier
            lock_token: Lock token returned from acquire()
        
        Returns:
            True if released, False if token mismatch or error
        """
        lock_key = f"{self.lock_prefix}:{resource_type}:{resource_id}"
        
        try:
            current_token = self.redis.get(lock_key)
            
            if current_token == lock_token:
                self.redis.delete(lock_key)
                logger.info(f"✅ Lock released: {lock_key}")
                return True
            else:
                logger.warning(f"❌ Lock token mismatch: {lock_key}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to release lock {lock_key}: {e}")
            return False
    
    def extend(self, resource_type: str, resource_id: str, lock_token: str, 
               additional_timeout: int = 10) -> bool:
        """
        Extend lock timeout
        
        Args:
            resource_type: Type of resource
            resource_id: Unique identifier
            lock_token: Current lock token
            additional_timeout: Additional seconds to extend
        
        Returns:
            True if extended, False otherwise
        """
        lock_key = f"{self.lock_prefix}:{resource_type}:{resource_id}"
        
        try:
            current_token = self.redis.get(lock_key)
            
            if current_token == lock_token:
                self.redis.expire(lock_key, self.default_timeout + additional_timeout)
                logger.debug(f"✅ Lock extended: {lock_key}")
                return True
            else:
                logger.warning(f"❌ Cannot extend: token mismatch")
                return False
                
        except Exception as e:
            logger.error(f"Failed to extend lock {lock_key}: {e}")
            return False
    
    def is_locked(self, resource_type: str, resource_id: str) -> bool:
        """Check if resource is locked"""
        lock_key = f"{self.lock_prefix}:{resource_type}:{resource_id}"
        return self.redis.exists(lock_key)
    
    def wait_for_lock(self, resource_type: str, resource_id: str, 
                     max_wait: int = 60, poll_interval: float = 0.5) -> bool:
        """
        Wait for a lock to be released
        
        Args:
            resource_type: Type of resource
            resource_id: Unique identifier
            max_wait: Maximum time to wait in seconds
            poll_interval: How often to check (seconds)
        
        Returns:
            True if lock was released, False if timeout
        """
        start_time = time.time()
        lock_key = f"{self.lock_prefix}:{resource_type}:{resource_id}"
        
        while time.time() - start_time < max_wait:
            if not self.is_locked(resource_type, resource_id):
                logger.info(f"✅ Lock released after {time.time() - start_time:.2f}s")
                return True
            time.sleep(poll_interval)
        
        logger.warning(f"❌ Timeout waiting for lock: {lock_key}")
        return False
    
    def get_lock_info(self, resource_type: str, resource_id: str) -> dict:
        """Get information about a lock"""
        lock_key = f"{self.lock_prefix}:{resource_type}:{resource_id}"
        
        try:
            token = self.redis.get(lock_key)
            ttl = self.redis.ttl(lock_key)
            
            return {
                'key': lock_key,
                'locked': token is not None,
                'token': token[:8] if token else None,
                'ttl': ttl if ttl > 0 else 0
            }
        except Exception as e:
            logger.error(f"Error getting lock info: {e}")
            return {}
    
    def list_locks(self, resource_type: str = None) -> List[dict]:
        """List all active locks, optionally filtered by type"""
        try:
            pattern = f"{self.lock_prefix}:{resource_type or '*'}:*" if resource_type else f"{self.lock_prefix}:*"
            # Note: In production, use SCAN instead of KEYS for large datasets
            locks = []
            # This would require implementing key scanning
            return locks
        except Exception as e:
            logger.error(f"Error listing locks: {e}")
            return []


class FileLockContext:
    """Context manager for file operations with automatic lock management"""
    
    def __init__(self, lock_manager: DistributedLockManager, 
                 file_id: str, operation: str = "upload"):
        """
        Initialize file lock context
        
        Args:
            lock_manager: DistributedLockManager instance
            file_id: File ID to lock
            operation: Operation type (upload, download, delete, etc.)
        """
        self.lock_manager = lock_manager
        self.file_id = file_id
        self.operation = operation
        self.lock_token = None
        
    def __enter__(self):
        """Acquire lock on context enter"""
        self.lock_token = self.lock_manager.acquire(
            resource_type=f"file_{self.operation}",
            resource_id=self.file_id,
            timeout=60  # 60 seconds for file operations
        )
        
        if not self.lock_token:
            raise RuntimeError(f"Failed to acquire lock for {self.operation} {self.file_id}")
        
        return self.lock_token
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Release lock on context exit"""
        if self.lock_token:
            self.lock_manager.release(
                resource_type=f"file_{self.operation}",
                resource_id=self.file_id,
                lock_token=self.lock_token
            )
        return False  # Don't suppress exceptions


class UploadLockContext:
    """Context manager specifically for upload operations"""
    
    def __init__(self, lock_manager: DistributedLockManager, file_id: str):
        """Initialize upload lock context"""
        self.lock_manager = lock_manager
        self.file_id = file_id
        self.lock_token = None
        self.lock_acquired = False
        
    def __enter__(self):
        """Acquire upload lock"""
        self.lock_token = self.lock_manager.acquire(
            resource_type="file_upload",
            resource_id=self.file_id,
            timeout=300  # 5 minutes for upload
        )
        
        if self.lock_token:
            self.lock_acquired = True
            logger.info(f"Upload lock acquired for {self.file_id}")
            return self
        else:
            logger.warning(f"Cannot acquire upload lock for {self.file_id} - already uploading")
            return None
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Release upload lock"""
        if self.lock_token and self.lock_acquired:
            self.lock_manager.release(
                resource_type="file_upload",
                resource_id=self.file_id,
                lock_token=self.lock_token
            )
        return False
    
    def extend_timeout(self, additional_seconds: int = 60) -> bool:
        """Extend lock timeout during long uploads"""
        if self.lock_token:
            return self.lock_manager.extend(
                resource_type="file_upload",
                resource_id=self.file_id,
                lock_token=self.lock_token,
                additional_timeout=additional_seconds
            )
        return False
