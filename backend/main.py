from __future__ import annotations

import base64
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import requests

# ── Optional heavy deps — graceful fallback if not installed ──────────────────
try:
    from faster_whisper import WhisperModel
    from faster_whisper.utils import download_model
except ImportError as _fwe:
    WhisperModel = None  # type: ignore[assignment]
    download_model = None  # type: ignore[assignment]
    FASTER_WHISPER_IMPORT_ERROR: Exception | None = _fwe
else:
    FASTER_WHISPER_IMPORT_ERROR = None

try:
    from gtts import gTTS
    GTTS_AVAILABLE = True
except ImportError:
    GTTS_AVAILABLE = False

try:
    from deep_translator import GoogleTranslator
    DEEP_TRANSLATOR_AVAILABLE = True
except ImportError:
    DEEP_TRANSLATOR_AVAILABLE = False

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
MODEL_DIR = BASE_DIR / "models"
MODEL_CACHE_DIR = MODEL_DIR / "hf-cache"
AUDIO_OUT_DIR = BASE_DIR / "uploads" / "audio"
UPLOAD_DIR.mkdir(exist_ok=True)
MODEL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
AUDIO_OUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Env config ────────────────────────────────────────────────────────────────
WHISPER_MODEL = os.getenv("SMARTEDIT_WHISPER_MODEL", "tiny.en")
WHISPER_DEVICE = os.getenv("SMARTEDIT_WHISPER_DEVICE", "cpu")
WHISPER_COMPUTE_TYPE = os.getenv("SMARTEDIT_WHISPER_COMPUTE_TYPE", "int8")
OLLAMA_BASE_URL = os.getenv("SMARTEDIT_OLLAMA_BASE_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.getenv("SMARTEDIT_OLLAMA_MODEL", "llama3:latest")
FFMPEG_PATH = os.getenv("SMARTEDIT_FFMPEG_PATH", "ffmpeg")

# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="SmartEdit AI — 16-Agent Local Pipeline API",
    description="Full 16-agent autonomous video production pipeline.",
    version="3.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── In-memory job store ───────────────────────────────────────────────────────
jobs: dict[str, dict[str, Any]] = {}
jobs_lock = threading.Lock()
model_lock = threading.Lock()
_whisper_model: WhisperModel | None = None  # type: ignore[type-arg]
_loaded_model_path: str | None = None


# ─────────────────────────────────────────────────────────────────────────────
# Pydantic request models
# ─────────────────────────────────────────────────────────────────────────────

class ScriptGenerationRequest(BaseModel):
    prompt: str = Field(..., min_length=5)
    duration_seconds: int = Field(30, ge=5, le=600)
    language: str = Field("en", min_length=2, max_length=12)
    aspect_ratio: str = Field("16:9", min_length=3, max_length=8)


class LayoutPlanRequest(BaseModel):
    scenes: list[dict[str, Any]]
    style: str = Field("cinematic", description="auto | cinematic | minimal | podcast")


class SlideGenerationRequest(BaseModel):
    scene_text: str = Field(..., min_length=3)
    scene_id: int = Field(1)
    visual_prompt: str = Field("")


class ImagePromptRequest(BaseModel):
    text: str = Field(..., min_length=3)
    style: str = Field("cinematic photorealistic")
    aspect_ratio: str = Field("16:9")


class AvatarPromptRequest(BaseModel):
    style: str = Field("professional presenter, studio lighting")
    gender: str = Field("neutral")
    background: str = Field("dark studio")


class VoiceSynthesisRequest(BaseModel):
    text: str = Field(..., min_length=1)
    language: str = Field("en")
    slow: bool = Field(False)


class LipSyncRequest(BaseModel):
    text: str = Field(..., min_length=1)
    duration: float = Field(5.0)
    fps: int = Field(30)


class TranslationRequest(BaseModel):
    text: str = Field(..., min_length=1)
    source_language: str = Field("en")
    target_language: str = Field("hi")
    scenes: list[dict[str, Any]] = Field(default_factory=list)


class BrandKitRequest(BaseModel):
    logo_text: str = Field("SmartEdit AI")
    primary_color: str = Field("#8B5CF6")
    secondary_color: str = Field("#06B6D4")
    font: str = Field("Inter")
    watermark: bool = Field(True)
    scenes: list[dict[str, Any]] = Field(default_factory=list)


class ConversationSplitRequest(BaseModel):
    scenes: list[dict[str, Any]]
    speaker_a_name: str = Field("Host")
    speaker_b_name: str = Field("Guest")


class NLEditRequest(BaseModel):
    command: str = Field(..., min_length=3)
    scenes: list[dict[str, Any]] = Field(default_factory=list)
    current_scene_id: int = Field(0)


class MusicSelectionRequest(BaseModel):
    mood: str = Field("neutral", description="energetic | calm | dramatic | neutral | upbeat")
    duration_seconds: float = Field(30.0)
    duck_on_speech: bool = Field(True)


class ExportRequest(BaseModel):
    aspect_ratio: str = Field("16:9")
    resolution: str = Field("1080p")
    fps: int = Field(30)
    codec: str = Field("h264")
    include_subtitles: bool = Field(True)
    job_id: str = Field("")


class CompositeRequest(BaseModel):
    job_id: str = Field("")
    scenes: list[dict[str, Any]] = Field(default_factory=list)
    include_captions: bool = Field(True)
    include_music: bool = Field(True)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def update_job(job_id: str, **fields: Any) -> None:
    with jobs_lock:
        if job_id in jobs:
            jobs[job_id].update(fields)
            jobs[job_id]["updated_at"] = utc_now()


def snapshot_job(job_id: str) -> dict[str, Any] | None:
    with jobs_lock:
        job = jobs.get(job_id)
        return dict(job) if job else None


def resolve_model_path() -> str:
    model_path = Path(WHISPER_MODEL)
    if model_path.exists():
        return str(model_path)
    if download_model is None:
        details = f": {FASTER_WHISPER_IMPORT_ERROR}" if FASTER_WHISPER_IMPORT_ERROR else ""
        raise RuntimeError(f"faster-whisper is not installed correctly{details}")
    return download_model(WHISPER_MODEL, cache_dir=str(MODEL_CACHE_DIR), local_files_only=False)


def get_whisper_model():
    global _whisper_model, _loaded_model_path
    if WhisperModel is None:
        details = f": {FASTER_WHISPER_IMPORT_ERROR}" if FASTER_WHISPER_IMPORT_ERROR else ""
        raise RuntimeError(f"faster-whisper is not installed correctly{details}")
    with model_lock:
        if _whisper_model is None:
            model_path = resolve_model_path()
            _loaded_model_path = model_path
            _whisper_model = WhisperModel(model_path, device=WHISPER_DEVICE, compute_type=WHISPER_COMPUTE_TYPE)
        return _whisper_model


def extract_json_object(raw_text: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw_text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", raw_text, re.DOTALL)
    if not match:
        raise ValueError("Ollama did not return a JSON object.")
    parsed = json.loads(match.group(0))
    if not isinstance(parsed, dict):
        raise ValueError("Ollama response JSON is not an object.")
    return parsed


def call_ollama(prompt: str, temperature: float = 0.5) -> str:
    """Call Ollama and return raw response string."""
    try:
        response = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False, "options": {"temperature": temperature}},
            timeout=600,
        )
        response.raise_for_status()
        return response.json().get("response", "")
    except requests.RequestException as exc:
        raise RuntimeError(f"Could not reach Ollama at {OLLAMA_BASE_URL}: {exc}") from exc


def call_ollama_json(prompt: str, temperature: float = 0.4) -> dict[str, Any]:
    """Call Ollama and parse JSON response."""
    try:
        response = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False, "format": "json", "options": {"temperature": temperature}},
            timeout=600,
        )
        response.raise_for_status()
        raw = response.json().get("response", "")
        return extract_json_object(raw)
    except requests.RequestException as exc:
        raise RuntimeError(f"Could not reach Ollama at {OLLAMA_BASE_URL}: {exc}") from exc


def ffmpeg_available() -> bool:
    try:
        subprocess.run([FFMPEG_PATH, "-version"], capture_output=True, timeout=5)
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Agent 9 — Caption Agent (Whisper STT) — background worker
# ─────────────────────────────────────────────────────────────────────────────

def transcribe_upload(job_id: str, media_path: str) -> None:
    update_job(job_id, status="processing", progress=15, message="Caption Agent: Loading Whisper model")
    try:
        model = get_whisper_model()
        update_job(job_id, progress=35, message="Caption Agent: Transcribing audio")
        segments_iter, info = model.transcribe(media_path, beam_size=5, vad_filter=True, word_timestamps=True)
        segments: list[dict[str, Any]] = []
        full_text: list[str] = []
        for index, segment in enumerate(segments_iter, start=1):
            words = [
                {
                    "word": word.word,
                    "start": round(float(word.start), 3) if word.start is not None else None,
                    "end": round(float(word.end), 3) if word.end is not None else None,
                    "probability": round(float(word.probability), 4) if word.probability is not None else None,
                }
                for word in (segment.words or [])
            ]
            text = segment.text.strip()
            if text:
                full_text.append(text)
            segments.append({
                "id": index,
                "start": round(float(segment.start), 3),
                "end": round(float(segment.end), 3),
                "text": text,
                "words": words,
            })
            update_job(job_id, progress=min(90, 35 + index * 5), message=f"Caption Agent: Transcribed {index} segment(s)")

        result = {
            "language": info.language,
            "language_probability": round(float(info.language_probability), 4),
            "duration": round(float(info.duration), 3),
            "transcript": " ".join(full_text).strip(),
            "segments": segments,
            "model": WHISPER_MODEL,
            "model_path": _loaded_model_path,
        }
        update_job(job_id, status="completed", progress=100, message="Caption Agent: Transcription complete", result=result)
    except Exception as exc:
        update_job(job_id, status="failed", progress=100, message="Caption Agent: Transcription failed", error=str(exc))


# ─────────────────────────────────────────────────────────────────────────────
# Agent 2 — Script Agent helpers
# ─────────────────────────────────────────────────────────────────────────────

