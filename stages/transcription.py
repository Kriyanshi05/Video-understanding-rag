import whisperx


def transcribe_audio(audio_path, model_size="base"):
    """Transcribe audio and attach word-level timestamps via WhisperX alignment."""
    # int8 uses 8-bit weights: less RAM and faster CPU inference, with a small accuracy cost.
    model = whisperx.load_model(model_size, device="cpu", compute_type="int8")

    # WhisperX wants a numpy waveform, not a file path.
    audio = whisperx.load_audio(audio_path)
    result = model.transcribe(audio)

    # Forced alignment: take Whisper's transcript as given, then find when each word
    # actually occurs in the audio (start/end times) using a phoneme/wav2vec model.
    # It does not re-guess the words; it only timestamps the existing text.
    align_model, metadata = whisperx.load_align_model(
        language_code=result["language"],
        device="cpu",
    )
    aligned = whisperx.align(
        result["segments"],
        align_model,
        metadata,
        audio,
        device="cpu",
    )
    return aligned
