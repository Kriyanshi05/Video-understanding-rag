from pathlib import Path
from uuid import uuid4

from celery.result import AsyncResult
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from api.config import settings
from api.gemini_client import get_gemini_client
from api.jobs import create_job, get_job
from retrieval.answer import (
    answer_general_question,
    answer_grounded_question,
    explain_screenshot,
)
from stages.celery_app import celery_app
from stages.ingest_task import process_video
from stages.test_task import add_numbers
from stages.vector_store import get_qdrant_client

# Video formats we currently accept for ingest.
ALLOWED_VIDEO_SUFFIXES = {".mp4", ".mov", ".mkv", ".webm"}

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


@app.post("/ingest")
async def ingest_video(file: UploadFile = File(...)):
    """Accept a video upload, save it to disk, and queue a background job."""
    original_filename = Path(file.filename or "").name
    suffix = Path(original_filename).suffix.lower()
    if suffix not in ALLOWED_VIDEO_SUFFIXES:
        raise HTTPException(
            status_code=400,
            detail="Filename must end in .mp4, .mov, .mkv, or .webm.",
        )

    job_id = str(uuid4())

    uploads_dir = Path("data/raw/uploads")
    uploads_dir.mkdir(parents=True, exist_ok=True)
    file_path = uploads_dir / f"{job_id}_{original_filename}"
    file_path.write_bytes(await file.read())

    create_job(job_id, original_filename, str(file_path))
    process_video.delay(job_id, str(file_path))
    return {"job_id": job_id, "status": "queued"}


@app.get("/ingest/{job_id}")
def get_ingest_job(job_id: str):
    """Return the stored job record, or 404 if this job_id is unknown."""
    job = get_job(job_id)
    if job is None:
        raise HTTPException(
            status_code=404,
            detail=f"Job '{job_id}' was not found.",
        )
    return job


class QueryBody(BaseModel):
    question: str


@app.post("/query/{job_id}")
def query_video(job_id: str, body: QueryBody):
    """Grounded RAG first; if chunks are too weak, fall back to general Gemini knowledge."""
    qdrant = get_qdrant_client()
    gemini = get_gemini_client()
    result = answer_grounded_question(
        qdrant,
        settings.qdrant_collection,
        job_id,
        body.question,
        gemini,
    )
    if result["mode"] == "ungrounded":
        result = answer_general_question(body.question, gemini)
        result["fallback_used"] = True
    return result


@app.post("/explain-screen")
async def explain_screen(
    file: UploadFile = File(...),
    question: str | None = Form(None),
    job_id: str | None = None,  # accepted for later video context; ignored for now
):
    """Multimodal frame explanation. job_id is unused until we add per-video visual context."""
    image_bytes = await file.read()
    gemini = get_gemini_client()
    return explain_screenshot(image_bytes, question, gemini)
