from qdrant_client.models import FieldCondition, Filter, MatchValue
from stages.embedding import get_embedding_model


def search_chunks(client, collection_name, job_id, query_text, top_k=5, speaker=None):
    """Embed the query and return the nearest transcript chunks for one video.

    The optional `speaker` argument adds a second Qdrant filter condition so that
    only chunks attributed to that speaker are returned. This enables per-speaker
    scoping without a separate collection or index.
    """
    query_vector = get_embedding_model().encode(query_text).tolist()

    # Build filter conditions. Always restrict by job_id; optionally also by speaker.
    filter_conditions = [FieldCondition(key="job_id", match=MatchValue(value=job_id))]
    if speaker:
        filter_conditions.append(
            FieldCondition(key="speaker", match=MatchValue(value=speaker))
        )

    # Filter by job_id so searching one video does not return chunks from
    # other videos that share the same Qdrant collection.
    response = client.query_points(
        collection_name=collection_name,
        query=query_vector,
        query_filter=Filter(must=filter_conditions),
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
                "speaker": payload.get("speaker", "SPEAKER_00"),
                "score": hit.score,
            }
        )
    return results
