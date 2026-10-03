import logging

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
        segment_words = segment.get("words")
        
        # DEFENSIVE HANDLING: If a segment has no word-level timestamps (e.g. alignment failed/skipped)
        if not segment_words:
            logging.warning(f"Segment missing word-level timestamps, using segment fallback: {segment.get('text', '').strip()[:30]}...")
            if "start" in segment and "end" in segment:
                words.append({
                    "word": segment.get("text", ""),
                    "start": segment["start"],
                    "end": segment["end"]
                })
            continue

        for word in segment_words:
            if "start" in word and "end" in word:
                words.append(word)
            else:
                logging.warning(f"Word missing timestamps, skipping: {word.get('word', '')}")

    if not words:
        logging.warning("No words or segments found to chunk.")
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
