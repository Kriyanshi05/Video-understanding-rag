from io import BytesIO

from PIL import Image

from retrieval.search import search_chunks

# Below this cosine similarity, retrieved chunks are treated as not relevant.
RELEVANCE_THRESHOLD = 0.3
GEMINI_MODEL = "gemini-2.5-flash"


def answer_grounded_question(client, collection_name, job_id, question, gemini_client):
    """Answer from this video's transcript chunks only (RAG). Skip Gemini if nothing is relevant."""
    chunks = search_chunks(client, collection_name, job_id, question)

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

    prompt = (
        "Answer the question using ONLY the transcript excerpts below. "
        "Do not use outside knowledge. Mention the timestamp(s) that support "
        "your answer (the start_time labels).\n\n"
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
    prompt = (
        "Answer this question using your own general knowledge. "
        "Start your answer with a short note that this is general knowledge "
        "and is not taken from the video.\n\n"
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
