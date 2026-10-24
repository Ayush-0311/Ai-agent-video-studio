# Faster generation

## Script planning update — 24 October 2026

The brief analyst, scriptwriter, shot director and narration–visual reviewer now
request direct structured JSON without Qwen's extended reasoning mode. Hindi
repairs use the same path. Scene IDs, language, narration meaning, timing and
visual relevance still pass the existing validators; invalid drafts have bounded
repair attempts. Topic references are still retrieved when requested.

After two different narration samples, the writer also reuses the measured words
per second for that exact language, voice and speech-rate setting. This helps
avoid writing a 14-second explanation for a 20-second target and then regenerating
the script and audio. Short/invalid samples are ignored; history is bounded and
expires after 30 days. The measured duration preflight still validates every
export and can request a rewrite when the new speech does not fit.

Ollama stays loaded for up to five idle minutes between adjacent planner calls.
The Colab bridge used to override every request with `keep_alive=0`, forcing the
runner to reload for the next stage. Image, OmniVoice, motion and presenter routes
explicitly unload Ollama under the shared GPU lock before allocating their own
models. No simultaneous GPU inference or automatic quality downgrade is added.

Both the desktop backend and the **updated Colab cell** are needed for model
reuse. A connected older cell can still force a reload even with the new desktop.
Production jobs now save worker start/finish times and timestamped events, so
queue waiting and time spent in each stage can be distinguished. The optional
`scripts/verify_planning_speed.py --render-hi` check runs real 20-second English
and Hindi planning, then a Hindi image-story export with captions. It records
results under `backend/studio-data/verification/planner-speed-2026-10-24` and
refuses to start alongside another production.

These changes reduce avoidable planning work. They do not remove the cost of
image generation, speech synthesis or Wan motion on a T4. An earlier balanced
motion trial reported **96.2 seconds for step 1 of 30**, estimating another
46.5 minutes for that shot; it was cancelled, so that is not a completed-render
measurement. Use the actual progress estimates for your selected mode and GPU.

### Verification on 24 October

Connected Tesla T4, Qwen3.5 9B, OmniVoice, 20-second target, high-quality images,
720p image-story export, research and captions enabled:

| Check | Script writing | Complete planning | Export after planning |
|---|---:|---:|---:|
| English | 31.55 s | 139.25 s | Not requested |
| Hindi | 33.47 s | 133.20 s | 399.93 s |

The Hindi MP4 decoded successfully at **1280×720, 30 fps, exactly 20.000 seconds**,
with audible audio and 11 caption cues within the video duration. The export
reported speech-word alignment. Four sampled frames showed the requested sunny
and cloudy solar-panel scenes with readable Hindi captions. This does not certify
every pronunciation or caption boundary. Initial speech was 14.51 seconds and
required one measured rewrite to 19.83 seconds before encoding. That extra round
motivated the new learned narration-pace budget.

A subsequent calibrated planning trial failed the director's structural checks
after two attempts (175.03 seconds). The final patch now constrains director and
review output to the actual scene IDs and count, retains validation/repair, and
includes the concrete validation reason in a failure. **The final calibration
and scene-ID changes still need another live run:** the saved tunnel returned
HTTP 404 when work resumed, and Colab was unavailable. Five-minute planner reuse
also needs the updated notebook; the measured runs used bridge version 10, which
did not report planner retention. No measured speedup factor is claimed.

Local verification: 229 backend tests, 88 Colab tests, 237 Electron UI checks,
syntax/runtime checks, plus 25 focused backend checks after the final schema
changes. Colab probe/notebook checks also passed after matching warmup context
size to normal planning. Live receipts, stage timestamps and inspection results
are under `backend/studio-data/verification/planner-speed-2026-10-24`; user media
and private service settings are not part of the source commit.

The desktop starts with a 20-second target and Hybrid mode. Hybrid generates **one motion opening** and animated images for the remaining scenes. Full AI motion remains available and never silently switches to still images.

## Choose a workflow