def normalize_script_result(data: dict[str, Any], request: ScriptGenerationRequest) -> dict[str, Any]:
    scenes = data.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        raise ValueError("Script Agent response did not include scenes.")
    normalized_scenes: list[dict[str, Any]] = []
    segment_length = request.duration_seconds / max(len(scenes), 1)
    for index, scene in enumerate(scenes, start=1):
        if not isinstance(scene, dict):
            continue
        start = scene.get("start")
        end = scene.get("end")
        if not isinstance(start, (int, float)):
            start = round((index - 1) * segment_length, 3)
        if not isinstance(end, (int, float)) or end <= start:
            end = round(index * segment_length, 3)
        text = str(scene.get("text") or scene.get("narration") or "").strip()
        if not text:
            continue
        normalized_scenes.append({
            "id": index,
            "start": round(float(start), 3),
            "end": round(float(end), 3),
            "text": text,
            "visual_prompt": str(scene.get("visual_prompt") or scene.get("visual") or "").strip(),
            "layout": str(scene.get("layout") or "full-presenter").strip(),
            "notes": str(scene.get("notes") or "").strip(),
        })
    if not normalized_scenes:
        raise ValueError("Script Agent returned scenes without narration text.")
    return {
        "title": str(data.get("title") or "SmartEdit AI Script").strip(),
        "prompt": request.prompt,
        "language": request.language,
        "duration_seconds": request.duration_seconds,
        "aspect_ratio": request.aspect_ratio,
        "model": OLLAMA_MODEL,
        "scenes": normalized_scenes,
        "transcript": " ".join(scene["text"] for scene in normalized_scenes),
    }


def generate_script_with_ollama(request: ScriptGenerationRequest) -> dict[str, Any]:
    scene_count = max(2, min(8, round(request.duration_seconds / 12)))
    prompt = f"""You are the SmartEdit AI Script Agent. Create a video narration script.
Return ONLY valid JSON. No markdown. No commentary.

JSON shape:
{{
  "title": "short title",
  "scenes": [
    {{
      "id": 1,
      "start": 0,
      "end": 6,
      "text": "spoken narration",
      "visual_prompt": "specific visual direction",
      "layout": "full-presenter | split-screen | pip-overlay | slide-deck",
      "notes": "editing note"
    }}
  ]
}}

Rules:
- Language: {request.language}
- Target duration: {request.duration_seconds} seconds
- Aspect ratio: {request.aspect_ratio}
- Create exactly {scene_count} scenes.
- Keep narration natural and ready for text-to-speech.
- Timings must cover 0 to {request.duration_seconds}.

User prompt: {request.prompt}""".strip()

    data = call_ollama_json(prompt, temperature=0.45)
    return normalize_script_result(data, request)


# ─────────────────────────────────────────────────────────────────────────────
# API Routes
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/")
def read_root() -> dict[str, Any]:
    return {
        "status": "online",
        "app": "SmartEdit AI",
        "version": "3.0.0",
        "agents": 16,
        "stt_engine": "faster-whisper",
        "model": WHISPER_MODEL,
        "script_engine": "Ollama",
        "script_model": OLLAMA_MODEL,
        "ffmpeg": ffmpeg_available(),
        "gtts": GTTS_AVAILABLE,
        "deep_translator": DEEP_TRANSLATOR_AVAILABLE,
    }


# ── Agent 9: Caption / Upload → STT ──────────────────────────────────────────

@app.post("/api/v1/generate-video")
async def generate_video(background_tasks: BackgroundTasks, file: UploadFile = File(...)) -> JSONResponse:
    """Upload media → Caption Agent (Whisper STT) processes it asynchronously."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="Upload must include a filename.")
    job_id = f"job_{uuid.uuid4().hex}"
    safe_name = Path(file.filename).name
    upload_path = UPLOAD_DIR / f"{job_id}_{safe_name}"
    try:
        with upload_path.open("wb") as output:
            shutil.copyfileobj(file.file, output)
    finally:
        await file.close()
    with jobs_lock:
        jobs[job_id] = {
            "job_id": job_id, "status": "queued", "progress": 0,
            "message": "Caption Agent: Upload saved; Whisper transcription queued",
            "filename": safe_name, "upload_path": str(upload_path),
            "created_at": utc_now(), "updated_at": utc_now(),
            "result": None, "error": None,
            "agent": "Caption Agent (Whisper)"
        }
    background_tasks.add_task(transcribe_upload, job_id, str(upload_path))
    return JSONResponse(status_code=202, content={
        "job_id": job_id, "status": "queued", "progress": 0,
        "message": "Caption Agent activated. Poll /api/v1/job-status/{job_id} for progress.",
        "agent": "Caption Agent (Whisper)"
    })


@app.get("/api/v1/job-status/{job_id}")
def job_status(job_id: str) -> dict[str, Any]:
    job = snapshot_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


# ── Agent 2: Script Agent ─────────────────────────────────────────────────────

@app.post("/api/v1/generate-script")
def generate_script(request: ScriptGenerationRequest) -> dict[str, Any]:
    """Script Agent: Ollama generates scene-by-scene narration script."""
    try:
        script = generate_script_with_ollama(request)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"status": "completed", "agent": "Script Agent", "model": OLLAMA_MODEL, "result": script}


# ── Agent 3: Layout Planner Agent ─────────────────────────────────────────────

@app.post("/api/v1/layout-plan")
def layout_plan(request: LayoutPlanRequest) -> dict[str, Any]:
    """Layout Planner Agent: Assigns optimal visual layout to each scene."""
    if not request.scenes:
        raise HTTPException(status_code=400, detail="No scenes provided.")

    scenes_summary = "\n".join(
        f"Scene {s.get('id', i+1)}: \"{s.get('text', '')[:120]}\"" 
        for i, s in enumerate(request.scenes[:8])
    )
    prompt = f"""You are the SmartEdit AI Layout Planner Agent.
For each scene below, decide the best video layout.

Layouts available:
- full-presenter: Solo talking head, full screen
- split-screen: Presenter left, visual/slide right
- pip-overlay: Presenter small corner, visual fills screen
- slide-deck: Full screen slide, no presenter
- dual-conversation: Two presenters side by side (podcast)

Style preference: {request.style}

Scenes:
{scenes_summary}

Return ONLY valid JSON:
{{
  "layouts": [
    {{"id": 1, "layout": "full-presenter", "reason": "opening hook"}}
  ]
}}"""

    try:
        data = call_ollama_json(prompt, temperature=0.3)
        layouts = data.get("layouts", [])
        
        # Apply layouts back to scenes
        layout_map = {item["id"]: item for item in layouts if isinstance(item, dict)}
        updated_scenes = []
        for i, scene in enumerate(request.scenes):
            scene_id = scene.get("id", i + 1)
            layout_info = layout_map.get(scene_id, {})
            updated = dict(scene)
            updated["layout"] = layout_info.get("layout", "full-presenter")
            updated["layout_reason"] = layout_info.get("reason", "default")
            updated_scenes.append(updated)

        return {
            "status": "completed",
            "agent": "Layout Planner Agent",
            "model": OLLAMA_MODEL,
            "scenes": updated_scenes,
            "layout_summary": {
                item["layout"]: sum(1 for s in updated_scenes if s.get("layout") == item["layout"])
                for item in layouts
            }
        }
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Layout Planner Agent failed: {exc}") from exc


# ── Agent 4: Slide Generator Agent ────────────────────────────────────────────

@app.post("/api/v1/generate-slides")
def generate_slides(request: SlideGenerationRequest) -> dict[str, Any]:
    """Slide Generator Agent: Creates structured slide content for a scene."""
    prompt = f"""You are the SmartEdit AI Slide Generator Agent.
Create a visual slide layout for this scene narration.

Scene text: "{request.scene_text}"
Visual direction: "{request.visual_prompt}"

Return ONLY valid JSON:
{{
  "title": "Bold slide headline (max 8 words)",
  "subtitle": "Supporting subtitle (max 12 words)",
  "bullets": ["Key point 1", "Key point 2", "Key point 3"],
  "background_style": "dark-gradient | light-minimal | tech-blue | purple-glow",
  "highlight_word": "most important word from the narration",
  "icon_suggestion": "emoji or icon concept"
}}"""

    try:
        data = call_ollama_json(prompt, temperature=0.6)
        return {
            "status": "completed",
            "agent": "Slide Generator Agent",
            "scene_id": request.scene_id,
            "slide": {
                "title": data.get("title", "AI Generated Slide"),
                "subtitle": data.get("subtitle", ""),
                "bullets": data.get("bullets", []),
                "background_style": data.get("background_style", "dark-gradient"),
                "highlight_word": data.get("highlight_word", ""),
                "icon_suggestion": data.get("icon_suggestion", "🤖"),
            }
        }
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Slide Generator Agent failed: {exc}") from exc


# ── Agent 5: Image Generator Agent ────────────────────────────────────────────

@app.post("/api/v1/generate-image-prompt")
def generate_image_prompt(request: ImagePromptRequest) -> dict[str, Any]:
    """Image Generator Agent: Creates optimized Stable Diffusion prompts for scene visuals."""
    prompt = f"""You are the SmartEdit AI Image Generator Agent.
Create an optimized image generation prompt for this scene.

Scene narration: "{request.text}"
Style: {request.style}
Aspect ratio: {request.aspect_ratio}

Return ONLY valid JSON:
{{
  "positive_prompt": "detailed SD/DALL-E prompt, comma-separated tags, cinematic quality",
  "negative_prompt": "blurry, low quality, watermark, text, ugly",
  "style_preset": "cinematic | anime | photorealistic | illustration | abstract",
  "color_palette": ["#hex1", "#hex2", "#hex3"],
  "mood": "dramatic | calm | energetic | mysterious | uplifting",
  "composition": "close-up | wide-angle | aerial | portrait | landscape"
}}"""

    try:
        data = call_ollama_json(prompt, temperature=0.7)
        return {
            "status": "completed",
            "agent": "Image Generator Agent",
            "result": {
                "positive_prompt": data.get("positive_prompt", f"{request.style} {request.text[:50]}"),
                "negative_prompt": data.get("negative_prompt", "blurry, low quality, watermark"),
                "style_preset": data.get("style_preset", "cinematic"),
                "color_palette": data.get("color_palette", ["#8B5CF6", "#06B6D4", "#1a1a2e"]),
                "mood": data.get("mood", "dramatic"),
                "composition": data.get("composition", "wide-angle"),
                "note": "Prompt ready for Stable Diffusion XL or DALL-E 3"
            }
        }
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Image Generator Agent failed: {exc}") from exc


# ── Agent 6: Avatar Generator Agent ───────────────────────────────────────────

@app.post("/api/v1/generate-avatar-prompt")
def generate_avatar_prompt(request: AvatarPromptRequest) -> dict[str, Any]:
    """Avatar Generator Agent: Creates SD portrait prompts for AI presenter avatars."""
    prompt = f"""You are the SmartEdit AI Avatar Generator Agent.
