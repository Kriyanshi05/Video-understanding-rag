from celery.result import AsyncResult
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.config import settings
from stages.celery_app import celery_app
from stages.test_task import add_numbers

# FastAPI application instance.
app = FastAPI(title="Video Understanding RAG API")

# Allow the browser frontend to call this API from any origin for now.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    """Simple liveness check that also reports the current environment."""
    return {"status": "ok", "environment": settings.ENVIRONMENT}


@app.post("/test-task")
def enqueue_test_task(x: int, y: int):
    """Enqueue add_numbers on a Celery worker; return the job id immediately."""
    async_result = add_numbers.delay(x, y)
    return {"task_id": async_result.id}


@app.get("/test-task/{task_id}")
def get_test_task(task_id: str):
    """Look up a Celery job by id and return its state (and result when finished)."""
    async_result = AsyncResult(task_id, app=celery_app)
    payload = {"state": async_result.state}
    if async_result.ready():
        payload["result"] = async_result.result
    return payload
