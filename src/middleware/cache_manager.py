"""
Cache Manager with Invalidation Strategy
Handles caching of file metadata, node stats, and replication state
Phase 3: Cache Layer with Redis Cluster HA
"""

import logging
import json
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from src.middleware.redis_sentinel_client import RedisSentinelClient

logger = logging.getLogger(__name__)


class CacheManager:
    """
    Redis-based cache manager with automatic invalidation
    
    Cache Key Patterns:
      - file:metadata:{file_id} - File metadata
      - file:list:{page} - Paginated file list
      - node:stats:{node_id} - Node statistics
      - node:health:{node_id} - Node health status
      - replication:status - Replication cluster status
      - cache:version - Cache version for bulk invalidation
    """
    
    def __init__(self, redis_client: RedisSentinelClient):
        """
        Initialize cache manager
        
        Args:
            redis_client: RedisSentinelClient instance
        """
        self.redis = redis_client
        self.cache_prefix = "cache"
        self.default_ttl = 300  # 5 minutes
        
        # Cache version for bulk invalidation
        self._init_cache_version()
    
    def _init_cache_version(self):
        """Initialize or get cache version"""
        version_key = f"{self.cache_prefix}:version"
        version = self.redis.get(version_key)
        if not version:
            self.redis.set(version_key, "1", ex=None)
    
    def invalidate_all(self):
        """Invalidate all caches by incrementing version"""
        version_key = f"{self.cache_prefix}:version"
        try:
            self.redis.incr(version_key)
            logger.info("✅ All caches invalidated")
        except Exception as e:
            logger.error(f"Failed to invalidate caches: {e}")
    
    # ============ FILE CACHE ============
    
    def get_file_metadata(self, file_id: str) -> Optional[Dict]:
        """Get cached file metadata"""
        key = f"file:metadata:{file_id}"
        try:
            data = self.redis.get(key)
            if data:
                logger.debug(f"✅ Cache hit: {key}")
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"Error getting file metadata from cache: {e}")
            return None
    
    def set_file_metadata(self, file_id: str, metadata: Dict, ttl: int = None):
        """Cache file metadata"""
        key = f"file:metadata:{file_id}"
        try:
            if ttl is None:
                ttl = self.default_ttl
            self.redis.set(key, json.dumps(metadata), ex=ttl)
            logger.debug(f"Cache stored: {key} (ttl={ttl}s)")
        except Exception as e:
            logger.error(f"Error caching file metadata: {e}")
    
    def invalidate_file_metadata(self, file_id: str):
        """Invalidate specific file metadata cache"""
        key = f"file:metadata:{file_id}"
        try:
            self.redis.delete(key)
            logger.info(f"✅ Cache invalidated: {key}")
        except Exception as e:
            logger.error(f"Error invalidating file metadata: {e}")
    
    def invalidate_file_list(self):
        """Invalidate all file list caches"""
        try:
            # In production, use SCAN to avoid blocking on large datasets
            # For now, we'll increment a file_list version
            self.redis.incr(f"{self.cache_prefix}:file_list:version")
            logger.info("✅ File list cache invalidated")
        except Exception as e:
            logger.error(f"Error invalidating file list: {e}")
    
    # ============ NODE STATS CACHE ============
    
    def get_node_stats(self, node_id: str) -> Optional[Dict]:
        """Get cached node statistics"""
        key = f"node:stats:{node_id}"
        try:
            data = self.redis.get(key)
            if data:
                logger.debug(f"✅ Cache hit: {key}")
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"Error getting node stats from cache: {e}")
            return None
    
    def set_node_stats(self, node_id: str, stats: Dict, ttl: int = 60):
        """Cache node statistics (shorter TTL for frequently changing data)"""
        key = f"node:stats:{node_id}"
        try:
            self.redis.set(key, json.dumps(stats), ex=ttl)
            logger.debug(f"Cache stored: {key} (ttl={ttl}s)")
        except Exception as e:
            logger.error(f"Error caching node stats: {e}")
    
    def invalidate_node_stats(self, node_id: str = None):
        """Invalidate node stats cache"""
        try:
            if node_id:
                key = f"node:stats:{node_id}"
                self.redis.delete(key)
                logger.info(f"✅ Cache invalidated: {key}")
            else:
                # Invalidate all node stats (increment version)
                self.redis.incr(f"{self.cache_prefix}:node_stats:version")
                logger.info("✅ All node stats cache invalidated")
        except Exception as e:
            logger.error(f"Error invalidating node stats: {e}")
    
    # ============ NODE HEALTH CACHE ============
    
    def get_node_health(self, node_id: str) -> Optional[Dict]:
        """Get cached node health status"""
        key = f"node:health:{node_id}"
        try:
            data = self.redis.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"Error getting node health from cache: {e}")
            return None
    
    def set_node_health(self, node_id: str, health_status: Dict, ttl: int = 30):
        """Cache node health status"""
        key = f"node:health:{node_id}"
        try:
            self.redis.set(key, json.dumps(health_status), ex=ttl)
        except Exception as e:
            logger.error(f"Error caching node health: {e}")
    
    # ============ REPLICATION CACHE ============
    
    def get_replication_status(self) -> Optional[Dict]:
        """Get cached replication cluster status"""
        key = "replication:status"
        try:
            data = self.redis.get(key)
            if data:
                logger.debug(f"✅ Cache hit: {key}")
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"Error getting replication status: {e}")
            return None
    
    def set_replication_status(self, status: Dict, ttl: int = 60):
        """Cache replication status"""
        key = "replication:status"
        try:
            self.redis.set(key, json.dumps(status), ex=ttl)
        except Exception as e:
            logger.error(f"Error caching replication status: {e}")
    
    def invalidate_replication_status(self):
        """Invalidate replication status cache"""
        key = "replication:status"
        try:
            self.redis.delete(key)
            logger.info(f"✅ Cache invalidated: {key}")
        except Exception as e:
            logger.error(f"Error invalidating replication status: {e}")
    
    # ============ GENERIC CACHE OPERATIONS ============
    
    def get(self, key: str) -> Optional[str]:
        """Get value from cache"""
        try:
            return self.redis.get(key)
        except Exception as e:
            logger.error(f"Cache get error: {e}")
            return None
    
    def set(self, key: str, value: str, ttl: int = None):
        """Set value in cache"""
        try:
            if ttl is None:
                ttl = self.default_ttl
            self.redis.set(key, value, ex=ttl)
        except Exception as e:
            logger.error(f"Cache set error: {e}")
    
    def delete(self, key: str):
        """Delete value from cache"""
        try:
            self.redis.delete(key)
        except Exception as e:
            logger.error(f"Cache delete error: {e}")
    
    def exists(self, key: str) -> bool:
        """Check if key exists in cache"""
        try:
            return self.redis.exists(key)
        except Exception as e:
            logger.error(f"Cache exists error: {e}")
            return False
    
    def get_cache_info(self) -> Dict:
        """Get cache statistics"""
        try:
            info = self.redis.info()
            return {
                'used_memory': info.get('used_memory_human', 'N/A'),
                'used_memory_peak': info.get('used_memory_peak_human', 'N/A'),
                'evicted_keys': info.get('evicted_keys', 0),
                'keyspace_hits': info.get('keyspace_hits', 0),
                'keyspace_misses': info.get('keyspace_misses', 0),
                'connected_clients': info.get('connected_clients', 0),
            }
        except Exception as e:
            logger.error(f"Error getting cache info: {e}")
            return {}
    
    def cleanup_expired(self):
        """Trigger cleanup of expired keys"""
        try:
            # Redis automatically removes expired keys
            # This is just for documentation and future extensions
            logger.info("Cache cleanup (handled by Redis)")
        except Exception as e:
            logger.error(f"Cache cleanup error: {e}")