Create a Stable Diffusion portrait prompt for an AI video presenter.

Style preference: {request.style}
Gender presentation: {request.gender}
Background: {request.background}

Return ONLY valid JSON:
{{
  "portrait_prompt": "highly detailed SD portrait prompt for the avatar",
  "negative_prompt": "cartoon, blurry, low quality, bad anatomy, deformed",
  "lighting": "studio lighting description",
  "camera_angle": "front-facing portrait | slight angle | close-up",
  "clothing_style": "professional attire description",
  "background_desc": "background environment description",
  "post_processing": "color grading suggestion"
}}"""

    try:
        data = call_ollama_json(prompt, temperature=0.6)
        return {
            "status": "completed",
            "agent": "Avatar Generator Agent",
            "result": {
                "portrait_prompt": data.get("portrait_prompt", f"professional {request.gender} presenter, {request.style}"),
                "negative_prompt": data.get("negative_prompt", "cartoon, blurry, low quality"),
                "lighting": data.get("lighting", "soft studio three-point lighting"),
                "camera_angle": data.get("camera_angle", "front-facing portrait"),
                "clothing_style": data.get("clothing_style", "business casual"),
                "background_desc": data.get("background_desc", request.background),
                "post_processing": data.get("post_processing", "cinematic color grade"),
                "note": "Prompt ready for Stable Diffusion Portrait Model"
            }
        }
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Avatar Generator Agent failed: {exc}") from exc


# ── Agent 7: Voice Agent (gTTS) ───────────────────────────────────────────────

@app.post("/api/v1/synthesize-voice")
def synthesize_voice(request: VoiceSynthesisRequest) -> dict[str, Any]:
    """Voice Agent: Synthesizes speech using gTTS and returns base64-encoded audio."""
    if not GTTS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Voice Agent: gTTS not installed. Run: pip install gtts")

    try:
        tts = gTTS(text=request.text, lang=request.language, slow=request.slow)
        filename = f"voice_{uuid.uuid4().hex}.mp3"
        filepath = AUDIO_OUT_DIR / filename
        tts.save(str(filepath))

        with open(filepath, "rb") as f:
            audio_b64 = base64.b64encode(f.read()).decode("utf-8")

        # Clean up file after encoding
        filepath.unlink(missing_ok=True)

        return {
            "status": "completed",
            "agent": "Voice Agent",
            "engine": "gTTS",
            "language": request.language,
            "text_length": len(request.text),
            "audio_base64": audio_b64,
            "audio_format": "mp3",
            "note": "Play with: new Audio('data:audio/mp3;base64,' + audio_base64).play()"
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Voice Agent failed: {exc}") from exc


# ── Agent 8: Lip-Sync Agent ────────────────────────────────────────────────────

@app.post("/api/v1/lip-sync-info")
def lip_sync_info(request: LipSyncRequest) -> dict[str, Any]:
    """Lip-Sync Agent: Generates phoneme timing data for avatar animation."""
    words = request.text.split()
    word_count = len(words)
    time_per_word = request.duration / max(word_count, 1)

    # Generate phoneme-level timing (approximation)
    mouth_frames: list[dict[str, Any]] = []
    phoneme_map = {"a": "open", "e": "half", "i": "narrow", "o": "round", "u": "round",
                   " ": "closed", "m": "closed", "b": "closed", "p": "closed"}

    current_time = 0.0
    for word in words:
        word_start = current_time
        for char in word.lower():
            mouth_shape = phoneme_map.get(char, "neutral")
            mouth_frames.append({
                "time": round(current_time, 3),
                "frame": round(current_time * request.fps),
                "mouth_shape": mouth_shape,
                "character": char
            })
            current_time += time_per_word / max(len(word), 1)
        mouth_frames.append({"time": round(current_time, 3), "frame": round(current_time * request.fps), "mouth_shape": "closed", "character": " "})

    return {
        "status": "completed",
        "agent": "Lip-Sync Agent",
        "engine": "phoneme-approximation",
        "text": request.text,
        "duration": request.duration,
        "fps": request.fps,
        "word_count": word_count,
        "frame_count": round(request.duration * request.fps),
        "mouth_frames": mouth_frames[:200],  # limit response size
        "note": "For production use: MuseTalk / Wav2Lip with CUDA GPU"
    }


# ── Agent 10: Compositor Agent ────────────────────────────────────────────────

@app.post("/api/v1/composite-video")
def composite_video(request: CompositeRequest) -> dict[str, Any]:
    """Compositor Agent: Generates FFmpeg command for video composition."""
    if not ffmpeg_available():
        return {
            "status": "unavailable",
            "agent": "Compositor Agent",
            "message": "FFmpeg not found on PATH. Install FFmpeg and add to system PATH.",
            "install_url": "https://ffmpeg.org/download.html",
            "ffmpeg_command": "# FFmpeg not available",
        }

    # Build a representative FFmpeg command
    scenes_info = [f"Scene {s.get('id')}: {s.get('start'):.1f}s-{s.get('end'):.1f}s" for s in request.scenes[:5]]
    ffmpeg_cmd = (
        f"ffmpeg -i input.mp4 "
        f"-vf \"scale=1920:1080,fps=30\" "
        f"-c:v libx264 -preset fast -crf 18 "
        f"-c:a aac -b:a 192k "
        f"-movflags +faststart output_composed.mp4"
    )

    return {
        "status": "completed",
        "agent": "Compositor Agent",
        "engine": "FFmpeg",
        "job_id": request.job_id,
        "scenes_count": len(request.scenes),
        "scenes_preview": scenes_info,
        "ffmpeg_command": ffmpeg_cmd,
        "settings": {
            "resolution": "1920x1080",
            "fps": 30,
            "codec": "H.264",
            "audio": "AAC 192kbps",
        },
        "note": "Run the ffmpeg_command in a terminal from your uploads directory."
    }


# ── Agent 11: Multi-Language Agent ────────────────────────────────────────────

@app.post("/api/v1/translate-script")
def translate_script(request: TranslationRequest) -> dict[str, Any]:
    """Multi-Language Agent: Translates script text and scene narrations."""
    if not DEEP_TRANSLATOR_AVAILABLE:
        raise HTTPException(status_code=503, detail="Multi-Language Agent: deep-translator not installed. Run: pip install deep-translator")

    try:
        translator = GoogleTranslator(source=request.source_language, target=request.target_language)

        # Translate main text
        translated_text = translator.translate(request.text) if request.text else ""

        # Translate all scenes if provided
        translated_scenes: list[dict[str, Any]] = []
        for scene in request.scenes:
            translated_scene = dict(scene)
            if scene.get("text"):
                translated_scene["text_original"] = scene["text"]
                translated_scene["text"] = translator.translate(scene["text"])
            translated_scenes.append(translated_scene)

        return {
            "status": "completed",
            "agent": "Multi-Language Agent",
            "engine": "deep-translator (Google)",
            "source_language": request.source_language,
            "target_language": request.target_language,
            "original_text": request.text,
            "translated_text": translated_text,
            "translated_scenes": translated_scenes,
            "scenes_translated": len(translated_scenes),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Multi-Language Agent failed: {exc}") from exc


# ── Agent 12: Brand Kit Agent ─────────────────────────────────────────────────

@app.post("/api/v1/apply-brand-kit")
def apply_brand_kit(request: BrandKitRequest) -> dict[str, Any]:
    """Brand Kit Agent: Applies branding configuration to all scenes."""
    brand = {
        "logo_text": request.logo_text,
        "primary_color": request.primary_color,
        "secondary_color": request.secondary_color,
        "font": request.font,
        "watermark": request.watermark,
    }

    # Generate CSS overlay rules
    css_rules = f"""
/* SmartEdit AI — Brand Kit Agent CSS */
:root {{
  --brand-primary: {request.primary_color};
  --brand-secondary: {request.secondary_color};
  --brand-font: '{request.font}', sans-serif;
}}
.brand-overlay {{
  font-family: var(--brand-font);
  color: var(--brand-primary);
}}
.brand-logo {{
  color: var(--brand-primary);
  font-weight: 800;
  letter-spacing: -0.5px;
}}
.brand-watermark {{
  position: absolute;
  bottom: 16px;
  right: 16px;
  opacity: 0.7;
  font-size: 12px;
  color: var(--brand-primary);
  font-family: var(--brand-font);
}}
.subtitle-display {{
  background: linear-gradient(135deg, {request.primary_color}CC, {request.secondary_color}CC);
  border-left: 3px solid {request.primary_color};
}}
""".strip()

    # Apply brand to each scene
    branded_scenes = []
    for scene in request.scenes:
        branded = dict(scene)
        branded["brand_applied"] = True
        branded["primary_color"] = request.primary_color
        branded["secondary_color"] = request.secondary_color
        branded["font"] = request.font
        branded_scenes.append(branded)

    return {
        "status": "completed",
        "agent": "Brand Kit Agent",
        "brand": brand,
        "css_rules": css_rules,
        "scenes_branded": len(branded_scenes),
        "branded_scenes": branded_scenes,
        "ffmpeg_watermark": f"ffmpeg -i input.mp4 -vf \"drawtext=text='{request.logo_text}':fontsize=24:fontcolor=white:x=w-tw-10:y=h-th-10\" output_branded.mp4"
    }


# ── Agent 13: Conversation Mode Agent ────────────────────────────────────────

@app.post("/api/v1/conversation-split")
def conversation_split(request: ConversationSplitRequest) -> dict[str, Any]:
    """Conversation Mode Agent: Splits script into dual-speaker dialogue."""
    if not request.scenes:
        raise HTTPException(status_code=400, detail="No scenes provided.")

    scenes_text = "\n".join(
        f"Scene {s.get('id', i+1)}: \"{s.get('text', '')}\""
        for i, s in enumerate(request.scenes[:6])
    )

    prompt = f"""You are the SmartEdit AI Conversation Mode Agent.
