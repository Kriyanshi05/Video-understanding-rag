import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import logging
logging.basicConfig(level=logging.INFO)

from api.config import settings
from stages.diarization import (
    get_diarization_pipeline,
    diarize_audio,
    merge_speaker_labels,
    _find_speaker_for_time,
)
from stages.chunking import chunk_transcript, _chunk_from_words

print("--- Test 1: Config settings ---")
print("settings.huggingface_token exists:", hasattr(settings, "huggingface_token"))
print("settings.huggingface_token value:", settings.huggingface_token[:8] + "..." if settings.huggingface_token else None)
assert hasattr(settings, "huggingface_token"), "Settings missing huggingface_token"

print("\n--- Test 2: get_diarization_pipeline & diarize_audio Graceful Degradation ---")
# Call get_diarization_pipeline; even if gated terms not accepted, it must NOT raise an exception
pipeline = get_diarization_pipeline()
print("Pipeline result (None is expected if gated model terms not accepted):", pipeline)

# diarize_audio must return [] if pipeline is None or if dummy audio path
segs = diarize_audio("non_existent_file.wav")
assert isinstance(segs, list) and len(segs) == 0, f"Expected [], got {segs}"
print("diarize_audio returned empty list safely without crashing.")

print("\n--- Test 3: merge_speaker_labels ---")
# 3a: Empty diarization segments (fallback to SPEAKER_00)
sample_transcript = {
    "segments": [
        {
            "start": 0.0,
            "end": 4.0,
            "text": "Hello world this is test",
            "words": [
                {"word": "Hello", "start": 0.0, "end": 1.0},
                {"word": "world", "start": 1.1, "end": 2.0},
                {"word": "this", "start": 2.1, "end": 2.5},
                {"word": "is", "start": 2.6, "end": 3.0},
                {"word": "test", "start": 3.1, "end": 4.0},
            ]
        }
    ]
}

res_fallback = merge_speaker_labels(sample_transcript, [])
assert res_fallback["segments"][0]["speaker"] == "SPEAKER_00"
for w in res_fallback["segments"][0]["words"]:
    assert w["speaker"] == "SPEAKER_00", f"Word missing SPEAKER_00: {w}"
print("Fallback to SPEAKER_00 succeeded for all segments and words.")

# 3b: Multi-speaker diarization segments
mock_diarization = [
    {"speaker_label": "SPEAKER_00", "speaker": "SPEAKER_00", "start_time": 0.0, "end_time": 2.0},
    {"speaker_label": "SPEAKER_01", "speaker": "SPEAKER_01", "start_time": 2.05, "end_time": 6.0},
]

sample_transcript_multi = {
    "segments": [
        {
            "start": 0.0,
            "end": 5.0,
            "text": "Hello world from two speakers",
            "words": [
                {"word": "Hello", "start": 0.2, "end": 0.8},
                {"word": "world", "start": 1.0, "end": 1.5},
                {"word": "from", "start": 2.2, "end": 2.6},
                {"word": "two", "start": 2.8, "end": 3.2},
                {"word": "speakers", "start": 3.5, "end": 4.2},
            ]
        }
    ]
}

res_multi = merge_speaker_labels(sample_transcript_multi, mock_diarization)
words = res_multi["segments"][0]["words"]
assert words[0]["speaker"] == "SPEAKER_00", f"Expected SPEAKER_00 for 'Hello', got {words[0]['speaker']}"
assert words[1]["speaker"] == "SPEAKER_00", f"Expected SPEAKER_00 for 'world', got {words[1]['speaker']}"
assert words[2]["speaker"] == "SPEAKER_01", f"Expected SPEAKER_01 for 'from', got {words[2]['speaker']}"
assert words[3]["speaker"] == "SPEAKER_01", f"Expected SPEAKER_01 for 'two', got {words[3]['speaker']}"
assert words[4]["speaker"] == "SPEAKER_01", f"Expected SPEAKER_01 for 'speakers', got {words[4]['speaker']}"
# Dominant speaker in this segment has 3 words from SPEAKER_01 vs 2 words from SPEAKER_00
assert res_multi["segments"][0]["speaker"] == "SPEAKER_01"
print("Multi-speaker word and segment alignment succeeded.")

# 3c: Segment without word-level timestamps (fallback)
sample_no_words = {
    "segments": [
        {"start": 3.0, "end": 5.0, "text": "Segment without words"}
    ]
}
res_no_words = merge_speaker_labels(sample_no_words, mock_diarization)
assert res_no_words["segments"][0]["speaker"] == "SPEAKER_01"
print("Segment without word timestamps correctly matched by start_time.")

print("\n--- Test 4: chunk_transcript dominant speaker calculation ---")
chunks = chunk_transcript(res_multi, window_seconds=10)
assert len(chunks) == 1
assert "speaker" in chunks[0], "Chunk missing speaker field!"
# In the chunk:
# SPEAKER_00: (0.8-0.2) + (1.5-1.0) = 0.6 + 0.5 = 1.1s
# SPEAKER_01: (2.6-2.2) + (3.2-2.8) + (4.2-3.5) = 0.4 + 0.4 + 0.7 = 1.5s
# SPEAKER_01 has 1.5s duration vs 1.1s duration, so dominant speaker should be SPEAKER_01
assert chunks[0]["speaker"] == "SPEAKER_01", f"Expected SPEAKER_01 as dominant speaker, got {chunks[0]['speaker']}"
print(f"Chunk dominant speaker correctly calculated: {chunks[0]['speaker']}")

print("\nALL DIARIZATION AND CHUNKING UNIT TESTS PASSED!")
