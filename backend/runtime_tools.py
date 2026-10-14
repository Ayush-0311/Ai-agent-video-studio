"""Read-only executable discovery shared by desktop checks and the backend."""
import os
from pathlib import Path
import subprocess


def _find_ffmpeg() -> str:
    """Return the first working ffmpeg executable path."""
    candidates = [
        os.getenv("SMARTEDIT_FFMPEG_PATH", ""),
        str(Path(os.getenv("ProgramData", "C:/ProgramData")) / "chocolatey/lib/ffmpeg/tools/ffmpeg/bin/ffmpeg.exe"),
        "ffmpeg",  # system PATH
        str(Path.home() / "ffmpeg" / "ffmpeg-8.1.1-essentials_build" / "bin" / "ffmpeg.exe"),
        str(Path.home() / "ffmpeg" / "ffmpeg-9.0-full_build" / "bin" / "ffmpeg.exe"),
        r"C:\\ffmpeg\\bin\\ffmpeg.exe",
        r"C:\\Program Files\\ffmpeg\\bin\\ffmpeg.exe",
    ]
    for candidate in candidates:
        if not candidate:
            continue
        try:
            result = subprocess.run([candidate, "-version"], capture_output=True, timeout=5)
            if result.returncode == 0:
                return candidate
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            continue
    return "ffmpeg"  # last resort — will fail gracefully
