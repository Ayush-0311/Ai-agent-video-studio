"""Startup fingerprint shared by the desktop launcher and the loaded backend."""
import hashlib
from pathlib import Path

API_VERSION = 15


def fingerprint():
    root = Path(__file__).resolve().parent
    digest = hashlib.sha256()
    # Hash source bytes, not mtimes. Capture once before importing app modules.
    for name in ('runtime_version.py', 'main.py', 'studio.py', 'explainer_research.py', 'script_timing.py', 'avatar_presenter.py', 'realistic_presenter.py', 'narration.py', 'narration_worker.py', 'speech_timing.py', 'production_agents.py', 'video_effects.py', 'edit_agent.py', 'runtime_tools.py', 'requirements.txt'):
        digest.update(name.encode())
        digest.update((root / name).read_bytes())
    return digest.hexdigest()


LOADED_FINGERPRINT = fingerprint()

if __name__ == '__main__':
    print(LOADED_FINGERPRINT)
