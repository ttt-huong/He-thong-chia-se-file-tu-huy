"""
src/middleware/redis_client.py - Redis Operations
Wrapper cho Redis (caching, locking, counter)
Chương 4, 6: Distributed Locking (Redlock) & Caching
"""

import redis
import json
from typing import Any, Optional
import time
import logging

logger = logging.getLogger(__name__)

# Fallback in-memory cache when Redis is unavailable
class InMemoryCache:
    """Simple in-memory cache as fallback"""
    def __init__(self):
        self.data = {}
        self.expiry = {}
    
    def set(self, key, value, ex=None):
        """Set key-value with optional expiry in seconds"""
        self.data[key] = value
        if ex:
            self.expiry[key] = time.time() + ex
    
    def get(self, key):
        """Get value, return None if expired or not found"""
        if key in self.expiry:
            if time.time() > self.expiry[key]:
                del self.data[key]
                del self.expiry[key]
                return None
        return self.data.get(key)
    
    def delete(self, key):
        """Delete key"""
        self.data.pop(key, None)
        self.expiry.pop(key, None)
    
    def setex(self, key, ttl, value):
        """Set with TTL (for compatibility)"""
        self.set(key, str(value), ex=ttl)
    
    def decr(self, key):
        """Decrement value"""
        if key in self.data:
            val = int(self.data[key]) - 1
            self.data[key] = str(val)
            return val
        return None
    
    def ping(self):
        """Compatibility ping"""
        return True