Split this video script into a natural two-speaker dialogue for podcast/interview format.

Speaker A: {request.speaker_a_name}
Speaker B: {request.speaker_b_name}

Original scenes:
{scenes_text}

Return ONLY valid JSON:
{{
  "dialogue": [
    {{
      "scene_id": 1,
      "speaker": "{request.speaker_a_name}",
      "text": "Speaker A's dialogue for this scene",
      "layout": "dual-conversation",
      "camera": "speaker_a"
    }},
    {{
      "scene_id": 1,
      "speaker": "{request.speaker_b_name}",
      "text": "Speaker B's response",
      "layout": "dual-conversation",
      "camera": "speaker_b"
    }}
  ]
}}"""

    try:
        data = call_ollama_json(prompt, temperature=0.6)
        dialogue = data.get("dialogue", [])
        return {
            "status": "completed",
            "agent": "Conversation Mode Agent",
            "model": OLLAMA_MODEL,
            "speaker_a": request.speaker_a_name,
            "speaker_b": request.speaker_b_name,
            "dialogue": dialogue,
            "exchange_count": len(dialogue),
        }
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Conversation Mode Agent failed: {exc}") from exc


# ── Agent 14: Natural Language Edit Agent ────────────────────────────────────

@app.post("/api/v1/nl-edit")
def nl_edit(request: NLEditRequest) -> dict[str, Any]:
    """NL Edit Agent: Parses natural language commands and generates scene diffs."""
    scenes_summary = "\n".join(
        f"Scene {s.get('id', i+1)}: layout={s.get('layout','?')}, text=\"{s.get('text','')[:80]}\""
        for i, s in enumerate(request.scenes[:6])
    )

    prompt = f"""You are the SmartEdit AI Natural Language Edit Agent.
Parse this edit command and generate a scene modification instruction.

User command: "{request.command}"
Current scene focus: Scene ID {request.current_scene_id}

Available scenes:
{scenes_summary}

