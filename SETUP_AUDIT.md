# Setup audit — 2026-10-22

## Result

Local installation and offline integration checks passed after updating the
setup instructions and regression fixtures. Live Colab inference remains
unverified: the saved bridge URL returned HTTP 404 on a read-only check outside
the sandbox. Upload the updated complete notebook and reconnect with its new
private connection link before production.

## Changes made during this audit

- Windows setup calls a Python script to locate FFmpeg, avoiding embedded
  `python -c` quoting problems in Windows PowerShell 5.1. The installed FFmpeg
  and FFprobe were successfully discovered and reused by that exact setup code.
- Setup prefers the existing environment, then the known Python 3.11 install.
  A broken existing environment now produces an actionable error instead of
  continuing with the unusable interpreter. User projects/media are untouched.
- Both setup entry points now explain that LTX 13B needs an A100-class runtime
  in this implementation: native BF16, 38 GiB VRAM and 48 GiB RAM. On T4 select
  Wan explicitly. The Colab startup banner now identifies the current build.
- Added coverage for LTX image input, resource guards, all preset/aspect sizes,
  distilled parameters, model reuse, and invalid/missing image rejection.
- A real FFmpeg render regression checks that all Hybrid images precede LTX
  motion, unchanged images reuse motion, and changed image bytes invalidate it.
- Added worker reuse/shutdown and HTTP resume/ETag/cache isolation checks.
  Existing tests were updated for streamed responses, the persistent voice
  worker, earlier motion health checks and desktop API 19. The avatar render
  fixture now supplies a duration-appropriate audio file instead of claiming a
  two-second tone fills twenty seconds.

## Evidence

| Check | Result |
|---|---|
| Python / JavaScript static checks | Passed |
| Backend suite, including real FFmpeg exports | 201 passed |
| Additional transfer/cache tests | 6 passed |
| Colab offline suite | 70 passed |
| Desktop dependencies / FFmpeg / FFprobe | Passed |
| Installed Python dependency consistency (`pip check`) | Passed |
| Cached multilingual Whisper base: actual CPU model load | Passed |
| Native PowerShell setup parsing and existing tool reuse | Passed |
| Launcher regression checks | Passed |
| Electron UI, presenter UI, generation recovery | Passed |
| Saved Colab bridge health | HTTP 404; live GPU check unavailable |

Logs and UI result artifacts are in `backend/studio-data/verification/`:
`check-backend.log`, `check-colab.log`, `check-transfer-cache.log`,
`check-ui.log`, `check-presenter.log`, `check-recovery.log`.

## UI clarity follow-up — 2026-10-22

- Image stories hide motion-only controls; unavailable motion has a visible warning and does not show an all-ready connection for motion modes.
- Connected LTX preset dimensions follow portrait, landscape and square selection. Disconnected/unavailable engines use neutral preset labels.
- Switching to a shorter supported duration explains the adjustment. Timestamped scripts show their own duration, lock ignored timing controls, and unlock when timestamps are removed.
- Timing guidance follows Exact target, Natural pace and voice-off selections. The creation guide now distinguishes their duration behavior.
- Failed progress shows `Stopped`, keeps the last progress amount, prevents status wrapping, and hides cancellation when no job remains active. The modal scrolls in short windows.
- Verification: static checks, 256 UI assertions, presenter UI, generation recovery and layout audit passed. Screenshots reviewed at desktop and narrow widths. UI service responses are fixtures; these checks do not establish live GPU generation quality or speed.

## Live verification limits

This audit did not perform a fresh Windows install on an empty machine, download
LTX weights onto a GPU, or generate/listen to a real LTX/OmniVoice production
video. GPU memory, runtime availability, downloads and perceptual quality still
need the connected production run. Passing mocked GPU boundary tests establishes
wiring and error handling, not model quality or generation speed. No promise of
error-free operation or universal best quality is made.

## Follow-up — 2026-10-23: real demo and Colab crash recovery

- A real original-script demo completed: job `2dc8e001371b4857ba466753ecc20f84`,
  60.0 seconds, 1080x1920, eight AI-image scenes, audio and speech-word captions.
  FFprobe and a full FFmpeg decode passed. This is the backup cut, not the final
  fuller-narration revision; the original short lines leave noticeable gaps.
- The next reference-image request returned HTTP 503. Colab subsequently reported
  “session crashed after using all available RAM”; its UI showed 111.5/112.6 GB disk
  used, and the saved tunnel went offline. The user confirmed resetting the runtime.
- SDXL reference encoding now runs before SDXL loads, releases CLIP, and retains
  only the pooled CPU embedding. Adapter files download serially as safetensors.
  Route/cache/ordering/error tests use mocked GPU boundaries, not live inference.
- Motion downloads are deferred to first use; optional setup prefetch is explicit.
  Pip/OmniVoice installer caches are disabled. Normal setup omits LTX from its
  dropdown; MuseTalk is unchecked by default and remains available as an opt-in.
  Legacy LTX implementation remains for advanced existing configurations.
- Image failures now retain the safe bridge diagnostic rather than only HTTP 503.
  The final-demo helper requires the updated bridge before retrying references.
- Verification this follow-up: 73 Colab tests and 85 studio/production-agent tests
  passed; `git diff --check` passed. The standalone notebook was synchronized and
  syntax-checked by its generator.
- Remaining: run the updated notebook, reconnect SmartEdit, generate the eight
  reference-conditioned images and expanded OmniVoice narration, measure timing,
  export and review the fuller 60-second cut. Windows automation reported capture
  timeouts and then minimized-window/user-input conflicts, so the updated setup
  has not been run remotely by the assistant. No live memory or speed improvement
  is claimed yet.

## Complete T4 setup follow-up — 2026-10-23

- User supplied fresh-runtime capacity: 12.7 GB system RAM, 15 GB GPU memory,
  42.3/112.6 GB disk used (about 70 GB free). All four capabilities are retained.
- Added resumable Wan encoder compaction from the official Diffusers checkpoint:
  FP32 source shards download/convert to BF16 storage one at a time. An 8 GiB
  working reserve is checked; only owned staging files are removed after compact
  output publication. Transformer weights and T4 compute modes are unchanged.
  Network transfer remains the original size; first setup includes conversion.
- MuseTalk installation is enabled again, as requested. Its installer now also
  disables redundant pip/uv caches and accelerated parallel Hub downloads.
- Default extended setup checks invoke production image, motion and presenter
  callbacks, save a Fast draft motion sample and a five-second lip-sync sample,
  and record independent success/failure in `smartedit-feature-checks.json`.
- Local verification: 79 Colab tests plus 4 feature-check tests passed (83 total).
  Six compaction tests include real tensor conversion and a real tiny Transformers
  UMT5 encoder checkpoint reload/inference, disk reserve, failure and resume cases.
  Full-size Wan/BNB inference, total installed disk usage and actual T4 perceptual
  results remain unverified until the new notebook runs.
- User chose to upload the updated notebook themselves. Local Python source,
  uploadable notebook and root standalone setup file are synchronized.
