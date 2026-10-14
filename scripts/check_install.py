"""Check the installed desktop runtime without contacting Colab or downloading models."""
import importlib
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'backend'))


def main():
    for module in ('uvicorn', 'fastapi', 'multipart', 'faster_whisper', 'edge_tts',
                   'deep_translator', 'gtts', 'requests', 'studio'):
        importlib.import_module(module)
    from runtime_tools import _find_ffmpeg
    ffmpeg = Path(_find_ffmpeg())
    sibling = ffmpeg.with_name('ffprobe.exe')
    ffprobe = str(sibling) if sibling.is_file() else shutil.which('ffprobe')
    if not ffprobe:
        raise RuntimeError('FFprobe is missing. Install the complete FFmpeg package and add its bin folder to PATH.')
    for binary in (str(ffmpeg), ffprobe):
        subprocess.run([binary, '-version'], check=True, capture_output=True, timeout=10)
    for relative in ('node_modules/electron/dist/electron.exe', 'index.html',
                     'frontend/api/studio-integration.js', 'frontend/api/timeline-editor.js',
                     'desktop-downloads.js', 'desktop-unsaved.js', 'frontend/api/project-safety.js', 'colab/SmartEdit_Colab.ipynb'):
        if not (ROOT/relative).is_file():
            raise RuntimeError(f'Missing {relative}. Run SETUP again or restore the project files.')
    print('Desktop dependencies, FFmpeg, FFprobe and production files: OK')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(f'SETUP CHECK FAILED: {error}', file=sys.stderr)
        sys.exit(1)