- **Draft video preview:** renders a separate 720p image-story MP4 using the planned scenes and narration. It does not run Wan or overwrite the final project. Generate video reuses the storyboard from Plan scenes or Draft video preview while its brief is unchanged. Changing only motion detail preserves reviewed scene edits and applies the new preset without another planning request.
- **Image story:** animated images throughout. No generated character movement.
- **Hybrid:** one motion opening, then animated images. Fewer motion jobs than full AI motion.
- **Full AI motion:** every unfilled scene generates a motion shot. More GPU work.

## Motion detail

| Preset | Steps | Frames / FPS | Landscape source | Purpose |
|---|---:|---:|---|---|
| Fast draft | 12 | 49 / 16 | 512 × 288 | Check composition/movement with less detail; roughly 3-second source stretched to the scene duration |
| Balanced | 30 | 81 / 16 | 640 × 352 | Reduce workload versus the previous 50-step, 832 × 480 T4 path |
| High detail | 50 | Model profile | 832 × 480 on T4; 1280 × 704 on supported larger GPUs | Highest workload of these presets |

Portrait and square buckets are provided. Exporting at 1080p resizes these sources; it does not create native 1080p detail. Fast draft is not a distilled model, and fewer steps can reduce image quality. None of these presets guarantees a particular generation time on free Colab.

## Activate the new Colab code once

1. Cancel any old render in SmartEdit and let Colab finish cancelling its current inference step.
2. Stop the old setup cell. Keep the current runtime disk/model cache; do not delete the runtime to apply this update.
3. Upload the complete updated `Colab_Ollama_Setup.py` through Colab's Files panel. Run `%run /content/Colab_Ollama_Setup.py` in a new code cell. Alternatively, upload `colab/SmartEdit_Colab.ipynb` and run its setup cell. Do not run the old setup cell afterward.
4. Confirm the output identifies **2026-10-24 / warm planner and direct structured generation**. Paste the new complete ONE-PASTE connection link into SmartEdit and Connect & Test. The desktop prevents an old bridge from silently ignoring your speed selection.

Startup no longer generates an unused motion test by default. Planner, image and voice checks remain. Motion is **untested** until an actual job succeeds; `SMARTEDIT_TEST_MOTION=1` opts into startup motion testing.

## What changed inside the pipeline

For full-motion storyboards, the first motion request prepares the remaining shot prompts while the text encoder is loaded. Later shots reuse those embeddings and the loaded video pipeline. Image generation or language-model work unloads the video pipeline before using shared GPU memory. Downloads remain serial. Cancellation/failure drops the loaded motion pipeline; no new large model or parallel GPU inference was introduced.

Every motion step reports its measured time, estimated time remaining **in that shot**, and peak PyTorch GPU allocation. Desktop progress advances with the actual step count. These estimates exclude subsequent shots and final encoding and can change as steps complete. Cached source files are separated by preset so a draft is not reused as a high-detail result.

## Verification and limits

- 127 backend checks, including a real 20-second Hybrid MP4 render with fixture media replacing the external AI boundaries.
- 206 Electron UI checks plus four screen sizes: preset wiring, separate image preview, storyboard reuse after Plan scenes and detail changes, changed-brief invalidation, responsive controls and existing editing operations.
- 41 Colab offline checks: execute the actual motion function with fake GPU boundaries to verify encoder/pipeline reuse, preset arguments, progress and cancellation; also validate setup, dependency configuration and notebook synchronization.
- Real editing/export/download regression checks run separately with FFmpeg and the reference video.

Offline checks do not measure GPU quality or speed. A live T4 benchmark on 10 October measured Balanced steps at 96.7 and 78.2 seconds; the user chose to stop that trial and test Fast draft. Draft steps settled around 21 seconds, but the first shot showed visible banding and failed visual review. See LIVE_QUALITY_REPORT_2026-10-10.md for completed sample timings and remaining limitations. A successfully encoded MP4 is not a quality guarantee.
