from rank_bm25 import BM25Okapi
from qdrant_client.models import FieldCondition, Filter, MatchValue


def bm25_search_chunks(client, collection_name, job_id, query_text, top_k=5):
    """
    Keyword-based BM25 search over all transcript chunks for a given job.

    How it works:
    - All chunks for this job_id are fetched from Qdrant via a scroll (no embedding needed).
    - A BM25Okapi index is built in-memory over just those chunks for this request.
    - The query is tokenized and scored against every chunk, returning the top_k results.

    NOTE ON IN-MEMORY INDEX:
    This rebuilds the BM25 index fresh on every request, rather than persisting it.
    That is acceptable at this project's scale — short videos have at most ~20-50 chunks,
    so the build is instantaneous. At larger scale (thousands of chunks per video, or many 
    concurrent users), you would pre-build and cache the index (e.g., in Redis or on disk)
    and only rebuild it when new chunks are added.

    Returns a list of dicts in the same shape as search_chunks():
      [{"text": ..., "start_time": ..., "end_time": ..., "score": float}, ...]
    """
    job_filter = Filter(must=[FieldCondition(key="job_id", match=MatchValue(value=job_id))])

    # Fetch ALL chunks for this job using scroll (no vector, no semantic search).
    # We request a large limit to capture every chunk in one call.
    all_points = []
    offset = None
    while True:
        batch, next_offset = client.scroll(
            collection_name=collection_name,
            scroll_filter=job_filter,
            limit=256,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        all_points.extend(batch)
        if next_offset is None:
            break
        offset = next_offset

    if not all_points:
        return []

    # Extract text and metadata from each point.
    # BM25 needs a corpus of tokenized documents.
    payloads = [p.payload or {} for p in all_points]
    texts = [p.get("text", "") for p in payloads]
    point_ids = [p.id for p in all_points]

    # Simple whitespace tokenizer — lowercase and split on spaces.
    # We deliberately avoid a heavy NLP tokenizer (NLTK, spaCy) to keep
    # the dependency footprint small and startup fast for a demo project.
    tokenized_corpus = [t.lower().split() for t in texts]
    tokenized_query = query_text.lower().split()

    # Build the BM25 index and score every chunk against the query.
    bm25 = BM25Okapi(tokenized_corpus)
    scores = bm25.get_scores(tokenized_query)

    # Pair each point with its BM25 score and sort descending.
    scored = sorted(
        zip(all_points, payloads, scores),
        key=lambda x: x[2],
        reverse=True,
    )

    results = []
    for point, payload, score in scored[:top_k]:
        results.append({
            "text": payload.get("text"),
            "start_time": payload.get("start_time"),
            "end_time": payload.get("end_time"),
            "score": float(score),
            "_point_id": str(point.id),  # internal key for RRF deduplication
        })
    return results