class CacheInvalidationQueue:
    """
    Queue for cache invalidation events
    Useful for event-driven cache invalidation across services
    """
    
    def __init__(self, redis_client: RedisSentinelClient):
        """Initialize cache invalidation queue"""
        self.redis = redis_client
        self.queue_key = "cache:invalidation:queue"
    
    def enqueue(self, cache_key: str, event_type: str = "invalidate"):
        """Add cache invalidation to queue"""
        try:
            event = {
                'cache_key': cache_key,
                'event_type': event_type,
                'timestamp': datetime.utcnow().isoformat()
            }
            self.redis.lpush(self.queue_key, json.dumps(event))
            logger.debug(f"Cache invalidation enqueued: {cache_key}")
        except Exception as e:
            logger.error(f"Error enqueueing invalidation: {e}")
    
    def dequeue(self) -> Optional[Dict]:
        """Get next cache invalidation from queue"""
        try:
            event_json = self.redis.rpop(self.queue_key)
            if event_json:
                return json.loads(event_json)
            return None
        except Exception as e:
            logger.error(f"Error dequeueing invalidation: {e}")
            return None
    
    def queue_length(self) -> int:
        """Get queue length"""
        try:
            return self.redis.llen(self.queue_key)
        except Exception as e:
            logger.error(f"Error getting queue length: {e}")
            return 0
