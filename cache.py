"""Redis 缓存层（升级2：差标规则 / 审批待办列表 / overdue 结果）

设计原则：缓存是可选的加速层，Redis 不可用时所有方法静默降级为「直接查库」，
业务逻辑不受影响——本地没装 Redis 也能跑，装好后自动生效。

环境变量：
  REDIS_URL        默认 redis://127.0.0.1:6379/0
  CACHE_ENABLED    auto / 1 / 0，默认 auto（连得上就开）
"""
import json
import logging
import os

logger = logging.getLogger("cache")

REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
CACHE_ENABLED = os.getenv("CACHE_ENABLED", "auto").strip().lower()

_client = None
_disabled = CACHE_ENABLED == "0"


def get_redis():
    """懒加载 Redis 客户端；连不上返回 None（降级）。"""
    global _client
    if _disabled:
        return None
    if _client is None:
        try:
            import redis

            _client = redis.Redis.from_url(REDIS_URL, socket_connect_timeout=1, socket_timeout=1)
            _client.ping()
            logger.info("Redis 缓存已启用：%s", REDIS_URL)
        except Exception as e:
            logger.warning("Redis 不可用，缓存降级为直查：%s", e)
            _client = None
    return _client


def cache_get(key: str):
    """读缓存；未命中或 Redis 不可用返回 None"""
    client = get_redis()
    if client is None:
        return None
    try:
        return client.get(key)
    except Exception:
        return None


def cache_get_json(key: str):
    value = cache_get(key)
    if value is None:
        return None
    try:
        return json.loads(value)
    except Exception:
        return None


def cache_set(key: str, value, ttl_seconds: int = 30):
    """写缓存（value 为 str 或可 json 序列化对象）；Redis 不可用时静默跳过"""
    client = get_redis()
    if client is None:
        return
    try:
        if not isinstance(value, str):
            value = json.dumps(value, ensure_ascii=False)
        client.set(key, value, ex=ttl_seconds)
    except Exception:
        pass


def cache_delete(*keys: str):
    """删除指定 key（写入后主动失效，保证缓存一致性）"""
    client = get_redis()
    if client is None:
        return
    try:
        if keys:
            client.delete(*keys)
    except Exception:
        pass


def cache_delete_prefix(prefix: str):
    """删除某个前缀的所有 key（如 approvals:pending:*）"""
    client = get_redis()
    if client is None:
        return
    try:
        for key in client.scan_iter(f"{prefix}*", count=200):
            client.delete(key)
    except Exception:
        pass
