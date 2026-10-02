# Time-based chunking is a development-speed simplification.
# Topic-boundary-based chunking is planned for a later iteration.


def chunk_transcript(transcript_result, window_seconds=35):
    """Group aligned WhisperX words into ~window_seconds chunks with start/end times."""
    segments = (
        transcript_result.get("segments", [])
        if isinstance(transcript_result, dict)
        else transcript_result
    )

    # Flatten word-level timestamps from every segment into one timeline.
    words = []
    for segment in segments or []:
        for word in segment.get("words", []) or []:
            if "start" in word and "end" in word:
                words.append(word)

    if not words:
        return []

    chunks = []
    current_words = []
    window_start = float(words[0]["start"])

    for word in words:
        word_end = float(word["end"])
        # Close the current chunk once it would exceed the time window.
        if current_words and (word_end - window_start) > window_seconds:
            chunks.append(_chunk_from_words(current_words))
            current_words = [word]
            window_start = float(word["start"])
        else:
            current_words.append(word)

    if current_words:
        chunks.append(_chunk_from_words(current_words))

    return chunks


def _chunk_from_words(words):
    """Build one chunk dict from a consecutive list of WhisperX word objects."""
    pieces = []
    for word in words:
        token = str(word.get("word") or word.get("text") or "").strip()
        if token:
            pieces.append(token)
    return {
        "text": " ".join(pieces),
        "start_time": float(words[0]["start"]),
        "end_time": float(words[-1]["end"]),
    }
