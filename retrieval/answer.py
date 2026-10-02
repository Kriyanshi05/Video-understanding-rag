from io import BytesIO

from PIL import Image

from retrieval.search import search_chunks

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

    if total_chunks > 0 and total_chunks <= 8:
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
        # For larger videos (or 0 chunks), do a semantic search.
        chunks = search_chunks(client, collection_name, job_id, question)
        
        # Only apply the similarity threshold fallback logic for videos ABOVE that chunk count
        if not chunks or chunks[0]["score"] < RELEVANCE_THRESHOLD:
            return {
                "mode": "ungrounded",
                "reason": "no relevant content found",
            }

    context_lines = []
    for chunk in chunks:
        context_lines.append(
            f"[start_time={chunk['start_time']}s] {chunk['text']}"
        )
    context = "\n".join(context_lines)

    # We instruct Gemini to format its response cleanly in Markdown for better UI readability.
    # The required structure (Summary, Explanation, Example) ensures consistent, skimmable answers.
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
