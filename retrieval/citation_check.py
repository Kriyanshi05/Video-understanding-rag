import json
import logging

# The verification model: we use a lighter/faster model than the main answer model.
# This is an intentional design choice — verification is a simpler task (yes/no JSON)
# and using a faster model keeps the added latency minimal.
VERIFY_MODEL = "gemini-2.0-flash"


def verify_citations(answer_text: str, source_chunks: list, gemini_client) -> dict:
    """
    Second-pass citation verification: asks Gemini to check whether the key
    factual claims in `answer_text` are actually supported by `source_chunks`.

    WHY A SEPARATE VERIFICATION CALL RATHER THAN SELF-CHECKING IN THE SAME PROMPT?
    There are two compelling reasons to split this into its own call:

    1. FOCUSED TASK = HIGHER RELIABILITY
       The main generation prompt is already complex (format in Markdown, cite timestamps,
       structure the response, etc.). Adding "and also grade your own factual accuracy"
       to the same prompt creates task interference — the model is optimising for a
       fluent, well-formatted answer AND simultaneously for honest self-critique, which
       are in tension. A dedicated prompt with a single, constrained task (→ output JSON
       with verified/confidence/note) produces a more reliable signal.

    2. POSITION BIAS & SELF-SERVING BIAS
       LLMs tend to affirm their own outputs when asked to self-evaluate in the same
       context window — the generation and the critique share the same hidden state,
       so the model has already "committed" to the answer. A fresh call without the
       prior generation in its context sees the answer and sources more neutrally,
       similar to how peer review in science is done by a different person, not the author.

    GRACEFUL DEGRADATION:
    Any failure (API error, JSON parse error, unexpected response shape) returns
    {"verified": None, "confidence": None, "note": "Verification unavailable"} and
    logs a warning. Verification failures NEVER propagate exceptions upward — the
    main answer is always returned to the user regardless.

    Args:
        answer_text:   The LLM-generated answer string to verify.
        source_chunks: The reranked list of chunks that were used as context for the answer.
                       Each chunk is a dict with at least "text", "start_time", "end_time".
        gemini_client: The shared Gemini API client.

    Returns:
        dict with keys:
            "verified":   True | False | None
            "confidence": "high" | "medium" | "low" | None
            "note":       str — explanation of any concern, or "" if fully verified.
    """
    FALLBACK = {"verified": None, "confidence": None, "note": "Verification unavailable"}

    if not source_chunks or not answer_text:
        return FALLBACK

    # Build a labelled source block so Gemini can directly match claims to timestamps.
    source_lines = [
        f"[{i+1}] [{chunk.get('start_time', '?')}s–{chunk.get('end_time', '?')}s] {chunk.get('text', '')}"
        for i, chunk in enumerate(source_chunks)
    ]
    sources_text = "\n".join(source_lines)

    # We request strict JSON output with a constrained schema to make parsing reliable.
    # The prompt instructs Gemini NOT to be pedantic about wording — only key factual
    # claims matter, not whether every adjective is sourced.
    verification_prompt = (
        "You are a fact-checking assistant. You will be given an ANSWER and a list of SOURCE EXCERPTS.\n"
        "Your task: check whether the KEY FACTUAL CLAIMS in the answer are supported by the sources.\n\n"
        "Rules:\n"
        "- Do NOT be pedantic about exact wording. If a claim is clearly supported by the substance "
        "of the sources (even if phrased differently), consider it verified.\n"
        "- Focus only on factual claims, not opinions, summaries, or framing.\n"
        "- Respond in valid JSON only, with exactly these fields:\n"
        '  {"verified": true/false, "confidence": "high"/"medium"/"low", "note": "short explanation or empty string"}\n\n'
        f"SOURCES:\n{sources_text}\n\n"
        f"ANSWER:\n{answer_text}\n\n"
        "Respond with JSON only. No markdown fences, no extra text."
    )

    try:
        response = gemini_client.models.generate_content(
            model=VERIFY_MODEL,
            contents=verification_prompt,
        )
        raw = response.text.strip()

        # Strip markdown code fences if the model wraps its output (common failure mode).
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        parsed = json.loads(raw)

        # Validate shape defensively — if any expected key is missing, fall back.
        verified = parsed.get("verified")
        confidence = parsed.get("confidence")
        note = parsed.get("note", "")

        if not isinstance(verified, bool) or confidence not in ("high", "medium", "low"):
            logging.warning(f"Citation check returned unexpected shape: {parsed}")
            return FALLBACK

        return {
            "verified": verified,
            "confidence": confidence,
            "note": note,
        }

    except Exception as e:
        logging.warning(f"Citation verification failed: {e}")
        return FALLBACK
