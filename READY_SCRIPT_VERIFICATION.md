# Ready-script verification — 2026-10-21

## Completed checks

| Check | Result |
|---|---|
| Studio integration, parser/music, production agents, timing, brief interpretation and research | 107 tests passed |
| Narration, speech timing and specialist regression | 29 tests passed |
| Colab setup/runtime/routes including reference-image PNG decoding | 63 tests passed |
| Frontend smoke | 237 checks passed |
| Editor/save/reload audit | 59 checks passed |
| Presenter UI | 14 checks passed |
| Layout audit | 18 screens and 57 dropdown checks passed |
| Static audit | Python/JavaScript syntax passed |
| Running backend | API 17; loaded source fingerprint matches disk |

The 60-second deterministic export test uses real FFmpeg with fixture images and the local
instrumental composer. It verified 1,800 video frames, 720×1280 dimensions, audible music,
visible screen-text pixels, final fade to black, and overlay timestamps independent of subtitles.
It does not use generated GPU imagery or real Hindi narration.

The supplied eight-scene Hindi script was parsed without rewriting its dialogue. Additional tests
cover 10, 40, 65, 120 and 180-second timelines, invalid timestamps, quoted label words, silent
visual scenes, oversized voice errors before new images, motion slot limits, reference routing
only to matching scenes, and cache reuse.

## Live status and next step

At the final live check, planner/image/voice/motion services were all unavailable. The desktop
backend was available and current. Actual connected generation, IP-Adapter weight downloads,
GPU memory use, visual identity and real Hindi voice quality remain unverified.

Save editor changes, reopen SmartEdit, upload the updated `colab/SmartEdit_Colab.ipynb`, run
its setup cell and reconnect. Review a draft before a full motion render. Ready scripts preserve
their supplied dialogue; overlong dialogue still needs shorter words or a longer explicit slot.

## Evidence

- `backend/studio-data/verification/ready-script-backend-tests.log`
- `backend/studio-data/verification/ready-script-voice-regression.log`
- `backend/studio-data/verification/check-colab.log`
- `backend/studio-data/verification/ui-result.json`
- `backend/studio-data/verification/audit-fixes-result.json`
- `backend/studio-data/verification/presenter-ui-result.json`
- `backend/studio-data/verification/layout-audit-result.json`

Pillow 12.3.0 was installed into the project virtual environment for real reference-image decoding
tests. No paid API key was added. New model weights load in the connected Colab runtime on demand.
