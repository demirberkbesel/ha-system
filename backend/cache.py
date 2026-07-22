import redis
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

redis_client = None


def _get_redis():
    global redis_client
    if redis_client is None:
        if _redis_ip is None:
            return None
        try:
            redis_client = redis.Redis(host=_redis_ip, port=6379, socket_connect_timeout=0.5, socket_timeout=0.5)
            redis_client.ping()
        except Exception:
            redis_client = None
            return None
    return redis_client


def cache_get(key: str):
    r = _get_redis()
    if r is None:
        return None
    try:
        data = r.get(key)
        if data:
            return json.loads(data)
    except Exception:
        global redis_client
        redis_client = None
    return None


def cache_set(key: str, value, ttl: int = CACHE_TTL):
    r = _get_redis()
    if r is None:
        return
    try:
        r.setex(key, ttl, json.dumps(value, default=str))
    except Exception:
        global redis_client
        redis_client = None


def cache_delete(key: str):
    r = _get_redis()
    if r is None:
        return
    try:
        r.delete(key)
    except Exception:
        global redis_client
        redis_client = None


def invalidate_items_cache():
    cache_delete("items:all")
