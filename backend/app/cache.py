from datetime import timedelta

import redis
from flask import current_app

_memory_blacklist = set()


def _redis():
    url = current_app.config.get("REDIS_URL")
    if not url:
        return None
    try:
        return redis.Redis.from_url(url, decode_responses=True)
    except Exception:
        return None


def revoke_token(jti, expires=timedelta(hours=24)):
    client = _redis()
    if client:
        client.setex(f"jwt:blacklist:{jti}", int(expires.total_seconds()), "1")
    else:
        _memory_blacklist.add(jti)


def is_token_revoked(jti):
    client = _redis()
    if client:
        return client.exists(f"jwt:blacklist:{jti}") == 1
    return jti in _memory_blacklist


def set_session_status(session_id, status):
    client = _redis()
    if client:
        client.set(f"session:{session_id}:status", status)


def get_session_status(session_id):
    client = _redis()
    if not client:
        return None
    return client.get(f"session:{session_id}:status")
