import json
import os
import socket
import logging

logger = logging.getLogger("cache")

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
CACHE_TTL = int(os.getenv("CACHE_TTL", 60))

_redis_ip = None
try:
    _redis_ip = socket.getaddrinfo(REDIS_HOST, 6379, socket.AF_INET, socket.SOCK_STREAM)[0][4][0]
except Exception:
    pass


def _try_redis(fn):
    if _redis_ip is None:
        return None
    try:
        import redis
        r = redis.Redis(host=_redis_ip, port=6379, socket_connect_timeout=0.2, socket_timeout=0.2)
        return fn(r)
    except Exception:
        return None


def cache_get(key: str):
    def _do(r):
        data = r.get(key)
        return json.loads(data) if data else None
    return _try_redis(_do)


def cache_set(key: str, value, ttl: int = CACHE_TTL):
    def _do(r):
        r.setex(key, ttl, json.dumps(value, default=str))
    _try_redis(_do)


def cache_delete(key: str):
    def _do(r):
        r.delete(key)
    _try_redis(_do)


def invalidate_items_cache():
    cache_delete("items:all")
