import subprocess
from pathlib import Path


def extract_audio(video_path, output_dir):
    """Extract 16 kHz mono WAV audio from a video file using FFmpeg."""
    video_path = Path(video_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Same stem as the video, but with a .wav extension.
    output_path = output_dir / f"{video_path.stem}.wav"

    command = [
        "ffmpeg",
        "-y",  # overwrite the output file if it already exists (non-interactive)
        "-i", str(video_path),  # input video path
        "-vn",  # drop the video stream; we only want audio
        "-ac", "1",  # mix down to 1 channel (mono), which Whisper expects
        "-ar", "16000",  # resample to 16 kHz (Whisper's native sample rate)
        str(output_path),
    ]

    completed = subprocess.run(command, capture_output=True, text=True)
    if completed.returncode != 0:
        raise RuntimeError(f"FFmpeg failed to extract audio:\n{completed.stderr}")

    return str(output_path)
