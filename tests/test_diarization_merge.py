# tests/test_diarization_merge.py
# Verifies that merge_speaker_labels() in stages/diarization.py:
#   - assigns the correct speaker label when a word timestamp falls inside a
#     diarization segment
#   - uses proximity matching for timestamps that fall in gaps between segments
#   - labels every word and segment "SPEAKER_00" when the diarization list is empty
#   - handles both the dict-wrapped form {"segments": [...]} and a plain list
#   - never modifies the diarization_segments list itself

import pytest

# conftest.py sets GEMINI_API_KEY before this import so Settings() won't fail.
from stages.diarization import merge_speaker_labels


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _diar_seg(label, start, end):
    """Build a minimal diarization segment dict (output shape of diarize_audio)."""
    return {"speaker_label": label, "speaker": label, "start_time": start, "end_time": end}


def _wx_word(word, start, end):
    """Build a minimal WhisperX word dict without a speaker field."""
    return {"word": word, "start": start, "end": end}


def _wx_seg(words, start, end, text=""):
    """Build a minimal WhisperX segment dict."""
    return {"words": words, "start": start, "end": end, "text": text}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestMergeSpeakerLabelsCorrectAssignment:
    """Words are labelled with the speaker whose interval contains them."""

    def test_single_speaker_single_segment(self):
        words = [_wx_word("hello", 1.0, 2.0), _wx_word("world", 2.5, 3.0)]
        segments = [_wx_seg(words, 1.0, 3.0)]
        diar = [_diar_seg("SPEAKER_00", 0.0, 5.0)]

        result = merge_speaker_labels({"segments": segments}, diar)
        for word in result["segments"][0]["words"]:
            assert word["speaker"] == "SPEAKER_00"
        assert result["segments"][0]["speaker"] == "SPEAKER_00"

    def test_two_speakers_split_across_words(self):
        # SPEAKER_00 owns 0–4 s, SPEAKER_01 owns 4–10 s
        words = [
            _wx_word("first", 1.0, 2.0),   # inside SPEAKER_00 window
            _wx_word("second", 5.0, 6.0),  # inside SPEAKER_01 window
        ]
        segments = [_wx_seg(words, 1.0, 6.0)]
        diar = [
            _diar_seg("SPEAKER_00", 0.0, 4.0),
            _diar_seg("SPEAKER_01", 4.0, 10.0),
        ]

        result = merge_speaker_labels({"segments": segments}, diar)
        merged_words = result["segments"][0]["words"]
        assert merged_words[0]["speaker"] == "SPEAKER_00"
        assert merged_words[1]["speaker"] == "SPEAKER_01"

    def test_dominant_speaker_per_segment_is_majority(self):
        # Three words: two for SPEAKER_00, one for SPEAKER_01 → segment speaker = SPEAKER_00
        words = [
            _wx_word("a", 0.5, 1.0),   # SPEAKER_00
            _wx_word("b", 1.5, 2.0),   # SPEAKER_00
            _wx_word("c", 5.0, 5.5),   # SPEAKER_01
        ]
        segments = [_wx_seg(words, 0.5, 5.5)]
        diar = [
            _diar_seg("SPEAKER_00", 0.0, 4.0),
            _diar_seg("SPEAKER_01", 4.0, 8.0),
        ]

        result = merge_speaker_labels({"segments": segments}, diar)
        # Majority of words are SPEAKER_00 → segment-level speaker should be SPEAKER_00
        assert result["segments"][0]["speaker"] == "SPEAKER_00"

    def test_speaker_label_field_also_populated(self):
        words = [_wx_word("hi", 1.0, 2.0)]
        segments = [_wx_seg(words, 1.0, 2.0)]
        diar = [_diar_seg("SPEAKER_01", 0.0, 5.0)]

        result = merge_speaker_labels({"segments": segments}, diar)
        word = result["segments"][0]["words"][0]
        assert word.get("speaker_label") == "SPEAKER_01"
        assert result["segments"][0].get("speaker_label") == "SPEAKER_01"


class TestMergeProximityFallback:
    """Timestamps in gaps between diarization segments get the nearest speaker."""

    def test_gap_between_speakers_uses_nearest(self):
        # Gap between 3.0 and 5.0 — a word at 3.8 s is closer to SPEAKER_00 (ends 3.0)
        # than to SPEAKER_01 (starts 5.0): dist to 00 = 0.8, dist to 01 = 1.2
        words = [_wx_word("gap", 3.8, 4.0)]
        segments = [_wx_seg(words, 3.8, 4.0)]
        diar = [
            _diar_seg("SPEAKER_00", 0.0, 3.0),
            _diar_seg("SPEAKER_01", 5.0, 8.0),
        ]

        result = merge_speaker_labels({"segments": segments}, diar)
        assert result["segments"][0]["words"][0]["speaker"] == "SPEAKER_00"


class TestMergeEmptyDiarization:
    """When diarization_segments is empty every word / segment gets SPEAKER_00."""

    def test_all_words_get_speaker_00_with_empty_diar(self):
        words = [
            _wx_word("one", 0.0, 1.0),
            _wx_word("two", 2.0, 3.0),
            _wx_word("three", 4.0, 5.0),
        ]
        segments = [_wx_seg(words, 0.0, 5.0)]

        result = merge_speaker_labels({"segments": segments}, diarization_segments=[])
        for word in result["segments"][0]["words"]:
            assert word["speaker"] == "SPEAKER_00"
        assert result["segments"][0]["speaker"] == "SPEAKER_00"

    def test_multiple_segments_all_speaker_00_with_empty_diar(self):
        seg1 = _wx_seg([_wx_word("a", 0.0, 1.0)], 0.0, 1.0)
        seg2 = _wx_seg([_wx_word("b", 5.0, 6.0)], 5.0, 6.0)

        result = merge_speaker_labels({"segments": [seg1, seg2]}, diarization_segments=[])
        for seg in result["segments"]:
            assert seg["speaker"] == "SPEAKER_00"

    def test_no_word_timestamps_fallback_empty_diar(self):
        # Segment has no 'words' key at all — merge must not crash
        seg = {"start": 0.0, "end": 5.0, "text": "no words here"}
        result = merge_speaker_labels({"segments": [seg]}, diarization_segments=[])
        assert result["segments"][0]["speaker"] == "SPEAKER_00"


class TestMergeInputForms:
    """merge_speaker_labels accepts both a dict and a plain list of segments."""

    def test_dict_form_returned_as_dict(self):
        words = [_wx_word("hi", 0.0, 1.0)]
        seg = _wx_seg(words, 0.0, 1.0)
        diar = [_diar_seg("SPEAKER_00", 0.0, 5.0)]
        result = merge_speaker_labels({"segments": [seg]}, diar)
        assert isinstance(result, dict)
        assert "segments" in result

    def test_list_form_returned_as_list(self):
        words = [_wx_word("hi", 0.0, 1.0)]
        seg = _wx_seg(words, 0.0, 1.0)
        diar = [_diar_seg("SPEAKER_00", 0.0, 5.0)]
        result = merge_speaker_labels([seg], diar)
        assert isinstance(result, list)

    def test_empty_segment_list_returns_input_unchanged(self):
        inp = {"segments": []}
        result = merge_speaker_labels(inp, diarization_segments=[])
        assert result is inp  # returns the exact same object, unmodified
