import whisperx
import logging

_GLOBAL_MODEL = None
_GLOBAL_MODEL_SIZE = None


def get_whisper_model(model_size: str = "base"):
    """
    Lazy loader for the WhisperX ASR model.

    WHY LAZY LOADING?
    Deferring model loading reduces peak memory pressure: the Celery worker
    imports this module on startup, but not every worker process will ever
    run a transcription task. Loading on first use spreads memory allocation
    over time instead of concentrating it all at worker startup.
    The loaded model is cached in the module-level variable so subsequent
    calls within the same worker process are instant.
    """
    global _GLOBAL_MODEL, _GLOBAL_MODEL_SIZE
    if _GLOBAL_MODEL is None or _GLOBAL_MODEL_SIZE != model_size:
        logging.info(f"Loading WhisperX model '{model_size}' into global cache...")
        # int8 uses 8-bit weights: less RAM and faster CPU inference
        _GLOBAL_MODEL = whisperx.load_model(model_size, device="cpu", compute_type="int8")
        _GLOBAL_MODEL_SIZE = model_size
    return _GLOBAL_MODEL


def transcribe_audio(audio_path, model_size="base"):
    """Transcribe audio using WhisperX, optimized for CPU."""
    whisper_model = get_whisper_model(model_size)

    # WhisperX wants a numpy waveform, not a file path.
    audio = whisperx.load_audio(audio_path)

    # Transcribe with a set batch_size for optimal CPU performance
    result = whisper_model.transcribe(audio, batch_size=4)

    lang_code = result.get("language", "en")

    # RESTORE FORCED ALIGNMENT WITH GRACEFUL DEGRADATION:
    # Downstream chunking (stages/chunking.py) works best with word-level timestamps.
    # However, alignment models download per-language on first use, which can hang
    # on slow connections or unsupported languages. We use a 60-second timeout so the 
    # pipeline degrades gracefully to segment-level chunking rather than freezing the whole worker.
    import concurrent.futures

    def do_alignment():
        try:
            am, md = whisperx.load_align_model(language_code=lang_code, device="cpu")
        except Exception as e:
            logging.warning(f"Failed to load align model for {lang_code}: {e}. Falling back to 'en'.")
            am, md = whisperx.load_align_model(language_code="en", device="cpu")
            
        return whisperx.align(
            result["segments"],
            am,
            md,
            audio,
            device="cpu",
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(do_alignment)
        try:
            aligned = future.result(timeout=60)
            return aligned
        except concurrent.futures.TimeoutError:
            logging.warning("Alignment unavailable for this language/timed out, falling back to segment-level timestamps")
            return result
        except Exception as e2:
            logging.warning(f"Alignment failed ({e2}), falling back to segment-level timestamps")
            return result
