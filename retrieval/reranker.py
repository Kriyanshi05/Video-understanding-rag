import logging
from typing import Optional

# --- Module-level model loading (cached for the lifetime of the worker process) ---
#
# WHY LOAD AT MODULE LEVEL?
# CrossEncoder weights are ~100-400 MB on disk. If we loaded inside rerank_chunks(),
# every single query would reload from disk. Loading once at import time means the
# model lives in RAM and is reused across all requests in the same worker process.
#
# WHY A CROSS-ENCODER FOR RERANKING (AND NOT AS PRIMARY RETRIEVAL)?
# There are two fundamentally different ways to compare a query to a document:
#
#   1. BI-ENCODER (what dense search uses): encodes query and document SEPARATELY
#      into vectors, then measures cosine distance. Fast — you can pre-compute all
#      document vectors and search millions in milliseconds. But the query and document
#      never "see" each other during encoding, so nuanced relevance can be missed.
#
#   2. CROSS-ENCODER: takes (query, document) as a SINGLE concatenated input and
#      outputs a single relevance score. The model's attention layers can directly
#      compare every token in the query against every token in the document.
#      This is significantly more accurate, but requires a fresh forward pass for
#      every (query, document) pair — it can't be pre-computed.
#
# CONCLUSION: Cross-encoders are too slow to run over all chunks in a large corpus
# (e.g., 1000 chunks × ~200ms each = 200 seconds per query). So we use a two-stage
# retrieval pattern:
#   STAGE 1 — Hybrid search (bi-encoder + BM25): cheap, runs over ALL chunks, returns
#             a short candidate list (e.g. top 10–15).
#   STAGE 2 — Cross-encoder reranker: expensive but accurate, runs only over the
#             small shortlist from stage 1, picks the final top k.
# This gives the accuracy of cross-encoders without their scalability cost.

_reranker = None  # will hold the loaded CrossEncoder or None if loading failed

try:
    from sentence_transformers import CrossEncoder
    # "cross-encoder/ms-marco-MiniLM-L-6-v2" is a 6-layer MiniLM fine-tuned on
    # MS MARCO (passage retrieval). It is small (~80 MB), CPU-friendly, and is
    # one of the most commonly used reranking checkpoints in practice.
    _reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
    logging.info("Reranker loaded: cross-encoder/ms-marco-MiniLM-L-6-v2")
except Exception as e:
    logging.warning(
        f"Failed to load cross-encoder reranker: {e}. "
        "Reranking will be skipped — hybrid search results will be used as-is. "
        "This may happen on first use while model weights download, or if "
        "sentence-transformers is not installed. The query pipeline will still work."
    )
    _reranker = None


def rerank_chunks(query_text: str, chunks: list, top_k: int = 5) -> list:
    """
    Second-pass reranking of a candidate chunk list using a cross-encoder model.

    WHY THIS FUNCTION EXISTS (TWO-STAGE RETRIEVAL):
    Hybrid search (stage 1) is fast and broad — it retrieves the top-N candidates
    from the full corpus efficiently. But it uses embedding vectors and BM25 which
    score query and document independently. The cross-encoder (stage 2) processes
    each (query, chunk) pair jointly, producing a more accurate relevance score.
    Running cross-encoder only over the small hybrid-search shortlist (not all chunks)
    keeps latency acceptable while dramatically improving final ranking quality.

    GRACEFUL DEGRADATION:
    If the reranker failed to load (e.g., during first-time weight download, or
    if sentence-transformers is missing), this function safely falls back to
    returning the hybrid search results unmodified, preserving the existing pipeline.

    Args:
        query_text: The user's original question.
        chunks:     List of dicts, each with at least a "text" key. Same shape as
                    hybrid_search_chunks() output.
        top_k:      How many chunks to return after reranking.

    Returns:
        List of top_k chunks, same shape as input but with "score" replaced by
        the cross-encoder relevance score. Sorted descending by relevance.
    """
    # Graceful fallback: if the model isn't available, return the hybrid results as-is.
    if _reranker is None:
        logging.warning("Reranker unavailable; returning hybrid search results unranked.")
        return chunks[:top_k]

    if not chunks:
        return []

    # Build (query, document) pairs for batch prediction.
    # The cross-encoder expects a list of [query, passage] pairs.
    pairs = [[query_text, chunk["text"]] for chunk in chunks]

    # Batch .predict() runs all pairs through the model in a single forward pass
    # (with internal batching). Much faster than calling predict() in a loop.
    try:
        scores = _reranker.predict(pairs)
    except Exception as e:
        logging.warning(f"Cross-encoder prediction failed: {e}. Falling back to hybrid results.")
        return chunks[:top_k]

    # Attach the new cross-encoder score to each chunk and sort descending.
    reranked = sorted(
        [
            {**chunk, "score": float(score)}
            for chunk, score in zip(chunks, scores)
        ],
        key=lambda x: x["score"],
        reverse=True,
    )

    return reranked[:top_k]
