# Faster generation

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
4. Confirm the output identifies **2026-10-03 / motion-speed-presets**. Paste the new complete ONE-PASTE connection link into SmartEdit and Connect & Test. The desktop prevents an old bridge from silently ignoring your speed selection.

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
