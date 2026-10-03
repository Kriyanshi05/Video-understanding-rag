import json
from pathlib import Path

from api.config import settings
from api.jobs import update_job_status
from stages.audio_extraction import extract_audio
from stages.celery_app import celery_app
from stages.chunking import chunk_transcript
from stages.embedding import embed_chunks
from stages.transcription import transcribe_audio
from stages.vector_store import ensure_collection, get_qdrant_client, store_chunks


from stages.url_download import download_from_url

@celery_app.task
def process_video_from_url(job_id, url):
    """Download video from URL non-blockingly, then process it."""
    try:
        update_job_status(job_id, "downloading")
        print(f"[{job_id}] Downloading video from URL...")
        uploads_dir = Path("data/raw/uploads")
        uploads_dir.mkdir(parents=True, exist_ok=True)
        file_path, original_title = download_from_url(url, uploads_dir)
        
        # Save the real file path and title back to the job record now that we have it
        update_job_status(job_id, "downloading", file_path=str(file_path))
        
        # Continue with standard video processing pipeline
        process_video(job_id, str(file_path))
    except Exception as exc:
        update_job_status(job_id, "failed", error=str(exc))
        print(f"[{job_id}] URL download failed with error: {exc}")
        raise exc

@celery_app.task
def process_video(job_id, file_path):
    """Extract audio, transcribe, chunk, embed, and index the video for this job."""
    try:
        update_job_status(job_id, "extracting_audio")
        print(f"[{job_id}] Extracting audio...")
        audio_path = extract_audio(file_path, Path("data/processed/audio"))

        update_job_status(job_id, "transcribing")
        print(f"[{job_id}] Transcribing audio...")
        transcript = transcribe_audio(audio_path)

        transcripts_dir = Path("data/processed/transcripts")
        transcripts_dir.mkdir(parents=True, exist_ok=True)
        transcript_path = transcripts_dir / f"{job_id}.json"

        # default=str covers numpy numbers that json cannot encode by itself.
        with transcript_path.open("w", encoding="utf-8") as handle:
            json.dump(transcript, handle, default=str)

        update_job_status(job_id, "chunking")
        chunks = chunk_transcript(transcript)

        update_job_status(job_id, "embedding")
        chunks = embed_chunks(chunks)

        update_job_status(job_id, "indexing")
        client = get_qdrant_client()
        ensure_collection(client, settings.qdrant_collection)
        store_chunks(client, settings.qdrant_collection, job_id, chunks)

        update_job_status(job_id, "done")
        print(f"[{job_id}] Processing complete! Saved to {transcript_path}")
        return {"status": "done", "job_id": job_id}

    except Exception as exc:
        update_job_status(job_id, "failed", error=str(exc))
        print(f"[{job_id}] Failed with error: {exc}")
        raise exc
