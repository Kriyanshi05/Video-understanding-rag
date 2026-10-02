import os
from pathlib import Path
import yt_dlp

def download_from_url(url: str, output_dir: Path | str) -> tuple[str, str]:
    """
    Downloads a video from a given URL using yt-dlp's Python API.
    Returns a tuple of (downloaded_file_path, video_title).
    
    This provides an alternative ingest method to local file uploads.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    ydl_opts = {
        # Enforce best mp4 available, or just the best format if mp4 is unavailable
        'format': 'best[ext=mp4]/best',
        # Set output template to save inside the provided output_dir
        'outtmpl': str(output_dir / '%(id)s_%(title)s.%(ext)s'),
        # Keep logs relatively clean
        'quiet': True,
        'no_warnings': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Extract info and download synchronously
            info = ydl.extract_info(url, download=True)
            if not info:
                raise RuntimeError("No information could be extracted from the URL.")
            
            title = info.get('title', 'Unknown Title')
            
            # Retrieve the final file path determined by outtmpl
            file_path = ydl.prepare_filename(info)
            
            # Safety check: yt-dlp might change extensions (e.g. mkv fallback) 
            # if post-processing was involved, though less likely with 'best'.
            if not os.path.exists(file_path):
                base, _ = os.path.splitext(file_path)
                for ext in ['.mp4', '.mkv', '.webm', '.mov']:
                    if os.path.exists(base + ext):
                        file_path = base + ext
                        break

            return str(file_path), title

    except Exception as e:
        # Wrap yt-dlp errors in a clear RuntimeError for the caller
        raise RuntimeError(
            f"Failed to download video. It might be private, region-locked, "
            f"or the URL is invalid. Details: {str(e)}"
        )
