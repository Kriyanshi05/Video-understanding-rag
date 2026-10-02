from sentence_transformers import SentenceTransformer

# Load MiniLM once at import time so Celery does not re-download/reload it per job.
# all-MiniLM-L6-v2 produces 384-dimensional embeddings.


def load_embedding_model():
    """Create the sentence-transformer model used for chunk embeddings."""
    return SentenceTransformer("all-MiniLM-L6-v2")


embedding_model = load_embedding_model()
# Alias used by retrieval/search.py (same object, loaded once).
model = embedding_model


def embed_chunks(chunks):
    """Add a JSON-serializable embedding list to each chunk dict."""
    for chunk in chunks:
        vector = embedding_model.encode(chunk["text"])
        chunk["embedding"] = vector.tolist()
    return chunks
