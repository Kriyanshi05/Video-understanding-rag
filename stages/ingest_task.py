import json
from pathlib import Path

from api.config import settings
from api.jobs import jobs_db
from stages.audio_extraction import extract_audio
from stages.celery_app import celery_app
from stages.chunking import chunk_transcript
from stages.embedding import embed_chunks
from stages.transcription import transcribe_audio
from stages.vector_store import ensure_collection, get_qdrant_client, store_chunks


def _set_job_status(job_id, status):
    """Update jobs_db when this process has the job record (in-memory, per process)."""
    job = jobs_db.get(job_id)
    if job is not None:
        job["status"] = status


@celery_app.task
def process_video(job_id, file_path):
    """Extract audio, transcribe, chunk, embed, and index the video for this job."""
    try:
        print(f"[{job_id}] Extracting audio...")
        audio_path = extract_audio(file_path, Path("data/processed/audio"))

        print(f"[{job_id}] Transcribing audio...")
        transcript = transcribe_audio(audio_path)

        transcripts_dir = Path("data/processed/transcripts")
        transcripts_dir.mkdir(parents=True, exist_ok=True)
        transcript_path = transcripts_dir / f"{job_id}.json"

        # default=str covers numpy numbers that json cannot encode by itself.
        with transcript_path.open("w", encoding="utf-8") as handle:
            json.dump(transcript, handle, default=str)

        _set_job_status(job_id, "chunking")
        chunks = chunk_transcript(transcript)

        _set_job_status(job_id, "embedding")
        chunks = embed_chunks(chunks)

        _set_job_status(job_id, "indexing")
        client = get_qdrant_client()
        ensure_collection(client, settings.qdrant_collection)
        store_chunks(client, settings.qdrant_collection, job_id, chunks)

        _set_job_status(job_id, "done")
        print(f"[{job_id}] Processing complete! Saved to {transcript_path}")
        return {"status": "done", "job_id": job_id}

    except Exception as exc:
        print(f"[{job_id}] Failed with error: {exc}")
        raise exc
