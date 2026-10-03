from retrieval.search import search_chunks
from retrieval.bm25_search import bm25_search_chunks


def hybrid_search_chunks(client, collection_name, job_id, query_text, top_k=5):
    """
    Hybrid retrieval: dense (semantic) + sparse (BM25) fused with Reciprocal Rank Fusion (RRF).

    WHY HYBRID SEARCH?
    - Dense search (embedding similarity) excels at semantic paraphrase matching:
      "How do I repeat a block?" → finds chunks about loops even if the word "loop" isn't used.
    - BM25 excels at exact keyword matching: "BM25 algorithm" → ranks chunks containing
      those exact terms highest, even if semantically similar chunks don't use them.
    - Neither alone is optimal. Hybrid search gets the benefits of both.

    HOW RECIPROCAL RANK FUSION WORKS:
    Instead of combining raw scores (which live on different scales — cosine vs BM25 TF-IDF),
    RRF uses only the *rank position* of each result in each list:

        rrf_score(chunk) = 1 / (60 + rank_dense) + 1 / (60 + rank_bm25)

    where rank is 1-indexed (best = 1). If a chunk doesn't appear in one list at all,
    its contribution from that list is 0.

    WHY THE CONSTANT 60?
    60 is a widely-used empirical default (from the original Cormack et al. 2009 RRF paper).
    It acts as a smoothing offset that:
    - Dampens the steep reward for being rank 1 vs rank 2 (without it, 1/1 - 1/2 = 0.5, huge gap)
    - Makes lower-ranked items still contribute meaningfully (1/61 vs 1/62 ≈ same)
    - Makes the combined list robust to noise in either retriever

    WHY RRF BEATS SCORE NORMALIZATION:
    Normalizing raw scores to [0,1] and averaging them is brittle — a BM25 score of 5.0
    means something very different on a 10-chunk corpus vs a 1000-chunk corpus.
    Rank is a stable, scale-free signal, which is why RRF consistently outperforms
    score fusion in benchmarks.

    Returns the top_k chunks with their RRF score as the "score" field, in the same
    shape as search_chunks() for drop-in compatibility with answer.py.
    """
    # --- Step 1: Get both ranked lists ---
    # Fetch more than top_k from each to give RRF a broader pool to merge from.
    fetch_k = max(top_k * 3, 15)
    dense_results = search_chunks(client, collection_name, job_id, query_text, top_k=fetch_k)
    bm25_results = bm25_search_chunks(client, collection_name, job_id, query_text, top_k=fetch_k)

    # --- Step 2: Build rank lookup maps ---
    # Key chunks by text content (stable, human-readable key).
    # We use text as the deduplication key because point IDs aren't returned
    # by search_chunks() — text is unique per chunk in a short video transcript.
    dense_rank = {r["text"]: idx + 1 for idx, r in enumerate(dense_results)}  # rank is 1-indexed
    bm25_rank  = {r["text"]: idx + 1 for idx, r in enumerate(bm25_results)}

    # --- Step 3: Collect all unique chunks from both lists ---
    all_chunks_by_text = {}
    for r in dense_results + bm25_results:
        key = r["text"]
        if key not in all_chunks_by_text:
            # Store the chunk payload (text, start_time, end_time) — score will be overwritten
            all_chunks_by_text[key] = {
                "text": r["text"],
                "start_time": r["start_time"],
                "end_time": r["end_time"],
            }

    # --- Step 4: Compute RRF score for every unique chunk ---
    # RRF constant k=60 (Cormack et al. 2009 default).
    K = 60
    rrf_scores = {}
    for text, chunk in all_chunks_by_text.items():
        rank_d = dense_rank.get(text, None)
        rank_b = bm25_rank.get(text, None)

        # Contribution is 0 if the chunk didn't appear in that retriever's list at all.
        score_dense = (1 / (K + rank_d)) if rank_d is not None else 0.0
        score_bm25  = (1 / (K + rank_b)) if rank_b is not None else 0.0

        rrf_scores[text] = score_dense + score_bm25

    # --- Step 5: Sort by RRF score and return top_k ---
    ranked = sorted(all_chunks_by_text.keys(), key=lambda t: rrf_scores[t], reverse=True)

    results = []
    for text in ranked[:top_k]:
        chunk = all_chunks_by_text[text]
        results.append({
            "text": chunk["text"],
            "start_time": chunk["start_time"],
            "end_time": chunk["end_time"],
            "score": rrf_scores[text],  # RRF score replaces raw cosine/BM25 score
        })
    return results
