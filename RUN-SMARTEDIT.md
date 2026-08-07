# SmartEdit AI - Local Run Guide

Use these files from this folder:

1. Double-click `Setup SmartEdit.bat` once.
2. Double-click `Launch SmartEdit.bat` whenever you want to use the app.
3. Drop a real video/audio file in the app.
4. The app uploads it to the local FastAPI backend and shows the real Whisper transcript when done.

`Launch SmartEdit.bat` starts:

- FastAPI backend at `http://127.0.0.1:8000`
- Electron frontend with `npm start`

To start only the backend for debugging, double-click `Start SmartEdit Backend.bat`. To stop only the backend, double-click `Stop SmartEdit Backend.bat`.

## Requirements

- Windows
- Python available as `python`
- Node.js/npm available as `npm`
- FFmpeg available on PATH

## Current Real Features

- Phase 1: local upload + faster-whisper speech-to-text
- Phase 2: Electron UI connected to backend upload + polling + real transcript display

Not implemented yet:

- Phase 3: Coqui TTS voice generation
- Phase 4: FFmpeg compositor/export
- Remaining agents: image generation, lip sync, avatar, translation, etc.