Return ONLY valid JSON:
{{
  "action": "change_layout | change_color | change_text | change_music | apply_transition | change_speaker | add_subtitle",
  "target_scene_ids": [1],
  "target_all": false,
  "changes": {{
    "layout": "new-layout-if-applicable",
    "color": "#hex-if-applicable",
    "text": "new-text-if-applicable",
    "transition": "fade | zoom | slide | none"
  }},
  "explanation": "Human-readable explanation of what will change",
  "confidence": 0.95
}}"""

    try:
        data = call_ollama_json(prompt, temperature=0.2)
        return {
            "status": "completed",
            "agent": "Natural Language Edit Agent",
            "model": OLLAMA_MODEL,
            "command": request.command,
            "action": data.get("action", "unknown"),
            "target_scene_ids": data.get("target_scene_ids", []),
            "target_all": data.get("target_all", False),
            "changes": data.get("changes", {}),
            "explanation": data.get("explanation", "No changes identified."),
            "confidence": data.get("confidence", 0.0),
        }
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"NL Edit Agent failed: {exc}") from exc


# ── Agent 15: Music / Sound Agent ─────────────────────────────────────────────

@app.post("/api/v1/select-music")
def select_music(request: MusicSelectionRequest) -> dict[str, Any]:
    """Music/Sound Agent: Selects music profile and generates FFmpeg audio ducking command."""
    music_profiles = {
        "energetic":  {"tempo": "fast", "genre": "electronic/trap", "bpm": 140, "key": "Am", "intensity": "high"},
        "calm":       {"tempo": "slow", "genre": "ambient/lo-fi", "bpm": 70, "key": "Dm", "intensity": "low"},
        "dramatic":   {"tempo": "medium", "genre": "orchestral/cinematic", "bpm": 90, "key": "Cm", "intensity": "high"},
        "upbeat":     {"tempo": "medium-fast", "genre": "pop/indie", "bpm": 115, "key": "C", "intensity": "medium"},
        "neutral":    {"tempo": "medium", "genre": "corporate/ambient", "bpm": 95, "key": "G", "intensity": "medium"},
    }

    profile = music_profiles.get(request.mood, music_profiles["neutral"])

    ducking_cmd = ""
    if request.duck_on_speech and ffmpeg_available():
        ducking_cmd = (
            "ffmpeg -i video.mp4 -i music.mp3 "
            "-filter_complex \"[1:a]volume=0.3[bg]; "
            "[0:a][bg]amix=inputs=2:duration=first:dropout_transition=2[out]\" "
            "-map 0:v -map \"[out]\" -c:v copy -c:a aac output_with_music.mp4"
        )

    return {
        "status": "completed",
        "agent": "Music/Sound Agent",
        "mood": request.mood,
        "duration_seconds": request.duration_seconds,
        "music_profile": profile,
        "search_query": f"royalty-free {profile['genre']} {profile['bpm']}bpm {request.mood} background music",
        "recommended_sources": [
            "Pixabay Music (free, no attribution)",
            "Free Music Archive (CC licensed)",
            "Incompetech.com (Kevin MacLeod)",
        ],
        "ffmpeg_ducking_command": ducking_cmd or "Install FFmpeg for audio ducking commands.",
        "volume_settings": {
            "music_normal": "30%",
            "music_ducked": "8%",
            "speech_priority": True,
            "duck_db": -14,
        }
    }


# ── Agent 16: Export Optimizer Agent ─────────────────────────────────────────

@app.post("/api/v1/export-video")
def export_video(request: ExportRequest) -> dict[str, Any]:
    """Export Optimizer Agent: Generates platform-optimized FFmpeg export commands."""
    resolution_map = {
        "720p":  {"w": 1280, "h": 720},
        "1080p": {"w": 1920, "h": 1080},
        "4K":    {"w": 3840, "h": 2160},
    }
    ratio_map = {
        "16:9": {"scale": "scale={w}:{h}", "label": "YouTube/Standard"},
        "9:16": {"scale": "scale={h}:{w}", "label": "Reels/Shorts/TikTok"},
        "1:1":  {"scale": "scale={h}:{h}", "label": "Instagram/LinkedIn"},
    }
    codec_map = {
        "h264": {"vcodec": "libx264", "preset": "fast", "crf": 20},
        "h265": {"vcodec": "libx265", "preset": "medium", "crf": 24},
        "av1":  {"vcodec": "libaom-av1", "preset": "slow", "crf": 30},
    }

    res = resolution_map.get(request.resolution, resolution_map["1080p"])
    ratio = ratio_map.get(request.aspect_ratio, ratio_map["16:9"])
    codec = codec_map.get(request.codec, codec_map["h264"])
    scale_filter = ratio["scale"].format(**res)

    subtitle_filter = ",subtitles=captions.srt" if request.include_subtitles else ""
    vf_filter = f"{scale_filter},fps={request.fps}{subtitle_filter}"

    ffmpeg_cmd = (
        f"ffmpeg -i input.mp4 "
        f"-vf \"{vf_filter}\" "
        f"-c:v {codec['vcodec']} -preset {codec['preset']} -crf {codec['crf']} "
        f"-c:a aac -b:a 192k "
        f"-movflags +faststart "
        f"output_{request.aspect_ratio.replace(':','x')}_{request.resolution}.mp4"
    )

    ffmpeg_ok = ffmpeg_available()

    return {
        "status": "completed" if ffmpeg_ok else "command_ready",
        "agent": "Export Optimizer Agent",
        "platform": ratio["label"],
        "aspect_ratio": request.aspect_ratio,
        "resolution": request.resolution,
        "fps": request.fps,
        "codec": request.codec,
        "include_subtitles": request.include_subtitles,
        "output_filename": f"smartedit_export_{request.aspect_ratio.replace(':','x')}_{request.resolution}.mp4",
        "ffmpeg_command": ffmpeg_cmd,
        "ffmpeg_available": ffmpeg_ok,
        "estimated_file_size": f"~{res['w'] * res['h'] * request.fps // 5_000_000} MB for 1 min",
        "presets": {
            "youtube":   "/api/v1/export-video with aspect_ratio=16:9, resolution=1080p",
            "reels":     "/api/v1/export-video with aspect_ratio=9:16, resolution=1080p",
            "linkedin":  "/api/v1/export-video with aspect_ratio=1:1, resolution=1080p",
            "cinematic": "/api/v1/export-video with aspect_ratio=16:9, resolution=4K, codec=h265",
        }
    }


# ─────────────────────────────────────────────────────────────────────────────
# NEW AGENTS — Section 2 (Agents 17-28)
# ─────────────────────────────────────────────────────────────────────────────

class SceneDetectionRequest(BaseModel):
    transcript_segments: list[dict[str, Any]] = Field(default_factory=list)
    threshold: float = Field(0.4, ge=0.1, le=1.0, description="Semantic similarity threshold")
    min_scene_duration: float = Field(3.0)


class JumpCutRequest(BaseModel):
    segments: list[dict[str, Any]] = Field(default_factory=list)
    silence_threshold_db: float = Field(-40.0)
    min_silence_duration: float = Field(0.3, description="Min silence seconds to remove")
    padding_seconds: float = Field(0.05)


class ViralHookRequest(BaseModel):
    scenes: list[dict[str, Any]] = Field(default_factory=list)
    platform: str = Field("youtube", description="youtube | reels | tiktok | linkedin")
    hook_duration_seconds: float = Field(3.0)


class SEORequest(BaseModel):
    transcript: str = Field(..., min_length=10)
    topic: str = Field("")
    platform: str = Field("youtube", description="youtube | linkedin | instagram | tiktok")
    language: str = Field("en")
    target_audience: str = Field("general")


class ChapterMarkerRequest(BaseModel):
    scenes: list[dict[str, Any]] = Field(default_factory=list)
    min_chapter_duration: float = Field(30.0)


class ThumbnailRequest(BaseModel):
    title: str = Field(..., min_length=3)
    hook: str = Field("")
    style: str = Field("bold-text-overlay", description="bold-text-overlay | minimal | face-close-up | split-before-after")
    platform: str = Field("youtube")
    color_theme: str = Field("dark-purple")


class ColorGradeRequest(BaseModel):
    scenes: list[dict[str, Any]] = Field(default_factory=list)
    mood: str = Field("cinematic", description="cinematic | warm | cool | vibrant | noir | natural | vintage")
    intensity: float = Field(0.7, ge=0.0, le=1.0)


class NoiseReductionRequest(BaseModel):
    job_id: str = Field("")
    noise_profile: str = Field("auto", description="auto | room | outdoor | studio | street")
    strength: float = Field(0.5, ge=0.0, le=1.0)


class BRollRequest(BaseModel):
    scenes: list[dict[str, Any]] = Field(default_factory=list)
    style: str = Field("cinematic", description="cinematic | documentary | stock | animated")


class ScriptOptimizerRequest(BaseModel):
    scenes: list[dict[str, Any]] = Field(default_factory=list)
    goal: str = Field("engagement", description="engagement | clarity | seo | retention | conversion")
    tone: str = Field("professional", description="professional | casual | energetic | educational | storytelling")


class EmotionAnalysisRequest(BaseModel):
    scenes: list[dict[str, Any]] = Field(default_factory=list)
    transcript: str = Field("")


class ViralClipRequest(BaseModel):
    scenes: list[dict[str, Any]] = Field(default_factory=list)
    platform: str = Field("reels", description="reels | tiktok | shorts | linkedin")
    clip_duration_max: float = Field(60.0)


# ── Agent 17: Scene Detection Agent ──────────────────────────────────────────

@app.post("/api/v1/detect-scenes")
def detect_scenes(request: SceneDetectionRequest) -> dict[str, Any]:
    """Scene Detection Agent: Groups transcript segments into semantic scenes using keyword clustering."""
    segments = request.transcript_segments
    if not segments:
        raise HTTPException(status_code=400, detail="No transcript segments provided.")

    # Cluster segments into scenes based on time gaps and keyword shifts
    scenes: list[dict[str, Any]] = []
    current_scene_segs: list[dict[str, Any]] = []
    scene_id = 1

    for i, seg in enumerate(segments):
        current_scene_segs.append(seg)
        # Scene boundary: long time gap or enough segments accumulated
        next_seg = segments[i + 1] if i + 1 < len(segments) else None
        time_gap = (next_seg["start"] - seg["end"]) if next_seg and "start" in next_seg and "end" in seg else 0
        scene_too_long = sum((s.get("end", 0) - s.get("start", 0)) for s in current_scene_segs) >= 25

        if not next_seg or time_gap > 1.2 or scene_too_long:
            if current_scene_segs:
                start_t = current_scene_segs[0].get("start", 0)
                end_t = current_scene_segs[-1].get("end", start_t + 5)
                scene_text = " ".join(s.get("text", "") for s in current_scene_segs).strip()
                duration = end_t - start_t
                if duration >= request.min_scene_duration:
                    scenes.append({
                        "id": scene_id,
                        "start": round(start_t, 3),
                        "end": round(end_t, 3),
                        "duration": round(duration, 2),
                        "text": scene_text,
                        "segment_count": len(current_scene_segs),
                        "suggested_layout": "full-presenter" if len(scene_text.split()) < 40 else "split-screen",
                        "boundary_reason": "time_gap" if time_gap > 1.2 else "max_duration"
                    })
                    scene_id += 1
                current_scene_segs = []

    return {
        "status": "completed",
        "agent": "Scene Detection Agent",
        "input_segments": len(segments),
        "detected_scenes": len(scenes),
        "scenes": scenes,
        "threshold_used": request.threshold,
        "note": "Scenes detected via time-gap clustering. For semantic detection, pair with Ollama Layout Planner."
    }


# ── Agent 18: Jump Cut Editor Agent ──────────────────────────────────────────

@app.post("/api/v1/jump-cut")
def jump_cut(request: JumpCutRequest) -> dict[str, Any]:
    """Jump Cut Editor Agent: Identifies silence gaps in segments for automatic removal."""
    segments = request.segments
    if not segments:
        raise HTTPException(status_code=400, detail="No segments provided.")

    kept_segments: list[dict[str, Any]] = []
    removed_gaps: list[dict[str, Any]] = []
    total_removed_duration = 0.0

    for i, seg in enumerate(segments):
        start = seg.get("start", 0)
        end = seg.get("end", start)
        duration = end - start

        if duration < 0.1:
            removed_gaps.append({"start": start, "end": end, "reason": "too_short"})
            total_removed_duration += duration
            continue

        # Check for silence gap before this segment
        if i > 0 and kept_segments:
            gap_start = kept_segments[-1]["end"]
            gap_end = start
            gap_dur = gap_end - gap_start
            if gap_dur >= request.min_silence_duration:
                removed_gaps.append({
                    "start": round(gap_start, 3),
                    "end": round(gap_end, 3),
                    "duration": round(gap_dur, 3),
                    "reason": "silence_gap"
                })
                total_removed_duration += gap_dur

        kept_segments.append(dict(seg))

    # Build FFmpeg concat filter for jump cuts
    ffmpeg_filters = []
    for idx, seg in enumerate(kept_segments):
        s = seg.get("start", 0)
        e = seg.get("end", s)
        pad_s = max(0, s - request.padding_seconds)
        pad_e = e + request.padding_seconds
        ffmpeg_filters.append(f"[0:v]trim={pad_s:.3f}:{pad_e:.3f},setpts=PTS-STARTPTS[v{idx}]; [0:a]atrim={pad_s:.3f}:{pad_e:.3f},asetpts=PTS-STARTPTS[a{idx}]")

    concat_inputs = "".join(f"[v{i}][a{i}]" for i in range(len(kept_segments)))
    concat_filter = concat_inputs + f"concat=n={len(kept_segments)}:v=1:a=1[outv][outa]"
    ffmpeg_cmd = f"ffmpeg -i input.mp4 -filter_complex \"{'; '.join(ffmpeg_filters)}; {concat_filter}\" -map \"[outv]\" -map \"[outa]\" jump_cut_output.mp4"

    original_duration = sum((s.get("end", 0) - s.get("start", 0)) for s in segments)
    new_duration = original_duration - total_removed_duration

    return {
        "status": "completed",
        "agent": "Jump Cut Editor Agent",
        "original_duration": round(original_duration, 2),
        "new_duration": round(new_duration, 2),
        "time_saved_seconds": round(total_removed_duration, 2),
        "silences_removed": len(removed_gaps),
        "kept_segments": len(kept_segments),
        "removed_gaps": removed_gaps[:20],
        "ffmpeg_command": ffmpeg_cmd if len(kept_segments) <= 20 else "# Too many segments for inline command — use script mode",
        "note": f"Removed {len(removed_gaps)} silence gaps, saving {total_removed_duration:.1f}s of dead air."
    }


# ── Agent 19: Viral Hook Analyzer Agent ──────────────────────────────────────

@app.post("/api/v1/analyze-hook")
def analyze_hook(request: ViralHookRequest) -> dict[str, Any]:
    """Viral Hook Analyzer Agent: Analyzes first 3 seconds and suggests improvements for viewer retention."""
    if not request.scenes:
        raise HTTPException(status_code=400, detail="No scenes provided.")

    hook_scenes = [s for s in request.scenes if s.get("start", 0) < request.hook_duration_seconds * 3]
    hook_text = " ".join(s.get("text", "") for s in hook_scenes[:2]).strip()
    if not hook_text:
        hook_text = request.scenes[0].get("text", "")[:200]

    platform_tips = {
        "youtube":  {"max_hook_words": 12, "style": "bold question or surprising stat", "cta": "Subscribe for more"},
        "reels":    {"max_hook_words": 8,  "style": "visual shock + caption text", "cta": "Follow for daily tips"},
        "tiktok":   {"max_hook_words": 6,  "style": "trend audio + unexpected twist", "cta": "Duet this"},
        "linkedin": {"max_hook_words": 15, "style": "professional insight or achievement", "cta": "Save this post"},
    }
    tips = platform_tips.get(request.platform, platform_tips["youtube"])

    prompt = f"""You are the SmartEdit AI Viral Hook Analyzer Agent.
Analyze this video opening and suggest improvements for maximum viewer retention.

Current hook text (first {request.hook_duration_seconds}s): "{hook_text}"
Platform: {request.platform}
Hook style for this platform: {tips['style']}

Return ONLY valid JSON:
{{
  "hook_score": 7.2,
  "hook_grade": "B+",
  "weaknesses": ["missing pattern interrupt", "no emotional trigger"],
  "improved_hook": "the rewritten, improved hook line (max {tips['max_hook_words']} words)",
  "alternative_hooks": ["hook variant 1", "hook variant 2", "hook variant 3"],
  "first_frame_suggestion": "visual direction for the first frame",
  "retention_tip": "specific advice to improve watch time past 3 seconds",
  "cta": "{tips['cta']}"
}}"""

    try:
        data = call_ollama_json(prompt, temperature=0.6)
        return {
            "status": "completed",
            "agent": "Viral Hook Analyzer Agent",
            "model": OLLAMA_MODEL,
            "platform": request.platform,
            "original_hook": hook_text[:150],
            "hook_score": data.get("hook_score", 6.0),
            "hook_grade": data.get("hook_grade", "C"),
            "weaknesses": data.get("weaknesses", []),
            "improved_hook": data.get("improved_hook", ""),
            "alternative_hooks": data.get("alternative_hooks", []),
            "first_frame_suggestion": data.get("first_frame_suggestion", ""),
            "retention_tip": data.get("retention_tip", ""),
            "cta": data.get("cta", tips["cta"]),
        }
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Viral Hook Analyzer failed: {exc}") from exc


# ── Agent 20: SEO Metadata Agent ─────────────────────────────────────────────

@app.post("/api/v1/generate-seo")
def generate_seo(request: SEORequest) -> dict[str, Any]:
    """SEO Metadata Agent: Generates platform-optimized titles, descriptions, tags, and timestamps."""
    prompt = f"""You are the SmartEdit AI SEO Metadata Agent.
Generate complete, platform-optimized metadata for this video.

Transcript (first 500 chars): "{request.transcript[:500]}"
Topic: "{request.topic}"
Platform: {request.platform}
Target audience: {request.target_audience}
Language: {request.language}

