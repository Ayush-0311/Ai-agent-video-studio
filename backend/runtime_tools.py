"""Read-only executable discovery shared by desktop checks and the backend."""
import os
from pathlib import Path
import subprocess


def resolve_speech_model(download, model, cache) -> str:
    """Reuse a complete local Whisper snapshot, fetching it only when needed."""
    model_name = str(model)
    requested_path = Path(model_name).expanduser()
    is_custom_path = (requested_path.is_absolute() or requested_path.exists()
                      or '/' in model_name or '\\' in model_name)

    def complete(path: Path) -> bool:
        return path.is_dir() and all(
            (path / name).is_file() and (path / name).stat().st_size > 0
            for name in ('model.bin', 'config.json', 'tokenizer.json'))

    if is_custom_path:
        if not complete(requested_path):
            raise RuntimeError('Local Whisper directory is incomplete: expected model.bin, config.json and tokenizer.json.')
        return str(requested_path.resolve())

    cache_path = Path(cache).expanduser()
    cache_path.mkdir(parents=True, exist_ok=True)
    for local_only in (True, False):
        try:
            result = Path(download(model_name, cache_dir=str(cache_path),
                                   local_files_only=local_only)).expanduser()
        except Exception:
            if local_only:
                continue
            raise
        if complete(result):
            return str(result)
        if not local_only:
            raise RuntimeError(f'Whisper model download is incomplete for {model_name}.')
    raise RuntimeError(f'Whisper model download is incomplete for {model_name}.')


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
