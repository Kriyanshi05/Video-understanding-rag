from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.config import settings

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
