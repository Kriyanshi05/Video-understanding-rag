import json
import redis
from api.config import settings

# In-memory dicts don't work across separate processes (API vs Celery worker),
# Redis gives both processes a shared, consistent view of job state.
redis_client = redis.Redis.from_url(settings.redis_url, decode_responses=True)


def create_job(job_id: str, filename: str, file_path: str) -> dict:
    """Register a new ingest job with status 'queued'."""
    job = {
        "status": "queued",
        "filename": filename,
        "file_path": file_path,
        "error": None,  # filled in if process_video fails
    }
    redis_client.set(f"job:{job_id}", json.dumps(job))
    return job


def get_job(job_id: str) -> dict | None:
    """Return the job dict, or None if this job_id was never created."""
    job_str = redis_client.get(f"job:{job_id}")
    if job_str:
        return json.loads(job_str)
    return None


def update_job_status(job_id: str, status: str, error: str | None = None):
    """Reads the existing job JSON, updates the status/error fields, and writes it back."""
    job = get_job(job_id)
    if job:
        job["status"] = status
        if error is not None:
            job["error"] = error
        redis_client.set(f"job:{job_id}", json.dumps(job))