Return ONLY valid JSON:
{{
  "title": "Click-worthy, SEO-optimized title (max 70 chars)",
  "title_variants": ["variant 1", "variant 2", "variant 3"],
  "description": "Full description with keywords naturally embedded (150-300 words)",
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5", "tag6", "tag7", "tag8", "tag9", "tag10"],
  "hashtags": ["#hashtag1", "#hashtag2", "#hashtag3", "#hashtag4", "#hashtag5"],
  "thumbnail_text": "Bold overlay text for thumbnail (max 5 words)",
  "first_comment": "Pinned first comment to boost engagement",
  "end_screen_cta": "End screen call-to-action text",
  "category": "video category",
  "language": "{request.language}"
}}"""

    try:
        data = call_ollama_json(prompt, temperature=0.5)
        return {
            "status": "completed",
            "agent": "SEO Metadata Agent",
            "model": OLLAMA_MODEL,
            "platform": request.platform,
            "title": data.get("title", ""),
            "title_variants": data.get("title_variants", []),
            "description": data.get("description", ""),
            "tags": data.get("tags", []),
            "hashtags": data.get("hashtags", []),
            "thumbnail_text": data.get("thumbnail_text", ""),
            "first_comment": data.get("first_comment", ""),
            "end_screen_cta": data.get("end_screen_cta", ""),
            "category": data.get("category", ""),
            "character_counts": {
                "title": len(data.get("title", "")),
                "description": len(data.get("description", "")),
            }
        }
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"SEO Metadata Agent failed: {exc}") from exc


# ── Agent 21: Chapter Marker Agent ───────────────────────────────────────────

@app.post("/api/v1/generate-chapters")
def generate_chapters(request: ChapterMarkerRequest) -> dict[str, Any]:
    """Chapter Marker Agent: Auto-generates YouTube chapter timestamps from scene data."""
    scenes = request.scenes
    if not scenes:
        raise HTTPException(status_code=400, detail="No scenes provided.")

    chapters: list[dict[str, Any]] = []
    chapter_id = 1
    current_start = 0.0
    accumulated_text: list[str] = []
    accumulated_duration = 0.0

    for i, scene in enumerate(scenes):
        s = float(scene.get("start", scene.get("s", 0)))
        e = float(scene.get("end", scene.get("e", s + 5)))
        duration = e - s
        accumulated_duration += duration
        accumulated_text.append(scene.get("text", ""))

        is_last = (i == len(scenes) - 1)
        if accumulated_duration >= request.min_chapter_duration or is_last:
            full_text = " ".join(accumulated_text)[:80].strip()
            # Derive chapter title from text (first meaningful phrase)
            words = full_text.split()[:6]
            chapter_title = " ".join(words).rstrip(".,!?") if words else f"Chapter {chapter_id}"

            # Format timestamp as MM:SS
            mins = int(current_start) // 60
            secs = int(current_start) % 60
            timestamp = f"{mins:02d}:{secs:02d}"

            chapters.append({
                "id": chapter_id,
                "timestamp": timestamp,
                "start_seconds": round(current_start, 2),
                "title": chapter_title,
                "duration_seconds": round(accumulated_duration, 2),
            })

            chapter_id += 1
            current_start = e
            accumulated_text = []
            accumulated_duration = 0.0

    # Build YouTube description format
    youtube_chapters = "\n".join(f"{c['timestamp']} {c['title']}" for c in chapters)
    youtube_chapters = "00:00 Intro\n" + youtube_chapters if chapters and chapters[0]["timestamp"] != "00:00" else youtube_chapters

    return {
        "status": "completed",
        "agent": "Chapter Marker Agent",
        "chapter_count": len(chapters),
        "chapters": chapters,
        "youtube_description_format": youtube_chapters,
        "note": "Paste the youtube_description_format block at the top of your YouTube video description."
    }


# ── Agent 22: Thumbnail Generator Agent ──────────────────────────────────────

@app.post("/api/v1/generate-thumbnail")
def generate_thumbnail(request: ThumbnailRequest) -> dict[str, Any]:
    """Thumbnail Generator Agent: Creates detailed SD/DALL-E prompts for viral thumbnails."""
    color_themes = {
        "dark-purple": {"bg": "#1a0033", "accent": "#8B5CF6", "text": "#FFFFFF"},
        "electric-blue": {"bg": "#0a0a2e", "accent": "#3B82F6", "text": "#00F5FF"},
        "fire-orange": {"bg": "#1a0800", "accent": "#F59E0B", "text": "#FFFFFF"},
        "green-neon": {"bg": "#001a00", "accent": "#10B981", "text": "#00FF88"},
        "red-drama": {"bg": "#1a0000", "accent": "#EF4444", "text": "#FFFFFF"},
    }
    theme = color_themes.get(request.color_theme, color_themes["dark-purple"])

    style_desc = {
        "bold-text-overlay": "large bold text overlay on dramatic background, YouTube thumbnail style",
        "minimal": "clean minimal design, lots of whitespace, subtle text",
        "face-close-up": "close-up reaction face with text beside it, MrBeast style",
        "split-before-after": "dramatic before/after split image with comparison text"
    }.get(request.style, "professional YouTube thumbnail")

    prompt = f"""You are the SmartEdit AI Thumbnail Generator Agent.
Create a viral thumbnail design for this video.

Title: "{request.title}"
Hook: "{request.hook}"
Style: {style_desc}
Platform: {request.platform}
Color theme: bg={theme['bg']}, accent={theme['accent']}

Return ONLY valid JSON:
{{
  "image_prompt": "detailed SD/DALL-E image generation prompt for the thumbnail background",
  "text_overlay": [{{"text": "LINE 1", "size": "xl", "color": "#ffffff", "position": "top-center"}}, {{"text": "LINE 2", "size": "lg", "color": "{theme['accent']}", "position": "bottom-center"}}],
  "design_tip": "specific advice to maximize CTR",
  "a_b_variant_prompt": "alternative thumbnail image prompt for A/B testing",
  "face_expression": "expression to use if using face in thumbnail",
  "prop_suggestion": "any prop or element to add for visual punch",
  "avoid": "what to avoid in the thumbnail design"
}}"""

    try:
        data = call_ollama_json(prompt, temperature=0.7)
        return {
            "status": "completed",
            "agent": "Thumbnail Generator Agent",
            "model": OLLAMA_MODEL,
            "title": request.title,
            "platform": request.platform,
            "style": request.style,
            "color_theme": theme,
            "image_prompt": data.get("image_prompt", f"viral YouTube thumbnail, {request.title}, {style_desc}"),
            "text_overlay": data.get("text_overlay", [{"text": request.title[:30].upper(), "size": "xl", "color": "#ffffff"}]),
            "design_tip": data.get("design_tip", ""),
            "a_b_variant_prompt": data.get("a_b_variant_prompt", ""),
            "face_expression": data.get("face_expression", "surprised/excited"),
            "prop_suggestion": data.get("prop_suggestion", ""),
            "avoid": data.get("avoid", ""),
            "canvas_css": f"background:{theme['bg']};color:{theme['text']};font-family:'Inter',sans-serif;border:3px solid {theme['accent']};"
        }
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Thumbnail Generator failed: {exc}") from exc


# ── Agent 23: Color Grading Agent ────────────────────────────────────────────

@app.post("/api/v1/color-grade")
def color_grade(request: ColorGradeRequest) -> dict[str, Any]:
    """Color Grading Agent: Generates FFmpeg color correction filters for specific visual moods."""
    lut_profiles = {
        "cinematic": {
            "eq": "contrast=1.2:brightness=-0.05:saturation=0.85",
            "curves": "r='0/0 0.3/0.2 1/0.9':g='0/0 0.5/0.45 1/0.95':b='0/0.05 0.5/0.5 1/1'",
            "vignette": "vignette=PI/4",
            "desc": "Desaturated, high-contrast cinematic look with lifted blacks",
        },
        "warm": {
            "eq": "contrast=1.1:brightness=0.05:saturation=1.2:gamma_r=1.1:gamma_b=0.9",
            "curves": "r='0/0 0.5/0.6 1/1':b='0/0 0.5/0.4 1/0.85'",
            "vignette": "vignette=PI/5",
            "desc": "Warm golden tones, boosted reds and yellows",
        },
        "cool": {
            "eq": "contrast=1.05:brightness=0:saturation=0.9:gamma_r=0.9:gamma_b=1.1",
            "curves": "b='0/0 0.5/0.6 1/1':r='0/0 0.5/0.45 1/0.9'",
            "vignette": "",
            "desc": "Cool blue tones, de-emphasized reds",
        },
        "vibrant": {
            "eq": "contrast=1.15:brightness=0.02:saturation=1.5",
            "curves": "all='0/0 0.5/0.5 1/1'",
            "vignette": "",
            "desc": "Punchy, saturated colors for social media",
        },
        "noir": {
            "eq": "contrast=1.5:brightness=-0.1:saturation=0",
            "curves": "all='0/0 0.3/0.15 0.7/0.85 1/1'",
            "vignette": "vignette=PI/3",
            "desc": "Black and white high contrast dramatic look",
        },
        "vintage": {
            "eq": "contrast=0.9:brightness=0.05:saturation=0.7",
            "curves": "r='0/0.1 0.5/0.6 1/0.95':b='0/0.1 0.5/0.4 1/0.8'",
            "vignette": "vignette=PI/3.5",
            "desc": "Faded vintage film look with lifted blacks",
        },
        "natural": {
            "eq": "contrast=1.05:brightness=0:saturation=1.05",
            "curves": "all='0/0 0.5/0.5 1/1'",
            "vignette": "",
            "desc": "Clean natural color with minimal processing",
        },
    }

    profile = lut_profiles.get(request.mood, lut_profiles["cinematic"])
    intensity = request.intensity

    # Build FFmpeg vf chain
    vf_parts = [f"eq={profile['eq']}"]
    if profile.get("curves"):
        vf_parts.append(f"curves={profile['curves']}")
    if profile.get("vignette") and intensity > 0.3:
        vf_parts.append(profile["vignette"])

    vf_filter = ",".join(vf_parts)
    ffmpeg_cmd = f'ffmpeg -i input.mp4 -vf "{vf_filter}" -c:a copy color_graded_{request.mood}.mp4'

    # Apply to scenes
    graded_scenes = [dict(s) | {"color_grade": request.mood, "grade_applied": True} for s in request.scenes]

    return {
        "status": "completed",
        "agent": "Color Grading Agent",
        "mood": request.mood,
        "intensity": request.intensity,
        "profile": profile,
        "ffmpeg_vf_filter": vf_filter,
        "ffmpeg_command": ffmpeg_cmd,
        "scenes_graded": len(graded_scenes),
        "css_filter": f"filter: contrast({0.9 + intensity * 0.3}) saturate({0.7 + intensity * 0.6}) brightness({0.95 + intensity * 0.1});",
        "note": f"{profile['desc']}"
    }


# ── Agent 24: Noise Reduction Agent ──────────────────────────────────────────

@app.post("/api/v1/reduce-noise")
def reduce_noise(request: NoiseReductionRequest) -> dict[str, Any]:
    """Noise Reduction Agent: Generates FFmpeg audio denoising filter commands."""
    noise_presets = {
        "auto":    {"nr": 12, "nf": -25, "highpass": 80,  "lowpass": 8000, "desc": "Auto-balanced noise reduction"},
        "room":    {"nr": 10, "nf": -20, "highpass": 100, "lowpass": 7500, "desc": "Indoor room tone removal"},
        "outdoor": {"nr": 15, "nf": -30, "highpass": 120, "lowpass": 6000, "desc": "Wind and outdoor noise reduction"},
        "studio":  {"nr": 6,  "nf": -15, "highpass": 60,  "lowpass": 16000,"desc": "Subtle studio hiss removal"},
        "street":  {"nr": 20, "nf": -35, "highpass": 150, "lowpass": 5500, "desc": "Heavy street/traffic noise removal"},
    }

    preset = noise_presets.get(request.noise_profile, noise_presets["auto"])
    nr_strength = int(preset["nr"] * request.strength)
    nf_level = preset["nf"] * request.strength

    # FFmpeg afftdn (audio FFT denoising) + highpass/lowpass
    audio_filter = (
        f"afftdn=nr={nr_strength}:nf={nf_level:.1f},"
        f"highpass=f={preset['highpass']},"
        f"lowpass=f={preset['lowpass']},"
        f"loudnorm=I=-16:LRA=11:TP=-1.5"
    )

    ffmpeg_cmd = f'ffmpeg -i input.mp4 -af "{audio_filter}" -c:v copy noise_reduced_{request.noise_profile}.mp4'

    return {
        "status": "completed" if ffmpeg_available() else "command_ready",
        "agent": "Noise Reduction Agent",
        "noise_profile": request.noise_profile,
        "strength": request.strength,
        "profile_desc": preset["desc"],
        "audio_filter": audio_filter,
        "ffmpeg_command": ffmpeg_cmd,
        "ffmpeg_available": ffmpeg_available(),
        "settings": {
            "noise_reduction_db": nr_strength,
            "noise_floor_db": round(nf_level, 1),
            "highpass_hz": preset["highpass"],
            "lowpass_hz": preset["lowpass"],
            "loudnorm": "EBU R128 (-16 LUFS)",
        },
        "note": preset["desc"] + ". Run the ffmpeg_command to apply."
    }


# ── Agent 25: B-Roll Suggestion Agent ────────────────────────────────────────

@app.post("/api/v1/suggest-broll")
def suggest_broll(request: BRollRequest) -> dict[str, Any]:
    """B-Roll Suggestion Agent: Suggests contextual B-roll footage for each scene."""
    if not request.scenes:
        raise HTTPException(status_code=400, detail="No scenes provided.")

    scenes_text = "\n".join(
        f"Scene {s.get('id', i+1)}: \"{s.get('text', '')[:100]}\""
        for i, s in enumerate(request.scenes[:8])
    )

    prompt = f"""You are the SmartEdit AI B-Roll Suggestion Agent.
