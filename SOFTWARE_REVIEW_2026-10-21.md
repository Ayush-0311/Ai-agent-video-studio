# SmartEdit software review — 21 October 2026

## Assessment

The local editor and deterministic generation pipeline have working implementations and passing checks.
The application still needs performance and recovery work before unattended long AI video production
can be considered dependable. Real connected image, voice, motion and character-reference quality
cannot be confirmed from local tests.

This review inspected production orchestration, narration, visual generation, editor integration,
job persistence, research, specialist actions, caching, storage and desktop packaging. It did not
install another model or change application behavior.

## Findings in priority order

### 1. Model residency and voice batching need improvement — high

`backend/studio.py:253` sends `keep_alive: 0` for every planner request, and the Colab chat
route also enforces it. Consecutive brief/writer/director/reviewer calls therefore cannot retain
the language model between requests. `colab/omnivoice_support.py:101` launches a new speech
worker for each uncached scene; that worker loads the model at line 128.

Keep the planner resident during the planning phase, release it explicitly before GPU visual/voice
work, and process a project's narration through a bounded batch/worker. Preserve cancellation,
GPU memory limits and measured speech timing. Do not run all GPU models concurrently by default.

The previously inspected 60-second full-motion job had twelve shots and observed roughly
81 seconds per step at 30 steps per shot. A faster compatible distilled motion model should be
benchmarked separately; FastWan/LTX alternatives have been researched but are not integrated.

### 2. Reconnecting Colab can invalidate reusable local assets — high

`backend/studio.py:1001` includes `settings().image_url` in generated image/motion cache keys.
The character-reference key also contains the URL (`studio.py:965`).
`backend/narration.py:50` includes the same URL in bridge voice cache identity.

Changing only the tunnel URL therefore changes cache keys even when the model, content and
generation parameters are identical. Use a stable provider/model revision and parameter identity,
including required model/adapter changes, instead of the temporary tunnel address.

### 3. Interrupted jobs have recovery, but not durable stage resume — high

`backend/studio.py:1451` marks running jobs failed after a backend restart. Saved projects and assets
remain, and the UI can reconnect to a still-running job, but there is no persisted stage/scene
execution cursor that resumes an interrupted pipeline automatically.

The frontend's failed `watch()` throws before loading a server-side partially planned project
(`frontend/api/studio-integration.js:267`). A user can open the saved project manually, but starting
again from the generation form can plan a new project.

Add an explicit resume/retry-failed-stage action tied to the saved job/project. Persist validated
storyboards, voice results, scene completion and model identities, then reuse only compatible work.

### 4. Timing/progress and cancellation need better feedback — medium

`backend/studio.py:295` records events without timestamps, and queued work is initially marked
running (`studio.py:327`) despite a single-worker executor. Consequently, persisted logs cannot
provide precise per-stage elapsed times or distinguish waiting from active execution.

Images and voice use synchronous requests with 900/1200-second timeouts
(`studio.py:683`, `studio.py:701`). Cancellation marks a flag and waits for the current blocking
operation to return; unlike motion jobs, these endpoints have no remote job cancellation handle.

Record queued/started/completed timestamps and stage durations, display an evidence-based estimate,
and use cancellable job endpoints for long voice/image work.

### 5. Output quality checks are mostly structural — medium

The visual reviewer checks narration against image prompts, not generated pixels.
Image/motion checks detect decoding failures and blank outputs, but do not reliably catch wrong
subjects, changed faces, distorted hands or poor movement. Exact duration and an audible stream
also do not establish natural Hindi delivery or correct pronunciation.

Add a reviewable first-shot sample and optional generated-output checks, with scene-specific
regeneration. Character-reference quality needs a real connected test.

### 6. Research and specialist scope are narrower than a fully automatic studio — medium

`backend/explainer_research.py` retrieves bounded Wikipedia introductory extracts. It does not
perform broad internet research or independently check every factual claim. When lookup fails,
the pipeline explicitly continues with a general explanation.

Several entries in `backend/production_agents.py:SPECIALISTS` intentionally return recommendations:
thumbnail design, B-roll, SEO, emotional pacing and two-speaker conversation briefs. They do not
automatically create every suggested asset or synthesize separate dialogue voices.

Keep those capability labels clear. For factual explainers, add stronger reference selection and
claim/source review where needed. For a complete studio workflow, connect useful specialist
recommendations to explicit media-generation actions.

### 7. Installer packaging needs a separate release pass — high before distribution

`package.json` includes `**/*` with only a dist exclusion. There is no explicit exclusion of
`backend/studio-data`, which currently includes saved media, models and a nonempty bridge-token
setting. No token value was printed during this review.

`main.js` launches a PowerShell script under `__dirname`; that script assumes an adjacent
`backend/.venv`. The builder's default ASAR packaging does not establish a working external Python
runtime layout. Runtime data is also stored beside backend source (`backend/studio.py:37`).

Before distributing an installer, exclude user data/secrets/caches, package external runtime
resources explicitly, move writable data to a user application-data folder, and verify installation
on a clean Windows environment. No installer was built or distributed during this audit.

### 8. Storage maintenance is incomplete — medium

Current logical file totals are approximately 58 MB cache, 213 MB assets, 343 MB renders and
1.34 GB downloaded models. Some render/asset files are hard-linked, so these totals are not
unique physical disk consumption.

There is no project-aware cache cleanup/storage budget in the inspected production UI/API.
Provide storage usage and safe removal of unreferenced failed renders/cache while retaining
assets used by saved projects. Model downloads should be managed separately.

## Working areas and verification evidence

- Script parsing, scene timing, narration fitting, rendering and agent validation already have
  deterministic backend coverage: the preceding verification run passed 136 relevant backend tests.
- The preceding Colab suite passed 63 tests; these isolate GPU boundaries rather than measure live
  model quality.
- Fresh checks for this review: syntax passed; generation recovery passed; 53 editor end-to-end
  checks passed, including real MP4 output.
- Recent UI smoke/editor audits passed 237 and 59 checks respectively.
- Local FFmpeg readiness was true.
- At this review's live health check, planner/image/voice/motion services were unavailable.

Fresh evidence:

- `backend/studio-data/verification/checks-result.json`
- `backend/studio-data/verification/check-editor.log`
- `backend/studio-data/verification/editor-e2e-result.json`
- `backend/studio-data/verification/generation-recovery-result.json`
- `READY_SCRIPT_VERIFICATION.md`

## Suggested implementation order

1. Stable cache identity, stage timings and explicit queue state.
2. Phase-aware model reuse and batched narration.
3. Durable resume and cancellation of long operations.
4. Benchmark a small distilled motion model against existing Wan on the actual GPU.
5. First-shot quality review and targeted regeneration.
6. Complete desired research/specialist actions and storage tools.
7. Prepare and verify a distributable installer.
