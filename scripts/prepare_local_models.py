"""Download the selected local speech model during setup, without GPU allocation."""
import os
from pathlib import Path
import sys


def main():
    from faster_whisper.utils import download_model
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'backend'))
    from runtime_tools import resolve_speech_model
    model = os.getenv('SMARTEDIT_WHISPER_MODEL', 'base')
    cache = Path(__file__).resolve().parents[1]/'backend/models/hf-cache'
    cache.mkdir(parents=True, exist_ok=True)
    print('Preparing Whisper '+model+'. Complete cached models are reused offline; missing files download automatically.', flush=True)
    resolve_speech_model(download_model, model, cache)
    print('Local speech model ready: '+model)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('MODEL SETUP FAILED: '+str(exc), file=sys.stderr)
        sys.exit(1)
