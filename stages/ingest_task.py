import json
from pathlib import Path
from stages.celery_app import celery_app
from stages.audio_extraction import extract_audio
from stages.transcription import transcribe_audio

@celery_app.task
def process_video(job_id, file_path):
    """Extract audio, transcribe it, and write a JSON transcript for this job."""
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

        print(f"[{job_id}] Processing complete! Saved to {transcript_path}")
        return {"status": "done", "job_id": job_id}

    except Exception as exc:
        print(f"[{job_id}] Failed with error: {exc}")
        raise exc