For each scene, suggest specific B-roll footage to enhance visual storytelling.

Scenes:
{scenes_text}

Style preference: {request.style}

Return ONLY valid JSON:
{{
  "suggestions": [
    {{
      "scene_id": 1,
      "b_roll_idea": "specific footage description",
      "search_query": "stock footage search query",
      "duration_seconds": 4,
      "placement": "before | during | after",
      "transition": "cut | dissolve | zoom",
      "sources": ["Pexels", "Pixabay", "Unsplash"]
    }}
  ]
}}"""

    try:
        data = call_ollama_json(prompt, temperature=0.6)
        suggestions = data.get("suggestions", [])

        # Enrich with royalty-free source links
        free_sources = {
            "Pexels":   "https://www.pexels.com/search/videos/",
            "Pixabay":  "https://pixabay.com/videos/search/",
            "Coverr":   "https://coverr.co/",
            "Mixkit":   "https://mixkit.co/free-stock-video/",
        }

        return {
            "status": "completed",
            "agent": "B-Roll Suggestion Agent",
            "model": OLLAMA_MODEL,
            "style": request.style,
            "scene_count": len(request.scenes),
            "suggestion_count": len(suggestions),
            "suggestions": suggestions,
            "free_sources": free_sources,
            "tip": "Use search_query on any free stock site. Pexels and Pixabay have 4K footage with no attribution required."
        }
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"B-Roll Suggestion Agent failed: {exc}") from exc


# ── Agent 26: Script Optimizer Agent ─────────────────────────────────────────

@app.post("/api/v1/optimize-script")
def optimize_script(request: ScriptOptimizerRequest) -> dict[str, Any]:
    """Script Optimizer Agent: Rewrites scenes for better engagement, clarity, or SEO."""
    if not request.scenes:
        raise HTTPException(status_code=400, detail="No scenes provided.")

    scenes_text = "\n".join(
        f"Scene {s.get('id', i+1)}: \"{s.get('text', '')[:200]}\""
        for i, s in enumerate(request.scenes[:8])
    )

    goal_instructions = {
        "engagement":  "Add emotional triggers, questions, and conversational language.",
        "clarity":     "Simplify complex sentences. Use shorter, clearer words. One idea per sentence.",
        "seo":         "Naturally weave in relevant keywords without stuffing. Use topic phrases.",
        "retention":   "Add pattern interrupts, mini-cliffhangers, and forward references between scenes.",
        "conversion":  "Add specific CTAs, benefit statements, and urgency language at key moments.",
    }

    prompt = f"""You are the SmartEdit AI Script Optimizer Agent.
Rewrite these video scenes to maximize {request.goal}.

Optimization goal: {request.goal} — {goal_instructions.get(request.goal, '')}
Tone: {request.tone}

Original scenes:
{scenes_text}

Return ONLY valid JSON:
{{
  "optimized_scenes": [
    {{
      "id": 1,
      "original_text": "original text",
      "optimized_text": "rewritten improved text",
      "changes_made": ["added hook", "simplified language"],
      "engagement_score_delta": +1.5
    }}
  ],
  "overall_tips": ["tip 1", "tip 2", "tip 3"],
  "readability_grade": "8th grade",
  "estimated_watch_time_improvement": "12%"
}}"""

    try:
        data = call_ollama_json(prompt, temperature=0.5)
        optimized = data.get("optimized_scenes", [])

        # Apply optimizations back to scenes
        opt_map = {s["id"]: s for s in optimized if isinstance(s, dict) and "id" in s}
        updated_scenes = []
        for i, scene in enumerate(request.scenes):
            scene_id = scene.get("id", i + 1)
            opt = opt_map.get(scene_id)
            updated = dict(scene)
            if opt:
                updated["text_original"] = scene.get("text", "")
                updated["text"] = opt.get("optimized_text", scene.get("text", ""))
                updated["optimization_changes"] = opt.get("changes_made", [])
            updated_scenes.append(updated)

        return {
            "status": "completed",
            "agent": "Script Optimizer Agent",
            "model": OLLAMA_MODEL,
            "goal": request.goal,
            "tone": request.tone,
            "scenes_optimized": len(optimized),
            "updated_scenes": updated_scenes,
            "overall_tips": data.get("overall_tips", []),
            "readability_grade": data.get("readability_grade", ""),
            "estimated_watch_time_improvement": data.get("estimated_watch_time_improvement", ""),
        }
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Script Optimizer Agent failed: {exc}") from exc


# ── Agent 27: Emotion Analysis Agent ─────────────────────────────────────────

@app.post("/api/v1/analyze-emotion")
def analyze_emotion(request: EmotionAnalysisRequest) -> dict[str, Any]:
    """Emotion Analysis Agent: Detects emotional tone and energy per scene for pacing insights."""
    scenes = request.scenes
    transcript = request.transcript

    if not scenes and not transcript:
        raise HTTPException(status_code=400, detail="Provide either scenes or transcript.")

    if scenes:
        text_input = "\n".join(
            f"Scene {s.get('id', i+1)}: \"{s.get('text', '')[:150]}\""
            for i, s in enumerate(scenes[:10])
        )
    else:
        text_input = f"Full transcript: \"{transcript[:600]}\""

    prompt = f"""You are the SmartEdit AI Emotion Analysis Agent.
Analyze the emotional tone and energy level of each scene for video pacing insights.

Content:
{text_input}

