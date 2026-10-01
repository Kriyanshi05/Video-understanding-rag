# Placeholder for a real database (e.g. PostgreSQL). This module-level dict is
# used for development speed only: it will NOT persist if the server restarts
# and will NOT work correctly with multiple worker processes (each process
# has its own copy of this dict).

jobs_db = {}


def create_job(job_id: str, filename: str, file_path: str) -> dict:
    """Register a new ingest job with status 'queued'."""
    jobs_db[job_id] = {
        "status": "queued",
        "filename": filename,
        "file_path": file_path,
        "error": None,  # filled in if process_video fails
    }
    return jobs_db[job_id]


def get_job(job_id: str) -> dict | None:
    """Return the job dict, or None if this job_id was never created."""
    return jobs_db.get(job_id)
