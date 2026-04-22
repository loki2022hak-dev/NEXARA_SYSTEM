import datetime
import redis.asyncio as redis
from app.core.config import REDIS_URL

redis_client = redis.from_url(REDIS_URL) if REDIS_URL else None
memory_cache = {}

TIER_LIMITS = {"GUEST": 1, "LITE": 50, "PRO": 999999, "ELITE": 999999}

async def check_rate_limit(user_id: int, tier: str) -> bool:
    limit = TIER_LIMITS.get(tier, 1)
    today = str(datetime.date.today())
    key = f"usage:{user_id}:{today}"
    
    if redis_client:
        current = await redis_client.get(key)
        current = int(current) if current else 0
        if current >= limit: return False
        await redis_client.incr(key)
        await redis_client.expire(key, 86400)
        return True
    else:
        current = memory_cache.get(key, 0)
        if current >= limit: return False
        memory_cache[key] = current + 1
        return True
