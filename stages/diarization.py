"""
Speaker Diarization Module (pyannote.audio + WhisperX Alignment Merge).

VIVA EXPLANATION & ARCHITECTURAL DESIGN:
1. WHAT IS SPEAKER DIARIZATION?
   Speaker diarization is the process of partitioning an audio stream into homogeneous
   temporal segments according to speaker identity ("who spoke when"). WhisperX handles
   Automatic Speech Recognition (ASR) and word-level forced alignment, but does not identify
   individual speakers by default. pyannote.audio provides neural speaker embeddings and
   clustering to detect speaker turns.

2. WHY LAZY LOADING?
   Neural diarization pipelines (such as pyannote/speaker-diarization-3.1) are memory-heavy
   and require downloading large model weights. Preloading them on worker boot degrades startup
   times and causes memory spikes on nodes that might only execute lighter Celery tasks.
   Using module-level caching with `get_diarization_pipeline()` loads the weights exactly once
   per process on demand.

3. GRACEFUL DEGRADATION CONTRACT (ZERO-CRASH DESIGN):
   pyannote requires both a Hugging Face user access token AND acceptance of gated model terms.
   In real-world deployments or academic evaluation:
   - The token might be absent or invalid.
   - The user might not have accepted gated model conditions on Hugging Face.
   - Network connectivity might drop.
   - Audio decoding libraries (e.g. torchcodec/FFmpeg) might fail on certain OS environments.
   Under ANY failure mode, `get_diarization_pipeline()` and `diarize_audio()` safely catch all
   exceptions, log actionable diagnostic warnings, and return an empty segment list `[]`.

4. TEMPORAL MERGE & SINGLE-SPEAKER FALLBACK:
   `merge_speaker_labels()` maps WhisperX words and segments to pyannote speaker turns:
   - For every WhisperX word timestamp `t`, we search for a diarization segment whose
     `[start_time, end_time]` interval covers `t`.
   - If `t` lands in a small boundary gap between diarization turns, we assign the nearest
     diarization turn.
   - If diarization was unavailable or produced 0 segments, every segment and word is
     labeled "SPEAKER_00". Downstream chunking, embedding, vector storage, and Gemini
     prompt-building ALWAYS receive a valid `speaker` field without None or missing keys.
"""

import logging
from typing import Any, Dict, List, Optional
from api.config import settings

# Module-level cache for lazy loading the pyannote pipeline
_GLOBAL_DIARIZATION_PIPELINE: Optional[Any] = None
_PIPELINE_LOAD_ATTEMPTED: bool = False


def get_diarization_pipeline() -> Optional[Any]:
    """
    Lazy loader for the pyannote speaker diarization pipeline.

    Returns:
        The loaded pyannote Pipeline instance, or None if unavailable/failed.
    """
    global _GLOBAL_DIARIZATION_PIPELINE, _PIPELINE_LOAD_ATTEMPTED

    if _PIPELINE_LOAD_ATTEMPTED:
        return _GLOBAL_DIARIZATION_PIPELINE

    _PIPELINE_LOAD_ATTEMPTED = True

    token = getattr(settings, "huggingface_token", None)
    if not token:
        logging.warning(
            "Speaker diarization disabled: HUGGINGFACE_TOKEN is missing or not set in settings/.env. "
            "Pipeline will degrade gracefully to single-speaker labeling ('SPEAKER_00')."
        )
        _GLOBAL_DIARIZATION_PIPELINE = None
        return None

    try:
        logging.info("Loading pyannote/speaker-diarization-3.1 pipeline from Hugging Face...")
        from pyannote.audio import Pipeline

        # Modern pyannote versions accept 'token', while older versions accept 'use_auth_token'.
        try:
            _GLOBAL_DIARIZATION_PIPELINE = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                token=token,
            )
        except TypeError:
            _GLOBAL_DIARIZATION_PIPELINE = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                use_auth_token=token,
            )

        if _GLOBAL_DIARIZATION_PIPELINE is not None:
            logging.info("pyannote speaker diarization pipeline loaded successfully.")
        else:
            logging.warning("pyannote Pipeline.from_pretrained returned None.")

    except Exception as exc:
        logging.warning(
            f"Failed to load pyannote speaker diarization pipeline ({exc}). "
            "Diarization is optional; continuing pipeline with single-speaker fallback ('SPEAKER_00'). "
            "NOTE: Ensure you have accepted user conditions on Hugging Face for "
            "'pyannote/speaker-diarization-3.1' and 'pyannote/segmentation-3.0'."
        )
        _GLOBAL_DIARIZATION_PIPELINE = None

    return _GLOBAL_DIARIZATION_PIPELINE


