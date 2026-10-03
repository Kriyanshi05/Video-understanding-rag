from io import BytesIO

from PIL import Image

from retrieval.search import search_chunks  # dense-only; kept for direct use / testing
from retrieval.hybrid_search import hybrid_search_chunks  # BM25 + dense via RRF
from retrieval.reranker import rerank_chunks  # cross-encoder second-pass reranker

# Below this cosine similarity, retrieved chunks are treated as not relevant.
RELEVANCE_THRESHOLD = 0.3
GEMINI_MODEL = "gemini-2.5-flash"


from qdrant_client.models import FieldCondition, Filter, MatchValue

def answer_grounded_question(client, collection_name, job_id, question, gemini_client):
    """Answer from this video's transcript chunks only (RAG). Skip Gemini if nothing is relevant."""
    
    # 1) Check total chunk count for this video
    job_filter = Filter(must=[FieldCondition(key="job_id", match=MatchValue(value=job_id))])
    count_result = client.count(
        collection_name=collection_name,
        count_filter=job_filter,
        exact=True,
    )
    total_chunks = count_result.count
    is_small_transcript = False

    if total_chunks > 0 and total_chunks <= 8:
        is_small_transcript = True
        # Short videos have few chunks, and broad/summary questions (e.g., "what did this video teach?")
        # don't closely match any single chunk by embedding similarity, even when the content IS relevant.
        # So for small transcripts, it's more reliable to just use the whole thing than to filter by similarity score.
        scroll_res, _ = client.scroll(
            collection_name=collection_name,
            scroll_filter=job_filter,
            limit=total_chunks,
            with_payload=True,
        )
        
        chunks = []
        for point in scroll_res:
            payload = point.payload or {}
            chunks.append({
                "text": payload.get("text"),
                "start_time": payload.get("start_time"),
                "end_time": payload.get("end_time"),
                "score": 1.0,  # Force a high score
            })
        # Sort chronologically for better context
        chunks.sort(key=lambda x: x["start_time"])
        
    else:
        # STAGE 1 — HYBRID SEARCH (broad, cheap):
        # Retrieve the top-10 candidates using hybrid search (BM25 + dense vectors via RRF).
        # We ask for more than the final top_k (10 instead of 5) to give the reranker
        # a wider pool to pick from — this is the standard two-stage retrieval pattern.
        candidates = hybrid_search_chunks(client, collection_name, job_id, question, top_k=10)

        # Only apply the relevance threshold fallback if no candidates came back.
        # RRF scores are small floats (~0.016 for a strong top result).
        if not candidates or candidates[0]["score"] < 0.01:
            return {
                "mode": "ungrounded",
                "reason": "no relevant content found",
            }

        # STAGE 2 — CROSS-ENCODER RERANKING (narrow, accurate):
        # The hybrid results are good but use bi-encoder / BM25 scores that evaluate
        # query and document independently. The cross-encoder sees (query, chunk) together,
        # so it catches subtle relevance signals the first stage can miss.
        # rerank_chunks() gracefully falls back to the hybrid results as-is if the
        # model failed to load, so a reranker failure never blocks the query pipeline.
        chunks = rerank_chunks(question, candidates, top_k=5)


    context_lines = []
    for chunk in chunks:
        context_lines.append(
            f"[start_time={chunk['start_time']}s] {chunk['text']}"
        )
    context = "\n".join(context_lines)

    # We instruct Gemini to format its response cleanly in Markdown for better UI readability.
    # The required structure (Summary, Explanation, Example) ensures consistent, skimmable answers.
    if is_small_transcript:
        # A system that just refuses is less useful than one that answers fully while staying transparent about its sources.
        # For small transcripts, we bypass the similarity filter and send everything.
        # But if the transcript lacks the answer, we shouldn't just refuse.
        # Instead, answer fully, structured to show what's from the video vs general knowledge.
        prompt = (
            "You are an assistant answering a question about a video. "
            "You are provided with the complete transcript of the short video below.\n\n"
            "Please provide a complete, useful answer in a SINGLE response. Follow these rules exactly:\n"
            "1. First, answer using only what's in the transcript, with timestamp citations (e.g. [start_time=X]s), "
            "if the transcript covers the topic at all (even partially).\n"
            "2. If the transcript's coverage is incomplete or the exact detail asked about isn't explicitly stated, "
            "continue your response with a clearly separated section headed '## Beyond This Video' that completes "
            "the answer using your general knowledge. Do not stop at 'the transcript does not contain this'.\n"
            "3. If the transcript doesn't mention the topic at all, skip straight to general knowledge (using the "
            "'## Beyond This Video' heading) but open with one honest line noting this isn't from the video, "
            "then give the full answer anyway.\n\n"
            "Format your response cleanly in Markdown. Structure the video-grounded part as follows:\n"
            "- A short bolded one-line summary at the top.\n"
            "- A '## Explanation' section with the main content in clear prose or bullet points.\n"
            "- If relevant, a '## Example' section with a concrete example from the content.\n"
            "Keep it concise and well-organized.\n\n"
            f"Transcript:\n{context}\n\n"
            f"Question: {question}"
        )
    else:
        prompt = (
            "Answer the question using ONLY the transcript excerpts below. "
            "Do not use outside knowledge. Mention the timestamp(s) that support "
            "your answer (the start_time labels). "
            "Format your response cleanly in Markdown. Structure it as follows:\n"
            "- A short bolded one-line summary at the top.\n"
            "- A '## Explanation' section with the main content in clear prose or bullet points.\n"
            "- If relevant, a '## Example' section with a concrete example from the content.\n"
            "Keep it concise and well-organized, not a dense paragraph.\n\n"
            f"Transcript excerpts:\n{context}\n\n"
            f"Question: {question}"
        )

    response = gemini_client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
    )
    return {
        "mode": "grounded",
        "answer": response.text,
        "sources": chunks,
    }


def answer_general_question(question, gemini_client):
    """Answer from Gemini's own knowledge when the video has no matching transcript."""
    # We instruct Gemini to never describe its own nature or limitations (e.g. "as an AI").
    # This keeps the product's voice consistent and neutral, hiding the underlying model's self-description.
    # The UI already informs the user via a label that this is a general-knowledge fallback.
    # Ensure consistent formatting even when falling back to general knowledge,
    # matching the Markdown structure defined for grounded answers.
    prompt = (
        "Answer this question directly using your general knowledge. "
        "NEVER describe your own nature or limitations (do not say 'As an AI...', "
        "do not say 'I cannot watch videos...', etc.). Just provide a clean, confident, "
        "neutral answer to the question as a knowledgeable assistant. "
        "Format your response cleanly in Markdown. Structure it as follows:\n"
        "- A short bolded one-line summary at the top.\n"
        "- A '## Explanation' section with the main content in clear prose or bullet points.\n"
        "- If relevant, a '## Example' section with a concrete example.\n"
        "Keep it concise and well-organized.\n\n"
        f"Question: {question}"
    )
    response = gemini_client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
    )
    return {
        "mode": "general_knowledge",
        "answer": response.text,
    }


def explain_screenshot(image_bytes, question, gemini_client):
    """Describe a captured video frame using Gemini vision (image + text in one request)."""
    if not question:
        question = (
            "Explain what is shown in this image, including any code, "
            "diagrams, or text visible"
        )

    image = Image.open(BytesIO(image_bytes))
    image.load()

    response = gemini_client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[question, image],
    )
    return {
        "mode": "visual",
        "answer": response.text,
    }
