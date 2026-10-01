from celery import Celery

from api.config import settings

# Celery app: Redis is both the message broker (queue) and the result store.
celery_app = Celery(
    "video_rag",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["stages.test_task", "stages.ingest_task"],  # load tasks on worker start
)
