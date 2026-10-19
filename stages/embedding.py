from sentence_transformers import SentenceTransformer

_model = None  # Populated on first use; None until then.


def get_embedding_model() -> SentenceTransformer:
    """
    Lazy loader for the SentenceTransformer embedding model.

    WHY LAZY LOADING?
    Deferring model loading reduces peak memory pressure: the Celery worker
    imports this module on startup, but not every worker process will ever
    run an embedding or query task. Loading on first use spreads memory
    allocation over time instead of concentrating it all at worker startup.
    The loaded model is cached in the module-level variable so subsequent
    calls within the same worker process are instant.
    """
    global _model
    if _model is None:
        # all-MiniLM-L6-v2 produces 384-dimensional embeddings.
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def embed_chunks(chunks):
    """Add a JSON-serializable embedding list to each chunk dict."""
    embedding_model = get_embedding_model()
    for chunk in chunks:
        vector = embedding_model.encode(chunk["text"])
        chunk["embedding"] = vector.tolist()
    return chunks
