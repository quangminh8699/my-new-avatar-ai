import os, json
from dotenv import load_dotenv
import redis

_redis = redis.Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))

def load_env():
    # load .env in project root
    load_dotenv()

def read_bytes(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()

def push_update(job_id: str, status: str, url: str | None = None, error: str | None = None):
    """Publish job status update to Redis pubsub channel"""
    payload = {"job_id": job_id, "status": status, "url": url, "error": error}
    _redis.publish("jobs_updates", json.dumps(payload))