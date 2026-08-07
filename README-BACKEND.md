# SmartEdit AI Backend - Phase 1

This backend now implements the first real local pipeline capability: upload media, transcribe it with local `faster-whisper`, and poll job progress.

## Setup

From `smart-multimedia-editor/backend`:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
```

FFmpeg must be available on `PATH` because Whisper reads audio/video through media decoders.

## Run

```powershell
.\.venv\Scripts\python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/docs` for FastAPI's interactive docs.

## Configuration

Optional environment variables:

```powershell
$env:SMARTEDIT_WHISPER_MODEL = "tiny.en"      # default; try "base.en" or "small.en" later
$env:SMARTEDIT_WHISPER_DEVICE = "cpu"         # use "cuda" only after CUDA is configured
$env:SMARTEDIT_WHISPER_COMPUTE_TYPE = "int8"  # good CPU default
```

The first transcription downloads the selected model into the Hugging Face cache at `backend/models/hf-cache/`.

## Test With Curl

Upload an audio or video file:

```powershell
curl.exe -X POST "http://127.0.0.1:8000/api/v1/generate-video" -F "file=@C:\path\to\sample.mp3"
```

Example response:

```json
{
  "job_id": "job_abc123",
  "status": "queued",
  "progress": 0,
  "message": "Upload saved; poll /api/v1/job-status/{job_id} for progress."
}
```

Poll until `status` is `completed` or `failed`:

```powershell
curl.exe "http://127.0.0.1:8000/api/v1/job-status/job_abc123"
```

A completed job includes:

- `result.transcript`
- `result.segments[]` with start/end timestamps
- `result.segments[].words[]` with word-level timestamps
- detected `language`, media `duration`, and model name

## Current Scope

Phase 1 intentionally skips Celery, Redis, image generation, TTS, lip sync, and FFmpeg composition. The only real agent in this phase is Speech-to-Text; the rest remain future phases.
