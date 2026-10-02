from uuid import uuid4

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from api.config import settings


def get_qdrant_client():
    """Return a Qdrant client pointed at the URL from settings."""
    return QdrantClient(url=settings.qdrant_url)


def ensure_collection(client, collection_name, vector_size=384):
    """Create the collection if it is missing. 384 matches MiniLM embedding size."""
    if client.collection_exists(collection_name):
        return
    # Cosine distance is the usual metric for sentence-transformer vectors.
    client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
    )


def store_chunks(client, collection_name, job_id, chunks):
    """Upsert each chunk as a Qdrant point: vector + searchable payload."""
    points = []
    for chunk in chunks:
        points.append(
            PointStruct(
                id=str(uuid4()),
                vector=chunk["embedding"],
                payload={
                    "job_id": job_id,
                    "text": chunk["text"],
                    "start_time": chunk["start_time"],
                    "end_time": chunk["end_time"],
                },
            )
        )
    if points:
        client.upsert(collection_name=collection_name, points=points)
