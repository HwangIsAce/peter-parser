"""Redis and RQ queue connection for async parse jobs."""
from __future__ import annotations

from typing import Optional

import redis
from rq import Queue

from peter_parser.common.config import Config

_redis: Optional[redis.Redis] = None


def get_connection() -> redis.Redis:
    """Get Redis connection (singleton)."""
    global _redis
    if _redis is None:
        _redis = redis.from_url(Config.REDIS_URL)
    return _redis


def get_queue(name: str = "default") -> Queue:
    """Get RQ Queue by name."""
    return Queue(name=name, connection=get_connection())
