import redis
from backend.core.config import settings
import logging

logger = logging.getLogger(__name__)

redis_client = None

def get_redis_client():
    global redis_client
    if redis_client is None:
        try:
            redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
            logger.info("Redis client initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize Redis: {e}")
    return redis_client