class RedisClient:
    def __init__(self, host: str = "localhost", port: int = 6379, db: int = 0):
        """Initialize Redis connection with fallback to in-memory cache"""
        self.using_fallback = False
        try:
            self.redis_client = redis.Redis(
                host=host,
                port=port,
                db=db,
                decode_responses=True,
                socket_connect_timeout=3,
            )
            self.redis_client.ping()
            logger.info(f"[REDIS] Connected to {host}:{port}")
        except (redis.ConnectionError, ConnectionRefusedError, OSError) as e:
            logger.warning(f"[REDIS] Connection failed: {e}. Using in-memory cache fallback")
            self.redis_client = InMemoryCache()
            self.using_fallback = True

    # ===== COUNTER OPERATIONS =====
    def set_download_counter(self, file_id: str, limit: int, ttl: int) -> bool:
        """
        Set download counter with TTL
        Chương 6: Caching
        """
        try:
            self.redis_client.setex(f"count:{file_id}", ttl, limit)
            logger.debug(f"[REDIS] Set counter for {file_id}: {limit} downloads, TTL {ttl}s")
            return True
        except Exception as e:
            logger.error(f"[REDIS] Failed to set counter: {e}")
            return False

    def get_download_counter(self, file_id: str) -> Optional[int]:
        """Get remaining download count"""
        try:
            value = self.redis_client.get(f"count:{file_id}")
            if value is None:
                return None
            return int(value)
        except Exception as e:
            logger.error(f"[REDIS] Failed to get counter: {e}")
            return None

    def decrement_counter(self, file_id: str) -> bool:
        """Decrease download counter by 1"""
        try:
            result = self.redis_client.decr(f"count:{file_id}")
            logger.debug(f"[REDIS] Decremented counter for {file_id}: {result}")
            return result >= 0
        except Exception as e:
            logger.error(f"[REDIS] Failed to decrement counter: {e}")
            return False

    # ===== CACHE OPERATIONS =====
    def set_cache(self, key: str, value: Any, ttl: int = 3600) -> bool:
        """Set value in cache with TTL"""
        try:
            if isinstance(value, dict):
                value = json.dumps(value)
            self.redis_client.setex(key, ttl, value)
            logger.debug(f"[REDIS] Cached {key} (TTL: {ttl}s)")
            return True
        except Exception as e:
            logger.error(f"[REDIS] Failed to cache: {e}")
            return False

    def get_cache(self, key: str) -> Optional[str]:
        """Get value from cache"""
        try:
            value = self.redis_client.get(key)
            if value:
                logger.debug(f"[REDIS] Cache hit: {key}")
                try:
                    return json.loads(value)
                except json.JSONDecodeError:
                    return value
            else:
                logger.debug(f"[REDIS] Cache miss: {key}")
                return None
        except Exception as e:
            logger.error(f"[REDIS] Failed to get cache: {e}")
            return None

    def delete_cache(self, key: str) -> bool:
        """Delete key from cache"""
        try:
            self.redis_client.delete(key)
            logger.debug(f"[REDIS] Cache deleted: {key}")
            return True
        except Exception as e:
            logger.error(f"[REDIS] Failed to delete cache: {e}")
            return False

    # ===== DISTRIBUTED LOCKING (Redlock) =====
    def acquire_lock(self, key: str, ttl: int = 10, timeout: int = 5) -> bool:
        """
        Acquire distributed lock
        Chương 4: Distributed Locking (Redlock)
        """
        lock_key = f"lock:{key}"
        lock_value = str(time.time())
        
        try:
            # NX: only set if not exists
            result = self.redis_client.set(lock_key, lock_value, nx=True, ex=ttl)
            if result:
                logger.debug(f"[REDIS] Lock acquired: {lock_key}")
                return True
            else:
                logger.debug(f"[REDIS] Lock already held: {lock_key}")
                return False
        except Exception as e:
            logger.error(f"[REDIS] Failed to acquire lock: {e}")
            return False

    def release_lock(self, key: str) -> bool:
        """Release distributed lock"""
        lock_key = f"lock:{key}"
        try:
            self.redis_client.delete(lock_key)
            logger.debug(f"[REDIS] Lock released: {lock_key}")
            return True
        except Exception as e:
            logger.error(f"[REDIS] Failed to release lock: {e}")
            return False

    def is_locked(self, key: str) -> bool:
        """Check if key is locked"""
        lock_key = f"lock:{key}"
        try:
            return self.redis_client.exists(lock_key) > 0
        except Exception as e:
            logger.error(f"[REDIS] Failed to check lock: {e}")
            return False

    # ===== QUEUE OPERATIONS =====
    def push_queue(self, queue_name: str, value: dict) -> bool:
        """Push value to queue"""
        try:
            self.redis_client.rpush(queue_name, json.dumps(value))
            logger.debug(f"[REDIS] Pushed to queue {queue_name}")
            return True
        except Exception as e:
            logger.error(f"[REDIS] Failed to push to queue: {e}")
            return False

    def pop_queue(self, queue_name: str, timeout: int = 0) -> Optional[dict]:
        """Pop value from queue (BLPOP if timeout > 0)"""
        try:
            if timeout > 0:
                result = self.redis_client.blpop(queue_name, timeout)
                if result:
                    return json.loads(result[1])
            else:
                result = self.redis_client.lpop(queue_name)
                if result:
                    return json.loads(result)
            return None
        except Exception as e:
            logger.error(f"[REDIS] Failed to pop from queue: {e}")
            return None

    # ===== HEALTH CHECK =====
    def health_check(self) -> bool:
        """Check Redis connection"""
        try:
            self.redis_client.ping()
            return True
        except Exception as e:
            logger.error(f"[REDIS] Health check failed: {e}")
            return False

    def flush_all(self) -> bool:
        """DANGER: Flush all data (use only in development)"""
        try:
            self.redis_client.flushall()
            logger.warning("[REDIS] All data flushed!")
            return True
        except Exception as e:
            logger.error(f"[REDIS] Failed to flush: {e}")
            return False


# Global instance
_redis_instance = None


def get_redis_client() -> RedisClient:
    """Get or create singleton Redis client"""
    global _redis_instance
    if _redis_instance is None:
        from src.config.settings import REDIS_HOST, REDIS_PORT, REDIS_DB
        _redis_instance = RedisClient(REDIS_HOST, REDIS_PORT, REDIS_DB)
    return _redis_instance


if __name__ == "__main__":
    # Test
    client = RedisClient()
    client.set_cache("test_key", {"data": "value"}, ttl=60)
    print(client.get_cache("test_key"))
