# SmartEdit: final-year project demo and verification

Updated: 10 October 2026. This is a source-folder desktop app; a standalone Windows installer has not been validated.

## What to demonstrate

1. Save any open work, close SmartEdit, and reopen **🚀 2. LAUNCH SmartEdit.bat** to load the updated interface. The launcher checks the local backend before opening the editor.
2. Choose **Edit your own video**, select an MP4, then **Open in Editor**. Alternatively select a speech language, enable **Transcribe speech into captions**, and choose **Import video**. Transcription is optional and may download its model on first use.
3. Play and scrub the video. Trim using clip edges or source in/out fields; split, reorder, change speed/volume, crop or mirror. Add caption text and choose portrait format.
4. Demonstrate a local edit request: `Make a reel, set volume to 50%, and increase brightness`. Show its applied-change summary, Undo, and Redo. Arbitrary wording may need the connected language model.
5. Save the project, return to Dashboard, and reopen it from **Saved projects & completed videos**.
6. Export 720p, wait for completion, and use **Download edited MP4**. Play the downloaded file to demonstrate that the edits are actually encoded.
7. Open Analytics. Counts and job errors come from saved local records. Completed export jobs provide download links; repeat exports count separately.

The tested example output is `backend/studio-data/verification/edited-avatar.mp4`: 5.5 seconds, 720 × 1280. It is a separate edited test copy of the supplied avatar video.

## AI generation demonstration

Open `colab/SmartEdit_Colab.ipynb` in a GPU Colab runtime and follow `COLAB_SETUP_GUIDE.md`. Keep the runtime running, paste the full ONE-PASTE connection link into SmartEdit, and use Connect & Test. Wait for successful planner, image, voice and selected motion service checks before presenting generation.

Start with a 20-second idea and two concise scenes. **Plan scenes** runs writing, shot direction and structural validation without rendering; **Generate video** also generates assets and renders. Image story uses still images with motion effects; AI motion uses generated video shots. Review the result before presenting it.

Agents orchestrate model/tool calls. Ollama runs the language model; the image/motion models generate visuals; FFmpeg performs composition/export. Role prompts and validation are not model training. See `AGENT_WORKFLOW_GUIDE.md` for the implemented stages.

Free Colab generation is slow and depends on available GPU/RAM and the runtime connection. Local editing/export does not require Colab. On 10 October, the connected T4 completed a 20-second image story and an illustrated presenter video. English and Hindi neural voice samples also passed decoding and audibility checks. See LIVE_QUALITY_REPORT_2026-10-10.md for measured times and the separate motion/presenter status; one successful sample does not certify every prompt.

## Verification evidence

| Suite | Evidence and scope |
|---|---|
| Backend | 127 tests: editing/effects validation, pixel-level composition checks, planning, specialist actions, translation preservation, cancellation and saved-project preservation |
| Colab bootstrap | 41 tests including the pinned pyngrok package; external CLI/network/model boundaries are mocked, not a live GPU run |
| Desktop launcher | 7 tests: version/restart decisions, busy-job protection and process ownership |
| Electron UI | 206 checks and four responsive viewport layouts: all 28 agent-card actions, effects controls, generation options, import controls, job recovery and real-record analytics |
| Real-video end-to-end | 53 checks: portable real video, isolated local backend, Chromium playback/recovery, timeline edits/effects, save/reopen, real encoding and native MP4 download |

Run `npm test` for the complete repeatable check set. Dedicated audit regressions also verify save/discard/cancel, failed saves, native close, generated previews and stale exports.

Results: `backend/studio-data/verification/ui-result.json` and `editor-e2e-result.json`. Compare file modification times with any old error logs; old error files can remain from earlier runs.

## Practical limits for the presentation

- Browser previews approximate color/sharpness/blur; chroma-key background replacement and final audio processing are applied during export. See `VIDEO_EFFECTS_GUIDE.md` for dip transitions, colored-screen replacement and manual motion paths.
- Optional MuseTalk lip-sync is integrated but must be enabled and tested in Colab. Tracked object/face replacement, guaranteed talking-avatar identity, and arbitrary scene reconstruction are not implemented.
- Structural validation and a playable MP4 do not measure realism, character consistency or factual accuracy. No model accuracy percentages are claimed.
- Keep a completed sample MP4 available as a fallback if the free Colab session disconnects. Show the working local edit/export flow independently.

## Recovery

If preview fails, use **Retry preview**. If a job record was deleted, tracking now clears so a new job can start. A temporary network failure preserves tracking; reopen the app to reconnect to that job. Avoid stopping an active export. If the backend reports an older API, save work and relaunch using the provided launcher.

For editor shortcuts and supported edit commands, read `VIDEO_EDITOR_GUIDE.md`.