def diarize_audio(audio_path: str) -> List[Dict[str, Any]]:
    """
    Run speaker diarization on an extracted audio file.

    Args:
        audio_path: Path to the .wav or extracted audio file.

    Returns:
        A list of dicts with keys:
          - "speaker_label": Speaker identifier (e.g. "SPEAKER_00")
          - "speaker": Same speaker identifier for convenience
          - "start_time": Segment start time in seconds (float)
          - "end_time": Segment end time in seconds (float)
        Returns an empty list `[]` if the pipeline is unavailable or diarization fails.
    """
    pipeline = get_diarization_pipeline()
    if pipeline is None:
        logging.info("Diarization skipped (pipeline unavailable).")
        return []

    try:
        logging.info(f"Running speaker diarization on '{audio_path}'...")

        # Defensive execution:
        # Direct file path loading in pyannote may invoke torchcodec, which can fail
        # on environments without required FFmpeg shared DLLs. If direct call fails,
        # fallback to preloading waveform via torchaudio in memory.
        try:
            diarization_output = pipeline(str(audio_path))
        except Exception as direct_err:
            logging.warning(
                f"Direct audio file processing failed ({direct_err}). "
                "Attempting in-memory torchaudio waveform fallback..."
            )
            import torchaudio
            waveform, sample_rate = torchaudio.load(str(audio_path))
            diarization_output = pipeline({"waveform": waveform, "sample_rate": sample_rate})

        # pyannote outputs an Annotation object, or DiarizeOutput containing speaker_diarization
        annotation = diarization_output
        if hasattr(diarization_output, "speaker_diarization"):
            annotation = diarization_output.speaker_diarization
        elif hasattr(diarization_output, "exclusive_speaker_diarization"):
            annotation = diarization_output.exclusive_speaker_diarization

        segments: List[Dict[str, Any]] = []
        if hasattr(annotation, "itertracks"):
            for turn, _track, speaker_label in annotation.itertracks(yield_label=True):
                segments.append({
                    "speaker_label": str(speaker_label),
                    "speaker": str(speaker_label),
                    "start_time": float(turn.start),
                    "end_time": float(turn.end),
                })

        logging.info(f"Diarization complete: found {len(segments)} speaker turn(s).")
        return segments

    except Exception as exc:
        logging.warning(
            f"Diarization execution failed on '{audio_path}': {exc}. "
            "Gracefully degrading to single-speaker fallback."
        )
        return []


def _find_speaker_for_time(timestamp: float, diarization_segments: List[Dict[str, Any]]) -> str:
    """
    Find which diarization segment contains a given timestamp `timestamp`.

    Matching logic:
    1. Exact containment: start_time <= timestamp <= end_time
    2. Proximity fallback: If `timestamp` falls in a brief pause/silence between speaker turns,
       assign the closest turn by boundary distance.
    3. Empty fallback: Defaults to 'SPEAKER_00'.
    """
    if not diarization_segments:
        return "SPEAKER_00"

    # Step 1: Containment
    for seg in diarization_segments:
        if seg["start_time"] <= timestamp <= seg["end_time"]:
            return seg.get("speaker_label") or seg.get("speaker") or "SPEAKER_00"

    # Step 2: Proximity (nearest speaker turn)
    def turn_distance(seg: Dict[str, Any]) -> float:
        if timestamp < seg["start_time"]:
            return seg["start_time"] - timestamp
        elif timestamp > seg["end_time"]:
            return timestamp - seg["end_time"]
        return 0.0

    nearest = min(diarization_segments, key=turn_distance)
    return nearest.get("speaker_label") or nearest.get("speaker") or "SPEAKER_00"


def merge_speaker_labels(
    whisperx_segments: Any,
    diarization_segments: List[Dict[str, Any]],
) -> Any:
    """
    Merge pyannote speaker turn intervals into WhisperX segments and words.

    VIVA MERGE LOGIC:
    - If diarization_segments is empty (due to pipeline unavailability or failure),
      every word and segment is tagged with "SPEAKER_00" as a single-speaker fallback.
    - When diarization_segments are present, each WhisperX word's start_time is tested
      against the diarization intervals.
    - Each segment's overall speaker is computed as the majority speaker across its words
      (or timestamp containment if word-level alignment is absent).
    - Downstream stages (chunking, vector store, Gemini answer generation) will ALWAYS
      find a valid 'speaker' field.

    Args:
        whisperx_segments: Either a WhisperX transcript dict {"segments": [...]}
                           or a list of segment dicts.
        diarization_segments: Output list from diarize_audio().

    Returns:
        The updated transcript structure with 'speaker' and 'speaker_label' populated.
    """
    # Accommodate either the full transcript dict or the raw list of segments
    if isinstance(whisperx_segments, dict):
        segments_list = whisperx_segments.get("segments", [])
    else:
        segments_list = whisperx_segments

    if not segments_list:
        return whisperx_segments

    for segment in segments_list:
        segment_words = segment.get("words")
        seg_start = float(segment.get("start", 0.0))

        if segment_words:
            word_speakers: List[str] = []
            for word in segment_words:
                w_start = word.get("start")
                if w_start is not None:
                    spk = _find_speaker_for_time(float(w_start), diarization_segments)
                else:
                    spk = _find_speaker_for_time(seg_start, diarization_segments)
                word["speaker"] = spk
                word["speaker_label"] = spk
                word_speakers.append(spk)

            # Segment dominant speaker is the most common speaker among its words
            if word_speakers:
                dominant_seg_speaker = max(set(word_speakers), key=word_speakers.count)
            else:
                dominant_seg_speaker = _find_speaker_for_time(seg_start, diarization_segments)
        else:
            # Word-level alignment was skipped or failed; assign based on segment start time
            dominant_seg_speaker = _find_speaker_for_time(seg_start, diarization_segments)

        segment["speaker"] = dominant_seg_speaker
        segment["speaker_label"] = dominant_seg_speaker

    return whisperx_segments
