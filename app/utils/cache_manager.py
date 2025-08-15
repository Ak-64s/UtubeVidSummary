import time
from typing import Any, Dict, Optional
import threading
import redis
import pickle
import os

class CacheManager:
    def __init__(self, default_ttl: int = 3600): # Default TTL 1 hour
        self.default_ttl = default_ttl
        redis_url = os.getenv('REDIS_URL')
        if redis_url:
            try:
                self.redis = redis.Redis.from_url(redis_url)
                self.redis.ping()
                self.use_redis = True
            except (redis.ConnectionError, redis.TimeoutError):
                self.use_redis = False
                self._cache = {}
                self._cache_expiry = {}
        else:
            self.use_redis = False
            self._cache = {}
            self._cache_expiry = {}

    def _get_namespaced_key(self, namespace: str, key: str) -> str:
        return f"{namespace}:{key}"

    def set_cached_data(self, namespace: str, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        actual_ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl
        namespaced_key = f"{namespace}:{key}"
        if self.use_redis:
            self.redis.setex(namespaced_key, actual_ttl, pickle.dumps(value))
        else:
            self._cache[namespaced_key] = pickle.dumps(value)
            self._cache_expiry[namespaced_key] = time.time() + actual_ttl

    def get_cached_data(self, namespace: str, key: str) -> Optional[Any]:
        namespaced_key = f"{namespace}:{key}"
        if self.use_redis:
            value = self.redis.get(namespaced_key)
        else:
            if namespaced_key in self._cache_expiry and time.time() > self._cache_expiry[namespaced_key]:
                del self._cache[namespaced_key]
                del self._cache_expiry[namespaced_key]
                return None
            value = self._cache.get(namespaced_key)
        return pickle.loads(value) if value else None

    def delete_cached_data(self, namespace: str, key: str) -> None:
        namespaced_key = f"{namespace}:{key}"
        if self.use_redis:
            self.redis.delete(namespaced_key)
        else:
            self._cache.pop(namespaced_key, None)
            self._cache_expiry.pop(namespaced_key, None)

    def clear_namespace(self, namespace: str) -> None:
        if self.use_redis:
            keys = self.redis.keys(f"{namespace}:*")
            if keys:
                self.redis.delete(*keys)
        else:
            keys_to_delete = [k for k in self._cache if k.startswith(f"{namespace}:")]
            for k in keys_to_delete:
                del self._cache[k]
                del self._cache_expiry[k]

    def clear_all_cache(self) -> None:
        if self.use_redis:
            self.redis.flushdb()
        else:
            self._cache.clear()
            self._cache_expiry.clear()

# Global instance (or inject it if preferred)
cache_manager = CacheManager() 