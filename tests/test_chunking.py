# tests/test_chunking.py
# Verifies that chunk_transcript() in stages/chunking.py:
#   - groups words into chunks that respect the time-window boundary
#   - records correct start_time and end_time on every chunk
#   - assigns the dominant speaker to each chunk
#   - handles segments that have only segment-level timestamps (no per-word
#     timestamps) without raising an exception

import pytest

from stages.chunking import chunk_transcript


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _word(word, start, end, speaker="SPEAKER_00"):
    """Build a minimal WhisperX word dict."""
    return {"word": word, "start": start, "end": end, "speaker": speaker}


def _seg(words=None, start=None, end=None, text="", speaker="SPEAKER_00"):
    """Build a minimal WhisperX segment dict."""
    seg = {"text": text, "speaker": speaker}
    if words is not None:
        seg["words"] = words
    if start is not None:
        seg["start"] = start
    if end is not None:
        seg["end"] = end
    return seg


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestChunkTranscriptTimeWindow:
    """chunks respect the time-window boundary (default 35 s)."""

    def test_all_words_in_one_window_produce_one_chunk(self):
        # 3 words inside 0–30 s — well within the 35 s default window
        seg = _seg(words=[
            _word("Hello", 0.0, 1.0),
            _word("world", 10.0, 11.0),
            _word("today", 29.0, 30.0),
        ])
        chunks = chunk_transcript({"segments": [seg]})
        assert len(chunks) == 1

    def test_words_spanning_two_windows_produce_two_chunks(self):
        # First word at 0–1 s, second at 36–37 s → 36 s gap exceeds default 35 s window
        seg = _seg(words=[
            _word("first", 0.0, 1.0),
            _word("second", 36.0, 37.0),
        ])
        chunks = chunk_transcript({"segments": [seg]})
        assert len(chunks) == 2

    def test_custom_window_seconds_is_respected(self):
        # With a 5-second window, words at 0 s and 6 s must land in separate chunks
        seg = _seg(words=[
            _word("alpha", 0.0, 1.0),
            _word("beta", 6.0, 7.0),
        ])
        chunks = chunk_transcript({"segments": [seg]}, window_seconds=5)
        assert len(chunks) == 2

    def test_many_words_create_correct_number_of_chunks(self):
        # 6 words, 10 s apart each → 0,10,20,30,40,50 s endpoints
        # With a 35 s window: chunk 1 closes before word at 36 s end → [0..30], [40..50]
        # Actually word ends: 1,11,21,31,41,51 — check word_end - window_start > 35
        # word 0: end=1,  ws=0  → 1-0=1     ≤35 → stay
        # word 1: end=11, ws=0  → 11-0=11   ≤35 → stay
        # word 2: end=21, ws=0  → 21-0=21   ≤35 → stay
        # word 3: end=31, ws=0  → 31-0=31   ≤35 → stay
        # word 4: end=41, ws=0  → 41-0=41   >35 → new chunk (ws=40)
        # word 5: end=51, ws=40 → 51-40=11  ≤35 → stay
        # → 2 chunks
        words = [_word(f"w{i}", i * 10, i * 10 + 1) for i in range(6)]
        seg = _seg(words=words)
        chunks = chunk_transcript({"segments": [seg]})
        assert len(chunks) == 2


class TestChunkTimestamps:
    """start_time and end_time of each chunk are taken from the first / last word."""

    def test_single_chunk_timestamps(self):
        seg = _seg(words=[
            _word("A", 5.0, 6.0),
            _word("B", 10.0, 11.5),
        ])
        chunks = chunk_transcript({"segments": [seg]})
        assert len(chunks) == 1
        assert chunks[0]["start_time"] == pytest.approx(5.0)
        assert chunks[0]["end_time"] == pytest.approx(11.5)

    def test_multi_chunk_timestamps(self):
        seg = _seg(words=[
            _word("first", 0.0, 1.0),
            _word("second", 40.0, 41.5),
        ])
        chunks = chunk_transcript({"segments": [seg]}, window_seconds=35)
        assert len(chunks) == 2
        assert chunks[0]["start_time"] == pytest.approx(0.0)
        assert chunks[0]["end_time"] == pytest.approx(1.0)
        assert chunks[1]["start_time"] == pytest.approx(40.0)
        assert chunks[1]["end_time"] == pytest.approx(41.5)

    def test_chunk_text_joins_words_in_order(self):
        seg = _seg(words=[
            _word("foo", 0.0, 1.0),
            _word("bar", 2.0, 3.0),
            _word("baz", 4.0, 5.0),
        ])
        chunks = chunk_transcript({"segments": [seg]})
        assert chunks[0]["text"] == "foo bar baz"


