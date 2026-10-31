"""
Generate suggested questions for a video's content — once per video, cached in Redis.

WHY CACHE ONCE PER VIDEO (not per query / per page view):
    Generating suggestions requires one Gemini LLM call. If we generated them on
    every page load, a popular video would burn through API quota quickly for no
    benefit — the transcript doesn't change after ingest. By caching the result
    in Redis under f"suggestions:{job_id}", we pay exactly ONE LLM call per video
    for the lifetime of the cache and serve every subsequent request from memory.
    If the call fails for any reason (rate-limit, parse error, etc.), we return
    an empty list WITHOUT caching so the next request can retry.
"""

import json
import re

from qdrant_client.models import FieldCondition, Filter, MatchValue

from api.jobs import redis_client
from retrieval.llm_utils import generate_with_retry  # transient-error retry wrapper

# Gemini model used for generating suggestion chips.
GEMINI_MODEL = "gemini-2.5-flash"

# Maximum character budget for the transcript fed into the prompt.
# This is generous enough for Gemini to understand the whole video but small
# enough to keep the request fast and within token limits.
_MAX_TRANSCRIPT_CHARS = 6000


def get_suggested_questions(
    job_id: str,
    qdrant_client,
    collection_name: str,
    gemini_client,
) -> list[str]:
    """Return up to 3 specific suggested questions for a processed video.

    1. If a cached result exists in Redis, return it immediately.
    2. Otherwise, build a representative transcript from Qdrant chunks,
       ask Gemini for 3 short questions, cache the result, and return it.
    3. On ANY failure (no chunks, Gemini error, parse error), return []
       without caching so a future call can retry.
    """

    # ── 1. Check Redis cache ─────────────────────────────────────────────
    cache_key = f"suggestions:{job_id}"
    cached = redis_client.get(cache_key)
    if cached is not None:
        try:
            return json.loads(cached)
        except (json.JSONDecodeError, TypeError):
            pass  # Corrupted cache entry — regenerate below.

    # ── 2. Fetch this video's chunks from Qdrant ─────────────────────────
    try:
        job_filter = Filter(
            must=[FieldCondition(key="job_id", match=MatchValue(value=job_id))]
        )

        all_chunks: list[dict] = []
        offset = None

        while True:
            batch, next_offset = qdrant_client.scroll(
                collection_name=collection_name,
                scroll_filter=job_filter,
                limit=256,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            for point in batch:
                payload = point.payload or {}
                text = payload.get("text", "")
                start_time = payload.get("start_time", 0)
                if text:
                    all_chunks.append({"text": text, "start_time": start_time})
            if next_offset is None:
                break
            offset = next_offset

        if not all_chunks:
            return []

        # Sort chronologically so we can sample evenly across the video.
        all_chunks.sort(key=lambda c: c["start_time"])

        # ── Build a representative transcript ────────────────────────────
        # If the full transcript fits within the budget, use it all.
        # Otherwise, sample chunks evenly so the questions cover the whole
        # video and not just the beginning.
        full_transcript = " ".join(c["text"] for c in all_chunks)

        if len(full_transcript) <= _MAX_TRANSCRIPT_CHARS:
            transcript = full_transcript
        else:
            # Take evenly spaced chunks until we fill the budget.
            n = len(all_chunks)
            selected_texts: list[str] = []
            total_len = 0

            # Start by estimating how many chunks we can fit, then pick
            # evenly spaced indices.
            avg_len = len(full_transcript) / n
            target_count = max(3, int(_MAX_TRANSCRIPT_CHARS / avg_len))
            step = max(1, n // target_count)

            for i in range(0, n, step):
                chunk_text = all_chunks[i]["text"]
                if total_len + len(chunk_text) > _MAX_TRANSCRIPT_CHARS:
                    break
                selected_texts.append(chunk_text)
                total_len += len(chunk_text) + 1  # +1 for space

            transcript = " ".join(selected_texts)

    except Exception:
        # Qdrant unreachable or other unexpected error — don't crash.
        return []

    # ── 3. Ask Gemini for 3 suggested questions ──────────────────────────
    prompt = (
        "You are given the transcript of a video. Generate exactly 3 short, specific "
        "questions (each UNDER 12 words) that this video's content can actually answer. "
        "The questions should be concrete and tied to specific details, facts, or "
        "explanations found in the transcript.\n\n"
        "Rules:\n"
        "- Respond ONLY with a JSON array of 3 strings.\n"
        "- No extra text, no markdown fences, no explanation.\n"
        "- Do NOT include generic questions like 'What is this video about?' or "
        "'What topics are covered?' — generic chips are handled separately in the UI.\n\n"
        f"Transcript:\n{transcript}"
    )

    try:
        response = generate_with_retry(
            gemini_client,
            model=GEMINI_MODEL,
            contents=prompt,
        )
        raw = response.text or ""
    except Exception:
        # Gemini error (rate-limit, network, etc.) — return empty, don't cache.
        return []

    # ── 4. Defensively parse the response ────────────────────────────────
    try:
        # Strip markdown code fences if the model wrapped its answer.
        cleaned = raw.strip()
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        cleaned = cleaned.strip()

        parsed = json.loads(cleaned)

        # Validate: must be a list of strings.
        if not isinstance(parsed, list):
            return []
        questions = [q for q in parsed if isinstance(q, str) and q.strip()]
        questions = questions[:3]  # Cap at 3 even if the model returned more.

        if not questions:
            return []
    except (json.JSONDecodeError, TypeError, ValueError):
        return []

    # ── 5. Cache and return ──────────────────────────────────────────────
    redis_client.set(cache_key, json.dumps(questions))
    return questions
