import hashlib
import mimetypes
import re
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

from celery.result import AsyncResult
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from api.config import settings
from api.gemini_client import get_gemini_client
from api.jobs import create_job, get_job, redis_client
from retrieval.answer import (
    answer_general_question,
    answer_grounded_question,
    explain_screenshot,
)
from retrieval.suggestions import get_suggested_questions
from stages.celery_app import celery_app
from stages.ingest_task import process_video
from stages.test_task import add_numbers
from stages.vector_store import get_qdrant_client
from stages.url_download import download_from_url

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


# === PART 2: BASIC CACHING BY VIDEO ID ===
def extract_youtube_id(url: str) -> str | None:
    """Extract YouTube video ID from various YouTube URL formats."""
    parsed = urlparse(url)
    hostname = parsed.netloc.lower()

    if "youtube.com" in hostname:
        query = parse_qs(parsed.query)
        if "v" in query and query["v"]:
            return query["v"][0]
        parts = [p for p in parsed.path.split("/") if p]
        if parts and parts[0] in ("embed", "v", "shorts") and len(parts) > 1:
            return parts[1]
    elif "youtu.be" in hostname:
        parts = [p for p in parsed.path.split("/") if p]
        if parts:
            return parts[0]

    match = re.search(r"(?:v=|\/|youtu\.be\/|embed\/|shorts\/)([a-zA-Z0-9_-]{11})", url)
    if match:
        return match.group(1)

    return None


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

    # === PART 2: BASIC CACHING BY VIDEO ID ===
    # Compute SHA256 in chunks to hash without loading entire file into memory at once
    hasher = hashlib.sha256()
    while chunk := await file.read(1024 * 1024):
        hasher.update(chunk)
    file_hash = hasher.hexdigest()
    await file.seek(0)

    # Check Redis for a completed job with this file hash
    cached_job_id = redis_client.get(f"video_cache:{file_hash}")
    if cached_job_id:
        cached_job = get_job(cached_job_id)
        if cached_job and cached_job.get("status") == "done":
            return {"job_id": cached_job_id, "status": "done", "cached": True}

    # Job not cached: proceed with saving and queueing
    job_id = str(uuid4())

    uploads_dir = Path("data/raw/uploads")
    uploads_dir.mkdir(parents=True, exist_ok=True)
    file_path = uploads_dir / f"{job_id}_{original_filename}"
    file_path.write_bytes(await file.read())

    create_job(job_id, original_filename, str(file_path), video_identifier=file_hash)
    process_video.delay(job_id, str(file_path))
    return {"job_id": job_id, "status": "queued"}


from stages.ingest_task import process_video, process_video_from_url

class IngestUrlBody(BaseModel):
    url: str

@app.post("/ingest-url")
def ingest_url(body: IngestUrlBody):
    """
    Alternative ingest method: queue a background job to download a video from a URL using yt-dlp,
    which then automatically continues with the standard pipeline.
    """
    # === PART 2: BASIC CACHING BY VIDEO ID ===
    # Compute stable identifier (YouTube ID or normalized URL)
    yt_id = extract_youtube_id(body.url)
    identifier = yt_id if yt_id else body.url.strip()

    # Check Redis for a completed job with this identifier
    cached_job_id = redis_client.get(f"video_cache:{identifier}")
    if cached_job_id:
        cached_job = get_job(cached_job_id)
        if cached_job and cached_job.get("status") == "done":
            return {"job_id": cached_job_id, "status": "done", "cached": True}

    # Job not cached: create job and queue background task
    job_id = str(uuid4())
    create_job(job_id, body.url, "", video_identifier=identifier)
    process_video_from_url.delay(job_id, body.url)
    
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


@app.get("/media/{job_id}")
def get_media(job_id: str):
    """
    Serve the original video file for the frontend <video> element.
    Provides the correct media_type (e.g. video/mp4) for streaming.
    """
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    
    file_path = Path(job["file_path"])
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Video file no longer exists on disk.")
    
    media_type, _ = mimetypes.guess_type(str(file_path))
    return FileResponse(file_path, media_type=media_type or "video/mp4")


class QueryBody(BaseModel):
    question: str
    # Optional speaker filter: when set (e.g. "SPEAKER_01"), the answer is grounded
    # only in chunks from that speaker. The frontend sends the raw pyannote label here;
    # the friendly display name ("Speaker 2") is a frontend-only mapping.
    speaker: str | None = None


@app.get("/speakers/{job_id}")
def get_speakers(job_id: str):
    """
    Return all unique speaker labels found in this video's Qdrant chunks.

    The frontend uses this to decide whether to show the speaker-filter pill row.
    Only videos with more than one speaker will show the filter UI — single-speaker
    videos and those without diarization data stay clean.

    Response: {"speakers": ["SPEAKER_00", "SPEAKER_01", ...]}
    """
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' was not found.")

    qdrant = get_qdrant_client()
    collection = settings.qdrant_collection

    # Scroll through all chunks for this job and collect unique speaker values.
    # We use scroll (not search) because we want every chunk, not just semantically
    # similar ones — we're building a list, not answering a question.
    from qdrant_client.models import FieldCondition, Filter, MatchValue

    job_filter = Filter(must=[FieldCondition(key="job_id", match=MatchValue(value=job_id))])
    speakers: set[str] = set()
    offset = None

    while True:
        batch, next_offset = qdrant.scroll(
            collection_name=collection,
            scroll_filter=job_filter,
            limit=256,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        for point in batch:
            payload = point.payload or {}
            spk = payload.get("speaker")
            if spk:
                speakers.add(spk)
        if next_offset is None:
            break
        offset = next_offset

    # Return speakers sorted for stable ordering in the UI pill row.
    return {"speakers": sorted(speakers)}


@app.get("/suggestions/{job_id}")
def get_suggestions(job_id: str):
    """Return cached (or freshly generated) suggested questions for a video.

    These are video-specific question chips shown in the empty-state chat panel.
    If the job doesn't exist or isn't fully processed yet, we return an empty list
    rather than an error so the frontend can treat this as a graceful no-op.
    """
    job = get_job(job_id)
    if job is None or job.get("status") != "done":
        return {"suggestions": []}

    qdrant = get_qdrant_client()
    gemini = get_gemini_client()
    suggestions = get_suggested_questions(
        job_id, qdrant, settings.qdrant_collection, gemini
    )
    return {"suggestions": suggestions}


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
        speaker=body.speaker,  # None means "all speakers"; a raw label like "SPEAKER_01" scopes retrieval
    )
    if result["mode"] == "ungrounded":
        result = answer_general_question(body.question, gemini)
        result["fallback_used"] = True
        # === PART 1: RETRIEVAL-PATH BADGE ===
        result["retrieval_path"] = "general_knowledge"
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
