# SmartEdit: original UI, real video exports

**Current Colab setup:** use [COLAB_SETUP_GUIDE.md](COLAB_SETUP_GUIDE.md) for the hardware-selected Qwen/SDXL/FLUX/Wan profiles and default full motion startup test. It supersedes the older fixed-model and first-job-only testing notes below. Both Python entry points and the uploadable notebook are synchronized. Offline setup checks pass; live GPU quality remains to be verified in your Colab runtime.

The existing landing page, dashboard, editor, timeline and 28-agent screen remain the default. The separate UI redesign was removed. `main.js` still opens `index.html`. A final script, `frontend/api/studio-integration.js`, connects those original controls to the production backend.

## Uploaded-video editor update

See **VIDEO_EDITOR_GUIDE.md** for the uploaded-footage workflow. `frontend/api/timeline-editor.js` now drives source-timeline playback, selectable/reorderable video clips, edge trimming, clip properties, project undo/redo, extra media and music, and edited-file downloads. Source editing/export needs no Colab connection. The reference-avatar test exercised the actual upload UI, Chromium playback, backend rendering and native download, producing a separate 5.5-second portrait MP4. Browser color is approximate; noise reduction and music ducking are final-export effects.

## Prompt to cinematic motion (September 30 update)

The generator now defaults to **AI motion · Free Colab GPU**, with a 10-second target. Enter a topic in Hindi or English, choose Cinematic realism / 3D animation / Anime / Documentary / Product showcase, and choose whether to add narration and subtitles. The director writes topic-specific short shots with subject action, camera movement, lighting, and repeated character descriptions. Selecting **Image story** retains the SDXL pan/zoom workflow. Old saved projects keep their image-generation behavior.

**Run the updated `colab/SmartEdit_Colab.ipynb` in a fresh T4 GPU session and reconnect with its new ONE-PASTE link. Restart the local backend after any existing jobs finish to load this update.** The older bridge cannot generate motion and the app reports that explicitly. Start with 10 seconds (two shots); the motion target is capped at 60 seconds because each shot can take many minutes on free Colab. There is no paid video API.