class TestChunkSpeakerAssignment:
    """Dominant speaker (by duration) is attached to each chunk."""

    def test_single_speaker_chunk(self):
        seg = _seg(words=[
            _word("hello", 0.0, 1.0, speaker="SPEAKER_01"),
            _word("world", 2.0, 3.0, speaker="SPEAKER_01"),
        ])
        chunks = chunk_transcript({"segments": [seg]})
        assert chunks[0]["speaker"] == "SPEAKER_01"

    def test_dominant_speaker_wins_by_duration(self):
        # SPEAKER_01 speaks for 8 s total, SPEAKER_02 for 1 s → SPEAKER_01 dominates
        seg = _seg(words=[
            _word("long1", 0.0, 4.0, speaker="SPEAKER_01"),
            _word("long2", 4.0, 8.0, speaker="SPEAKER_01"),
            _word("short", 9.0, 10.0, speaker="SPEAKER_02"),
        ])
        chunks = chunk_transcript({"segments": [seg]})
        assert chunks[0]["speaker"] == "SPEAKER_01"

    def test_speaker_per_chunk_independently(self):
        # Two chunks, each dominated by a different speaker
        words = [
            _word("a", 0.0, 2.0, speaker="SPEAKER_00"),
            _word("b", 2.0, 4.0, speaker="SPEAKER_00"),
            # New chunk starts here (window_seconds=5, word_end 10 - 0 > 5)
            _word("c", 6.0, 9.0, speaker="SPEAKER_01"),
        ]
        seg = _seg(words=words)
        chunks = chunk_transcript({"segments": [seg]}, window_seconds=5)
        assert len(chunks) == 2
        assert chunks[0]["speaker"] == "SPEAKER_00"
        assert chunks[1]["speaker"] == "SPEAKER_01"


class TestChunkSegmentLevelFallback:
    """Segments with no word-level timestamps must not raise; they produce chunks."""

    def test_segment_only_timestamps_does_not_crash(self):
        # Segment has start/end but no 'words' list at all
        seg = _seg(start=0.0, end=10.0, text="Some spoken text without word alignment.")
        chunks = chunk_transcript({"segments": [seg]})
        # Must not raise — result is a single chunk built from the segment boundary
        assert len(chunks) == 1
        assert chunks[0]["start_time"] == pytest.approx(0.0)
        assert chunks[0]["end_time"] == pytest.approx(10.0)

    def test_segment_only_timestamps_with_explicit_speaker(self):
        seg = _seg(
            start=2.5, end=15.0,
            text="Hello from speaker two.",
            speaker="SPEAKER_02",
        )
        chunks = chunk_transcript({"segments": [seg]})
        assert chunks[0]["speaker"] == "SPEAKER_02"

    def test_empty_transcript_returns_empty_list(self):
        assert chunk_transcript({"segments": []}) == []

    def test_transcript_with_no_timestamps_at_all_returns_empty(self):
        # Segment has neither words nor start/end — nothing to chunk
        seg = {"text": "ghost segment"}
        chunks = chunk_transcript({"segments": [seg]})
        assert chunks == []

    def test_accepts_raw_list_of_segments(self):
        # chunk_transcript also accepts a plain list (not a dict wrapper)
        seg = _seg(words=[_word("hi", 0.0, 1.0)])
        chunks = chunk_transcript([seg])
        assert len(chunks) == 1