Return ONLY valid JSON:
{{
  "scene_emotions": [
    {{
      "scene_id": 1,
      "primary_emotion": "excitement | calm | urgency | curiosity | inspiration | tension | humor | empathy",
      "energy_level": 8.5,
      "tone": "upbeat | serious | neutral | dramatic | light",
      "pacing_suggestion": "speed up | maintain | slow down",
      "music_mood_match": "energetic | ambient | dramatic | uplifting | neutral",
      "color_grade_suggestion": "vibrant | warm | cinematic | cool | noir"
    }}
  ],
  "overall_arc": "emotional arc description (e.g. calm → tension → resolution)",
  "pacing_issues": ["any detected pacing problems"],
  "engagement_prediction": "high | medium | low",
  "best_scene_for_thumbnail": 1
}}"""

    try:
        data = call_ollama_json(prompt, temperature=0.4)
        emotions = data.get("scene_emotions", [])

        # Apply emotion data back to scenes
        emotion_map = {e["scene_id"]: e for e in emotions if isinstance(e, dict) and "scene_id" in e}
        enriched = []
        for i, scene in enumerate(scenes):
            scene_id = scene.get("id", i + 1)
            em = emotion_map.get(scene_id, {})
            enriched.append(dict(scene) | {
                "emotion": em.get("primary_emotion", "neutral"),
                "energy": em.get("energy_level", 5.0),
                "pacing": em.get("pacing_suggestion", "maintain"),
                "color_grade_suggestion": em.get("color_grade_suggestion", "natural"),
                "music_mood": em.get("music_mood_match", "neutral"),
            })

        return {
            "status": "completed",
            "agent": "Emotion Analysis Agent",
            "model": OLLAMA_MODEL,
            "scene_count": len(scenes),
            "emotions_detected": len(emotions),
            "scene_emotions": emotions,
            "enriched_scenes": enriched,
            "overall_arc": data.get("overall_arc", ""),
            "pacing_issues": data.get("pacing_issues", []),
            "engagement_prediction": data.get("engagement_prediction", "medium"),
            "best_scene_for_thumbnail": data.get("best_scene_for_thumbnail", 1),
        }
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Emotion Analysis Agent failed: {exc}") from exc


# ── Agent 28: Viral Clip Finder Agent ────────────────────────────────────────

@app.post("/api/v1/find-viral-clip")
def find_viral_clip(request: ViralClipRequest) -> dict[str, Any]:
    """Viral Clip Finder Agent: Identifies the most shareable moments in the video."""
    if not request.scenes:
        raise HTTPException(status_code=400, detail="No scenes provided.")

    total_duration = sum(
        (float(s.get("end", s.get("e", 0))) - float(s.get("start", s.get("s", 0))))
        for s in request.scenes
    )

    scenes_text = "\n".join(
        f"Scene {s.get('id', i+1)} [{s.get('start', s.get('s',0)):.1f}s-{s.get('end', s.get('e',0)):.1f}s]: \"{s.get('text','')[:150]}\""
        for i, s in enumerate(request.scenes[:10])
    )

    platform_formats = {
        "reels":    {"max_dur": 90, "ratio": "9:16", "style": "punchy, fast-paced"},
        "tiktok":   {"max_dur": 60, "ratio": "9:16", "style": "trend-following, hook in 1s"},
        "shorts":   {"max_dur": 60, "ratio": "9:16", "style": "educational, satisfying loop"},
        "linkedin": {"max_dur": 120, "ratio": "16:9 or 1:1", "style": "professional insight"},
    }
    fmt = platform_formats.get(request.platform, platform_formats["reels"])

    prompt = f"""You are the SmartEdit AI Viral Clip Finder Agent.
Identify the best shareable moments from this video for {request.platform}.

Platform specs: max {fmt['max_dur']}s, ratio {fmt['ratio']}, style: {fmt['style']}
Max clip duration: {request.clip_duration_max}s

Video scenes:
{scenes_text}

Return ONLY valid JSON:
{{
  "viral_clips": [
    {{
      "rank": 1,
      "scene_ids": [2, 3],
      "start_seconds": 12.0,
      "end_seconds": 37.0,
      "duration": 25.0,
      "virality_score": 9.1,
      "reason": "why this clip is shareable",
      "hook_moment": 13.5,
      "suggested_title": "short punchy clip title",
      "suggested_caption": "social media caption with hashtags"
    }}
  ],
  "best_clip_index": 0,
  "editing_suggestions": ["add captions", "speed ramp at 0:15", "zoom on face at 0:08"]
}}"""

    try:
        data = call_ollama_json(prompt, temperature=0.5)
        clips = data.get("viral_clips", [])

        # Build FFmpeg trim commands for each clip
        for clip in clips:
            s = clip.get("start_seconds", 0)
            e = clip.get("end_seconds", s + 30)
            clip["ffmpeg_command"] = (
                f"ffmpeg -i input.mp4 -ss {s:.2f} -to {e:.2f} "
                f"-vf \"scale=-2:1920,fps=30\" "
                f"-c:v libx264 -crf 20 -c:a aac "
                f"viral_clip_{clip.get('rank', 1)}.mp4"
            )

        return {
            "status": "completed",
            "agent": "Viral Clip Finder Agent",
            "model": OLLAMA_MODEL,
            "platform": request.platform,
            "total_video_duration": round(total_duration, 2),
            "clips_found": len(clips),
            "viral_clips": clips,
            "best_clip_index": data.get("best_clip_index", 0),
            "editing_suggestions": data.get("editing_suggestions", []),
        }
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Viral Clip Finder Agent failed: {exc}") from exc


# ── Agent 1: Orchestrator — run full pipeline ─────────────────────────────────

@app.post("/api/v1/orchestrate")
def orchestrate(request: ScriptGenerationRequest) -> dict[str, Any]:
    """Orchestrator Agent: Coordinates the full multi-agent pipeline from prompt."""
    log: list[dict[str, Any]] = []

    def log_step(agent: str, status: str, detail: str = "") -> None:
        log.append({"agent": agent, "status": status, "detail": detail, "timestamp": utc_now()})

    log_step("Orchestrator Agent", "started", f"Pipeline initiated for: {request.prompt[:60]}")

    # Step 1: Script Agent
    try:
        script = generate_script_with_ollama(request)
        log_step("Script Agent", "completed", f"{len(script['scenes'])} scenes generated")
        scenes = script["scenes"]
    except Exception as exc:
        log_step("Script Agent", "failed", str(exc))
        raise HTTPException(status_code=502, detail=f"Orchestrator: Script Agent failed — {exc}") from exc

    # Step 2: Layout Planner
    try:
        layout_req = LayoutPlanRequest(scenes=scenes, style="cinematic")
        layout_result = layout_plan(layout_req)
        scenes = layout_result["scenes"]
        log_step("Layout Planner Agent", "completed", f"Layouts assigned to {len(scenes)} scenes")
    except Exception as exc:
        log_step("Layout Planner Agent", "failed", str(exc))

    # Step 3: Image prompts for each scene
    image_prompts = []
    for scene in scenes[:3]:  # limit to first 3 for speed
        try:
            img_req = ImagePromptRequest(text=scene.get("text", ""), style="cinematic photorealistic")
            img_result = generate_image_prompt(img_req)
            image_prompts.append(img_result["result"])
        except Exception:
            pass
    log_step("Image Generator Agent", "completed", f"{len(image_prompts)} image prompts ready")

    # Step 4: Music selection
    try:
        music_req = MusicSelectionRequest(mood="cinematic" if "cinematic" in request.prompt.lower() else "neutral",
                                          duration_seconds=request.duration_seconds)
        music_result = select_music(music_req)
        log_step("Music/Sound Agent", "completed", f"Music profile: {music_result['mood']}")
    except Exception as exc:
        log_step("Music/Sound Agent", "failed", str(exc))
        music_result = {}

    log_step("Orchestrator Agent", "completed", f"Pipeline complete — {len(scenes)} scenes ready")

    return {
        "status": "completed",
        "agent": "Orchestrator Agent",
        "agents_run": [step["agent"] for step in log if step["status"] == "completed"],
        "pipeline_log": log,
        "script": script,
        "scenes": scenes,
        "image_prompts": image_prompts,
        "music": music_result,
    }


# ── Status endpoint ───────────────────────────────────────────────────────────

@app.get("/api/v1/agents-status")
def agents_status() -> dict[str, Any]:
    return {
        "status": "online",
        "total_agents": 16,
        "implemented_agents": [
            {"id": 1,  "name": "Orchestrator Agent",        "endpoint": "/api/v1/orchestrate",           "status": "active"},
            {"id": 2,  "name": "Script Agent",              "endpoint": "/api/v1/generate-script",       "status": "active", "requires": "Ollama"},
            {"id": 3,  "name": "Layout Planner Agent",      "endpoint": "/api/v1/layout-plan",           "status": "active", "requires": "Ollama"},
            {"id": 4,  "name": "Slide Generator Agent",     "endpoint": "/api/v1/generate-slides",       "status": "active", "requires": "Ollama"},
            {"id": 5,  "name": "Image Generator Agent",     "endpoint": "/api/v1/generate-image-prompt", "status": "active", "requires": "Ollama"},
            {"id": 6,  "name": "Avatar Generator Agent",    "endpoint": "/api/v1/generate-avatar-prompt","status": "active", "requires": "Ollama"},
            {"id": 7,  "name": "Voice Agent",               "endpoint": "/api/v1/synthesize-voice",      "status": "active" if GTTS_AVAILABLE else "needs_install", "requires": "gtts"},
            {"id": 8,  "name": "Lip-Sync Agent",            "endpoint": "/api/v1/lip-sync-info",         "status": "active"},
            {"id": 9,  "name": "Caption Agent (Whisper)",   "endpoint": "/api/v1/generate-video",        "status": "active", "requires": "faster-whisper"},
            {"id": 10, "name": "Compositor Agent",          "endpoint": "/api/v1/composite-video",       "status": "active" if ffmpeg_available() else "ffmpeg_missing"},
            {"id": 11, "name": "Multi-Language Agent",      "endpoint": "/api/v1/translate-script",      "status": "active" if DEEP_TRANSLATOR_AVAILABLE else "needs_install"},
            {"id": 12, "name": "Brand Kit Agent",           "endpoint": "/api/v1/apply-brand-kit",       "status": "active"},
            {"id": 13, "name": "Conversation Mode Agent",   "endpoint": "/api/v1/conversation-split",    "status": "active", "requires": "Ollama"},
            {"id": 14, "name": "Natural Language Edit Agent","endpoint": "/api/v1/nl-edit",              "status": "active", "requires": "Ollama"},
            {"id": 15, "name": "Music/Sound Agent",         "endpoint": "/api/v1/select-music",          "status": "active"},
            {"id": 16, "name": "Export Optimizer Agent",    "endpoint": "/api/v1/export-video",          "status": "active"},
        ],
        "runtime": {
            "ollama_url": OLLAMA_BASE_URL,
            "ollama_model": OLLAMA_MODEL,
            "whisper_model": WHISPER_MODEL,
            "ffmpeg_available": ffmpeg_available(),
            "gtts_available": GTTS_AVAILABLE,
            "deep_translator_available": DEEP_TRANSLATOR_AVAILABLE,
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