The model is [Wan 2.1 T2V 1.3B](https://huggingface.co/Wan-AI/Wan2.1-T2V-1.3B-Diffusers), integrated using [Diffusers WanPipeline](https://huggingface.co/docs/diffusers/api/pipelines/wan). Generated shots contain 81 frames at 16 fps, with 832×480 landscape, 480×832 portrait or 624×624 square sources. The final 1080p export resizes this source; it does not create native 1080p detail. Reference-level cinematic quality, identical characters between shots, and precise lip-sync are not guaranteed. Wan supplies visuals only. Optional neural narration and uploaded music are added by the existing compositor.

The bridge requires at least 14 GiB GPU memory and 11 GiB system RAM to advertise motion. It unloads Ollama and SDXL, loads an 8-bit UMT5 encoder on the GPU, saves prompt embeddings, releases the encoder, then loads the video transformer. Native BF16 is used on supported GPUs; T4 uses FP32 to avoid FP16 overflow. Model CPU offload and tiled VAE decoding reduce memory pressure, but a successful live runtime inference is still required. The first motion request downloads the weights; sufficient Colab disk space and session time are needed.

GPU jobs run in the background and the PC polls short authenticated requests. Status includes model loading and denoising steps. Cancellation is checked between stages and denoising steps. Requests use idempotent IDs; corrupt responses are not cached. Failed motion jobs stop without switching to still images. Generated clips are cached and a single shot is retimed to fit its scene/narration, without looping; excessively long narration is rejected. Health distinguishes **available** from **inference tested**: motion remains untested until a job actually produces nonblank frames and an encoded clip. The PC then decodes the clip before caching it.

Validation for this update: **20 backend integration tests**, **9 Colab configuration/queue tests**, and **28 Electron UI checks** passed. Backend media tests use actual FFmpeg encoding/decoding with fixture video and mocked external AI. They cover motion mode, silent shots, measured narration, cache reuse, provider errors, cancellation, polling and corrupt downloads, alongside the existing editing/export tests. The UI checks include Generate → storyboard → render → download with isolated HTTP fixtures, and rejection of an older bridge. **No live Colab GPU inference or reference-quality comparison has been completed.** Offline tests do not establish model quality or free-T4 memory fit.

Run Colab checks with `backend/.venv/Scripts/python.exe -m unittest discover -s colab -p "test_colab*.py" -v`. After editing the Colab source, run `backend/.venv/Scripts/python.exe scripts/sync_colab_notebook.py` to update the uploadable notebook and compatibility copy.

## Start

After updating the project, rerun the first-time SETUP batch file once. It installs current requirements and verifies Electron, backend imports, FFmpeg and FFprobe. LAUNCH uses `scripts/desktop.ps1` to check the installation, start the backend hidden with logs, verify this project's local health endpoint, and open the original Electron app. Repeated launches reuse the same backend. STOP verifies the project directory and process command before stopping its backend. It does not stop arbitrary port-8000 listeners. Startup logs are under `backend/studio-data/launcher`. The preflight check does not import/start the backend application or alter running job statuses.

Desktop lifecycle verification: installation check passed, the real backend started, a second launch reused its PID, and the verified Stop action shut it down. Setup dependency downloads were not repeated because this machine already has the dependencies installed.

1. Use the existing `🚀 2. LAUNCH SmartEdit.bat` in this folder.
2. In Google Colab, select a **GPU runtime**. Upload and run `colab/SmartEdit_Colab.ipynb`, or paste `colab/SmartEdit_Colab.py` into a cell.
3. Set `NGROK_AUTHTOKEN` in Colab Secrets and grant the notebook access. The script can also ask for this token using a hidden input. Do not paste it into source code.
4. Keep the Colab cell running. It downloads the models and actually tests language inference, Hindi/English speech and an SDXL image before printing **SMARTEDIT CONNECTION READY**.
5. Copy the complete **ONE-PASTE CONNECTION LINK** into the existing Colab URL box in SmartEdit and click **Connect & Test**. The fragment carries the model and temporary token; the app extracts them and configures image/voice URLs automatically. Keep this link private. Manual URL/token fields still work in Settings.
6. Create a script/storyboard or use **Generate video**. The final download is an actual MP4. For uploaded footage, use **Open in Editor**, make edits, then **Export**.

The previous URL supplied during development returned HTTP 404 at `/api/tags`, `/api/version` and `/health`. Live Colab inference has therefore not been verified. A new working session is required; local renderer tests do not establish remote model quality.

## Models

- Default language model: **Qwen3.5 9B**, selected as a practical fit for constrained Colab GPU memory, not claimed to be the universally best model. Its Ollama distribution is approximately 6.6 GB. [Official model](https://ollama.com/library/qwen3.5:9b).
- Hardware selection: 14+ GiB GPU memory and 11+ GiB system RAM select 9B (including a typical free T4 runtime). Smaller supported runtimes select **Qwen3.5 4B**, a 4096-token context and sequential image CPU offloading below 14 GiB VRAM. Below 7 GiB VRAM or 10 GiB RAM, setup stops with a clear message. These conservative total-memory checks are not a guarantee of currently free memory; startup inference must still pass. Advanced users can set `SMARTEDIT_COLAB_MODEL` to `qwen3.5:4b` before running the cell. Larger GPUs retain 9B rather than automatically downloading a much larger model.
- Image inference uses FP16 on T4; no BF16-only image model or extra GPU speech model is required. Startup now generates a production-size 1344×768 image to check memory usage. This uses 8 test steps; actual High-quality production uses 40. `/health` exposes the chosen model, context and offload profile. Agent context requests are capped to the selected memory budget.
- Image generation: **SDXL base 1.0**, producing real PNG assets. It uses CPU offloading on limited GPU memory. [Official model and usage](https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0).
- The bridge serializes inference and unloads Ollama before SDXL; it releases SDXL before the next language-model request. Both endpoints require the temporary bridge token.
- No paid image API is configured. Colab availability and runtime limits still apply. First downloads take time.
- Voice: Edge neural TTS through the same authenticated Colab bridge, including Hindi Madhur/Swara and English Christopher/Jenny. This calls Microsoft's online speech service; it is not an offline GPU voice model. Male/female choice and speech rate are available in the existing Settings screen, along with **Hear voice sample**. [Library documentation](https://github.com/rany2/edge-tts).
- Hindi is why this setup does not switch speech to Qwen3-TTS: its official CustomVoice language list does not include Hindi. [Official language support](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice). Voice quality and pronunciation should be reviewed with the existing preview button before rendering a long project.
- High image detail: 1344×768 landscape, 768×1344 portrait, or 1024×1024 square; 40 steps with DPM-Solver++/Karras. Balanced mode uses smaller images and 28 steps. Higher settings are a quality-oriented configuration, not a guarantee of better output for every prompt. [Scheduler documentation](https://huggingface.co/docs/diffusers/api/schedulers/multistep_dpm_solver).
- New projects default to 1080p output, H.264 CRF 18 with the medium preset. Source audio keeps its original level multiplied by the clip volume, with peak limiting; final AAC audio uses 48 kHz / 192 kbps. Export resolution is separate from native generated-image detail; this does not manufacture native 4K source detail.
- **Image story** turns images into pan/zoom scenes with narration. **AI motion** generates video shots with Wan as described above. Talking-avatar/lip-sync output is not integrated; its control is disabled and labeled.

## What works in the production path

- Prompt → validated scenes with narration and English image descriptions → actual generated images and TTS → encoded scenes → actual downloadable MP4.
- Image caching and voice caching; provider failures stop the job instead of substituting black frames or silent narration.
- Voice cache keys include narrator, language and rate. Image cache keys include the quality profile, so changed settings cannot accidentally reuse the previous profile's assets.
- Voice duration is measured with FFprobe. Final timeline and caption timing use encoded scene duration, not the requested estimate.
- Source-video trimming, splitting, duplication/deletion, speed and mute are carried into export. Splits preserve source-time ranges separately from output timeline time.
- Repeated speed changes no longer divide an already modified duration incorrectly. Selection also updates the target scene used by agents.
- Whisper transcription of uploaded video; optional removal of speech gaps via the Jump Cut agent. Multilingual `base` replaces English-only `tiny.en` as the default.
- 16:9, 9:16 and square export; 720p/1080p; H.264/AAC MP4; burned-in captions, watermark, color treatment, source-audio denoising.
- Uploaded background music is mixed into the actual file and ducked under speech. The app does not pretend a music recommendation is a downloaded/licensed track.
- Actual image generation on the selected scene from the Image Generator card.
- Editorial review: narration optimization plus hook/emotion/SEO/thumbnail/B-roll advice. Advice remains reviewable and is included in the production report.
- Saved projects, job results and downloads survive restarting the app. The dashboard has a compact **Saved projects & completed videos** section. Restarted unfinished jobs report failure rather than remaining indefinitely “running.”
- Export provides MP4, SRT and JSON production metadata. SRT phrase timing is estimated within measured scene speech, not word-level forced alignment.
- Electron keeps Node access disabled in the renderer. AI result dialogs use text nodes. Native unsupported `window.prompt` dialogs were replaced with in-app dialogs using the existing visual style.

## Agent capability boundaries

All 28 cards remain. Their status badges describe capability rather than falsely claiming every external provider is online. Production stages run when relevant; there is no requirement to run 28 unrelated models for every video.

Avatar prompts, lip-sync timing, conversation layouts, slide content and some analytics remain legacy helpers. The generator's character preference now contributes to the visual style, but does not create a speech-synchronized presenter. AI motion can generate character motion; the separate legacy cards do not become motion providers. Review the capability labels and the actual downloaded video. Advanced legacy layout advice is not a full presentation compositor.

## Validation

Backend tests use **real FFmpeg/FFprobe**, synthetic media, and fake external AI responses only where explicitly needed. They cover playable exports, dimensions, duration, source trim/speed, music/captions, image/voice timing, muted scenes, invalid uploads, persistent projects, cancellation, failure handling, short speech, jump-cut duration and editorial response validation.

```powershell
backend\.venv\Scripts\python.exe -m unittest discover -s backend -p test_studio.py -v
backend\.venv\Scripts\python.exe -m unittest discover -s colab -p test_colab_setup.py -v
```

The Electron smoke test loads the **original index.html** and tests agent-screen uniqueness, 28 cards, selected-scene targeting, source-preserving split, repeated speed changes, ripple delete, undo, mute payloads and Settings. It writes results under the ignored `backend/studio-data/verification` directory.

Current checks: 20 backend tests, 9 Colab configuration/queue tests and 28 editor/connection/generation checks. The Colab checks cover memory policy, unsupported resources, context limits, notebook/source agreement, job idempotency, bounded results, failure and cancellation. An earlier real 13.944-second Hindi neural speech sample was generated and decoded locally. That verifies the speech provider from this PC; the updated GPU bridge still needs an actual Colab runtime test.

```powershell
node_modules\electron\dist\electron.exe tests\ui-smoke.cjs
```

Runtime files and connection secrets are stored under ignored `backend/studio-data`. Do not publish that folder. The backend binds to `127.0.0.1`; keep it local. Install test-only `httpx` if your fresh venv does not already include it.

Editing the timeline switches the player from the last completed export to the edited source sequence. Trimmed source time, clip ordering, speed, mute, crop and mirror are reflected in preview. Export encodes the final file and restores its download link; new edits invalidate that link. Color preview is approximate, and denoising/music ducking require export. Cancellation is checked between blocking service/encoding operations, so the current operation can finish before cancellation takes effect.
