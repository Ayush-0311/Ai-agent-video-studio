# SmartEdit setup and generation performance

## Applying this update

1. Let any active export finish. Run `🔧 1. SETUP (First Time Run).bat`.
2. Setup installs missing Python/Node using Windows Package Manager, reuses the
   Python environment, installs app dependencies, and prepares the selected local
   Whisper model. Missing FFmpeg/FFprobe downloads into `.runtime` with SHA256
   verification and retry/resume. Windows Nirmala UI is checked for Hindi text.
   Windows App Installer (winget), Internet access and any installer elevation
   required by Windows must be available. A missing prerequisite produces a
   specific failure, never a false success.
3. Launch SmartEdit after setup. The launcher updates an idle old backend; it
   refuses to interrupt active or queued jobs. Production API is now 19.
4. Upload the updated `colab/SmartEdit_Colab.ipynb`, stop the previous setup cell,
   and run the new complete cell on a GPU. Paste its new private connection link.
   Local edits cannot update an already running remote notebook automatically.

## Changes

### Image to motion update (2026-10-22)

- The notebook's `MOTION_ENGINE` dropdown defaults to `auto`, selecting compatible
  Wan motion (Wan2.1 on T4). The optional `ltx-13b` selection uses
  **Lightricks LTX-Video 0.9.8 13B Distilled**. It consumes the actual generated
  scene image from FLUX.2 Klein 4B / SDXL. `auto`, `wan2.1`, and `wan2.2`
  use text-to-motion engines.
- This BF16 implementation uses model CPU offload and conservatively requires
  native BF16, **38 GiB VRAM and 48 GiB RAM** (A100-class Colab). This is an
  application guard, not a measured minimum. On unsupported hardware the image
  and voice services can start, but LTX motion stays unavailable with a clear
  reason and its weights are not downloaded. No silent engine substitution.
- All scene images are prepared before motion, including Hybrid's later stills.
  Character references guide those images when enabled. LTX receives them as
  frame-zero conditions. Appearance across shots is still not guaranteed.
- LTX keeps the official seven-step single-pass distilled schedule. Fast draft:
  512x288 / 97 frames; Balanced: 832x480 / 161 frames; High detail: 1216x704 /
  161 frames. All use 30 fps; portrait and square sizes adapt. Export to 1080p
  resizes these sources. The optional multi-scale latent upsampler is not included.
- Motion cache keys include the exact source-image content hash. The UI shows
  the connected engine, actual preset sizes/steps and unavailable reason.
- OmniVoice remains the narrator; subtitles, selected duration and final FFmpeg
  assembly use the existing production path. MuseTalk remains separate.
- Model files are downloaded by Colab setup, not onto this PC. First downloads
  are large. No paid generation API key is required; Colab GPU availability and
  pricing are separate. Live LTX speed/quality has not been verified here.

References: [LTX model card](https://huggingface.co/Lightricks/LTX-Video-0.9.8-13B-distilled),
[official distilled config](https://github.com/Lightricks/LTX-Video/blob/main/configs/ltxv-13b-0.9.8-distilled.yaml),
[pinned Diffusers implementation](https://github.com/huggingface/diffusers/blob/v0.37.1/src/diffusers/pipelines/ltx/pipeline_ltx_condition.py).

### Setup and reuse improvements

- OmniVoice remains the default. Its isolated worker loads weights once for
  consecutive narration requests. It stops before planner/image/motion/presenter
  work, on a generation failure/timeout, and after five idle minutes. Narrator
  references and 32 inference steps are preserved; there is no silent voice swap.
- The planner remains loaded for adjacent requests for up to five minutes.
  Visual and voice routes explicitly unload it before allocating other models.
- Colab caches resolved model snapshots for the session. Default full verification
  downloads motion weights for a real Fast draft sample; disabling that checkbox
  defers the download to first use. Completed Hub files are
  reusable while the runtime cache survives; deleting the runtime loses its disk.
- Wan2.1 text-encoder FP32 shards convert serially to BF16 storage in an owned
  directory. The converter deletes only its own verified source shard after
  publishing the compact file. It preserves an 8 GiB working reserve and resumes
  completed shards. This roughly halves encoder disk storage, not network traffic
  or generation time. Runtime T4 INT8 encoder / FP32 motion settings remain.
- Talking-avatar installation and actual motion/avatar startup checks are enabled
  by default. Each check reports its result separately; inspect the saved samples.
- SDXL encodes a character reference before loading its image pipeline, releases
  the CLIP encoder, and caches only its small CPU embedding. This avoids loading
  both large models into the T4 runtime's system RAM together.
- Updated bridge health exposes model/weight/pipeline identities. Compatible
  local cached images, motion and speech survive a tunnel URL change. A new voice
  installation gets a distinct narrator identity. Older bridges use address-based
  isolation. Old cache files remain intact; new keys can require one regeneration.
- Motion and presenter downloads stream into a temporary file, retry interrupted
  transfers up to three times, and resume ranges against the same immutable job.
  Clips still pass the existing decode/duration checks before publication.
- Production jobs record queued/started/finished times and timestamp their events.
  Waiting jobs are labelled queued rather than running.
- Release file patterns exclude user media, model caches, settings/tokens and
  local runtime downloads. This is not a completed standalone installer release.

## Quality and remaining limits

Existing image quality, selected motion preset, duration fitting, subtitles and
export checks remain in effect. No low-resolution preset is silently selected.
Existing GPU profiles remain Qwen3.5 4B/9B/27B, SDXL/FLUX.2 Klein 4B,
Wan2.1 1.3B/Wan2.2 5B, OmniVoice and optional MuseTalk. LTX 13B is now integrated
as described above; its weights still require the updated Colab setup. Larger
FLUX.2 dev and Wan A14B are not integrated or advertised as verified.

These changes remove repeated loading/downloading and improve transfer recovery.
LTX uses a different distilled computation path from Wan. Actual speed,
voice naturalness, character consistency and GPU compatibility need a connected
production run. No claim that generation is instant or error-free is made.

The notebook and duplicate Python setup are generated by
`scripts/sync_colab_notebook.py`; edit the canonical sources and rerun it together.

## Checks performed for this change

The later full audit is recorded in [SETUP_AUDIT.md](SETUP_AUDIT.md). Backend,
Colab, UI, launcher and setup checks passed there; the saved bridge returned
HTTP 404 and needs a new connection before live GPU verification.

Initial implementation checks:

- Python compilation, PowerShell setup parsing, JavaScript syntax and Git
  whitespace checks passed.
- The existing desktop installation check passed (dependencies, FFmpeg,
  FFprobe and required files).
- The selected local multilingual Whisper base model was found/prepared.
- Selected settings were bridge narration and high image quality.
- The configured remote bridge could not be reached from this environment;
  no live GPU generation or speed comparison was performed.
- A clean Windows first-install run and automated regression suites were not run.
