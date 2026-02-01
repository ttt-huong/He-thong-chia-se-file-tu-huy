"""
Redis Sentinel Client for HA and failover
Handles automatic failover from master to slave
Phase 3: Redis Master-Slave Cluster
"""

import logging
import redis
from redis.sentinel import Sentinel
import os
from typing import Optional, Dict

logger = logging.getLogger(__name__)


class RedisSentinelClient:
    """
    Redis client with Sentinel support for High Availability
    Automatically handles master-slave failover
    """
    
    def __init__(self):
        """
        Initialize Redis Sentinel client
        Uses environment variables:
        - REDIS_SENTINEL_HOST: Primary Sentinel host (default: localhost)
        - REDIS_SENTINEL_PORT: Primary Sentinel port (default: 26379)
        - REDIS_SENTINEL_MASTER: Master name in Sentinel (default: fileshare-master)
        """
        self.sentinel_host = os.getenv('REDIS_SENTINEL_HOST', 'localhost')
        self.sentinel_port = int(os.getenv('REDIS_SENTINEL_PORT', '26379'))
        self.master_name = os.getenv('REDIS_SENTINEL_MASTER', 'fileshare-master')
        
        # Fallback: try direct Redis connection if Sentinel not available
        self.redis_host = os.getenv('REDIS_HOST', 'localhost')
        self.redis_port = int(os.getenv('REDIS_PORT', '6379'))
        
        self.client = None
        self.sentinel = None
        self._connect()
        
    def _connect(self):
        """Connect to Redis via Sentinel"""
        try:
            # Sentinel configuration - list of (host, port) tuples
            sentinels = [
                (self.sentinel_host, self.sentinel_port),
                (self.sentinel_host.replace('-1', '-2'), self.sentinel_port + 1),
                (self.sentinel_host.replace('-1', '-3'), self.sentinel_port + 2),
            ]
            
            logger.info(f"Connecting to Redis via Sentinel: {self.master_name}")
            
            # Create Sentinel instance
            self.sentinel = Sentinel(sentinels, socket_connect_timeout=5)
            
            # Get master connection
            self.client = self.sentinel.master_for(
                self.master_name,
                socket_connect_timeout=5,
                socket_keepalive=True,
                health_check_interval=10
            )
            
            # Test connection
            self.client.ping()
            logger.info("✅ Connected to Redis Master via Sentinel")
            
        except Exception as e:
            logger.warning(f"Sentinel connection failed: {e}")
            logger.info(f"Falling back to direct Redis connection: {self.redis_host}:{self.redis_port}")
            
            try:
                # Fallback to direct connection
                self.client = redis.Redis(
                    host=self.redis_host,
                    port=self.redis_port,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_keepalive=True
                )
                self.client.ping()
                logger.info("✅ Connected to Redis (direct mode)")
            except Exception as e2:
                logger.error(f"❌ Failed to connect to Redis: {e2}")
                raise
    
    def get(self, key: str) -> Optional[str]:
        """Get value from Redis"""
        try:
            return self.client.get(key)
        except Exception as e:
            logger.error(f"Redis GET error: {e}")
            return None
    
    def set(self, key: str, value: str, ex: int = None) -> bool:
        """Set value in Redis with optional expiration"""
        try:
            if ex:
                self.client.setex(key, ex, value)
            else:
                self.client.set(key, value)
            return True
        except Exception as e:
            logger.error(f"Redis SET error: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """Delete key from Redis"""
        try:
            self.client.delete(key)
            return True
        except Exception as e:
            logger.error(f"Redis DELETE error: {e}")
            return False
    
    def exists(self, key: str) -> bool:
        """Check if key exists"""
        try:
            return self.client.exists(key) > 0
        except Exception as e:
            logger.error(f"Redis EXISTS error: {e}")
            return False
    
    def incr(self, key: str) -> int:
        """Increment counter"""
        try:
            return self.client.incr(key)
        except Exception as e:
            logger.error(f"Redis INCR error: {e}")
            return 0
    
    def decr(self, key: str) -> int:
        """Decrement counter"""
        try:
            return self.client.decr(key)
        except Exception as e:
            logger.error(f"Redis DECR error: {e}")
            return 0
    
    def lpush(self, key: str, value: str) -> int:
        """Push value to list"""
        try:
            return self.client.lpush(key, value)
        except Exception as e:
            logger.error(f"Redis LPUSH error: {e}")
            return 0
    
    def rpop(self, key: str) -> Optional[str]:
        """Pop value from list"""
        try:
            return self.client.rpop(key)
        except Exception as e:
            logger.error(f"Redis RPOP error: {e}")
            return None
    
    def llen(self, key: str) -> int:
        """Get list length"""
        try:
            return self.client.llen(key)
        except Exception as e:
            logger.error(f"Redis LLEN error: {e}")
            return 0
    
    def sadd(self, key: str, value: str) -> int:
        """Add to set"""
        try:
            return self.client.sadd(key, value)
        except Exception as e:
            logger.error(f"Redis SADD error: {e}")
            return 0
    
    def smembers(self, key: str) -> set:
        """Get all members of set"""
        try:
            return self.client.smembers(key)
        except Exception as e:
            logger.error(f"Redis SMEMBERS error: {e}")
            return set()
    
    def sismember(self, key: str, value: str) -> bool:
        """Check if value is in set"""
        try:
            return self.client.sismember(key, value)
        except Exception as e:
            logger.error(f"Redis SISMEMBER error: {e}")
            return False
    
    def hset(self, key: str, field: str, value: str) -> int:
        """Set hash field"""
        try:
            return self.client.hset(key, field, value)
        except Exception as e:
            logger.error(f"Redis HSET error: {e}")
            return 0
    
    def hget(self, key: str, field: str) -> Optional[str]:
        """Get hash field"""
        try:
            return self.client.hget(key, field)
        except Exception as e:
            logger.error(f"Redis HGET error: {e}")
            return None
    
    def hgetall(self, key: str) -> Dict:
        """Get all hash fields"""
        try:
            return self.client.hgetall(key)
        except Exception as e:
            logger.error(f"Redis HGETALL error: {e}")
            return {}
    
    def expire(self, key: str, seconds: int) -> bool:
        """Set key expiration"""
        try:
            return self.client.expire(key, seconds)
        except Exception as e:
            logger.error(f"Redis EXPIRE error: {e}")
            return False
    
    def ttl(self, key: str) -> int:
        """Get key TTL (time to live)"""
        try:
            return self.client.ttl(key)
        except Exception as e:
            logger.error(f"Redis TTL error: {e}")
            return -1
    
    def flush_all(self):
        """Flush all data (use with caution)"""
        try:
            self.client.flushall()
            logger.warning("Redis database flushed")
        except Exception as e:
            logger.error(f"Redis FLUSH error: {e}")
    
    def info(self) -> Dict:
        """Get Redis server info"""
        try:
            return self.client.info()
        except Exception as e:
            logger.error(f"Redis INFO error: {e}")
            return {}
    
    def get_sentinel_info(self) -> Dict:
        """Get Sentinel cluster info"""
        try:
            if not self.sentinel:
                return {}
            
            info = {
                'master_name': self.master_name,
                'sentinels': [],
                'master': None,
                'slaves': []
            }
            
            # Get master info
            try:
                master = self.sentinel.discover_master(self.master_name)
                info['master'] = {
                    'host': master[0],
                    'port': master[1]
                }
            except Exception as e:
                logger.error(f"Failed to discover master: {e}")
            
            # Get slaves info
            try:
                slaves = self.sentinel.discover_slaves(self.master_name)
                info['slaves'] = [{'host': s[0], 'port': s[1]} for s in slaves]
            except Exception as e:
                logger.error(f"Failed to discover slaves: {e}")
            
            return info
            
        except Exception as e:
            logger.error(f"Error getting Sentinel info: {e}")
            return {}
    
    def acquire_lock(self, lock_name: str, timeout: int = 10) -> Optional[str]:
        """
        Acquire distributed lock
        Returns lock token if successful, None if lock already held
        """
        try:
            lock_key = f"lock:{lock_name}"
            lock_token = f"token-{lock_name}-{int(os.times()[4] * 1000000)}"
            
            # Try to set lock (NX = only if not exists)
            if self.client.set(lock_key, lock_token, ex=timeout, nx=True):
                logger.debug(f"✅ Lock acquired: {lock_name}")
                return lock_token
            else:
                logger.debug(f"❌ Lock already held: {lock_name}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to acquire lock: {e}")
            return None
    
    def release_lock(self, lock_name: str, lock_token: str) -> bool:
        """Release distributed lock (only if token matches)"""
        try:
            lock_key = f"lock:{lock_name}"
            current_token = self.client.get(lock_key)
            
            if current_token == lock_token:
                self.client.delete(lock_key)
                logger.debug(f"✅ Lock released: {lock_name}")
                return True
            else:
                logger.warning(f"❌ Lock token mismatch: {lock_name}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to release lock: {e}")
            return False
    
    def close(self):
        """Close Redis connection"""
        try:
            if self.client:
                self.client.close()
                logger.info("Redis connection closed")
        except Exception as e:
            logger.error(f"Error closing Redis: {e}")
