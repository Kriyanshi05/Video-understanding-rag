from qdrant_client.models import FieldCondition, Filter, MatchValue
from stages.embedding import model

def search_chunks(client, collection_name, job_id, query_text, top_k=5):
    """Embed the query and return the nearest transcript chunks for one video."""
    query_vector = model.encode(query_text).tolist()

    # Filter by job_id so searching one video does not return chunks from
    # other videos that share the same Qdrant collection.
    response = client.query_points(
        collection_name=collection_name,
        query=query_vector,
        query_filter=Filter(
            must=[
                FieldCondition(key="job_id", match=MatchValue(value=job_id)),
            ]
        ),
        limit=top_k,
        with_payload=True,
    )
    hits = response.points

    results = []
    for hit in hits:
        payload = hit.payload or {}
        results.append(
            {
                "text": payload.get("text"),
                "start_time": payload.get("start_time"),
                "end_time": payload.get("end_time"),
                "score": hit.score,
            }
        )
    return results
