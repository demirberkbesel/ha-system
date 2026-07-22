import redis
import json
import os
import logging

logger = logging.getLogger("cache")

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
CACHE_TTL = int(os.getenv("CACHE_TTL", 60))

redis_client = None


def _get_redis():
    global redis_client
    if redis_client is None:
        try:
            redis_client = redis.Redis.from_url(REDIS_URL, socket_connect_timeout=2, socket_timeout=2)
            redis_client.ping()
        except Exception as e:
            logger.warning("redis unavailable (%s), falling back to DB", e)
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
    except Exception as e:
        logger.warning("cache get error: %s", e)
    return None


def cache_set(key: str, value, ttl: int = CACHE_TTL):
    r = _get_redis()
    if r is None:
        return
    try:
        r.setex(key, ttl, json.dumps(value, default=str))
    except Exception as e:
        logger.warning("cache set error: %s", e)


def cache_delete(key: str):
    r = _get_redis()
    if r is None:
        return
    try:
        r.delete(key)
    except Exception as e:
        logger.warning("cache delete error: %s", e)


def invalidate_items_cache():
    cache_delete("items:all")
