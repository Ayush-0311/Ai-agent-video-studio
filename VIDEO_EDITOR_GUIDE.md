# Uploaded video editor

## Prompt-to-video controls

- **Video creation:** AI motion requests generated video shots; Image story requests still images with pan/zoom. Generate checks the selected visual service, planner and local encoder before planning. Connect the running Colab bridge first.
- **Visual style / Character preference:** both are sent to the planner and visual model. Character preference describes appearance; it does not guarantee character identity or lip-sync.
- **Video format / Narration language:** landscape, portrait or square controls export dimensions; the selected language is sent to planning and speech synthesis.
- **Target duration:** new videos default to **Exact target · Fit script to duration**. With Auto shots and narration enabled, the app measures the voice and expands or shortens the generated script before creating images, motion or an avatar. A 40-second target exports 40 seconds, with short scene pauses instead of long silent padding. Up to three measured revisions are allowed; unsuccessful fitting stops before generating new visuals. **Natural pace** remains optional and can produce a different final length. Motion is capped at 60 seconds, and individual shots must fit the preset limit and cannot be stretched beyond twice their source length.
- **Add narration / Show subtitles:** independent switches. Subtitles can remain on while narration is off. No voice synthesis is requested for silent scenes.
- **Scenes:** Auto shots plans a sequence from a topic. Sentences splits at sentence endings (including Hindi `।`) or line breaks. Paragraphs uses blank-line boundaries. Manual tags requires `[Scene 1]`, `[Scene 2]`, etc. Each script segment gets one scene; invalid scene counts/durations produce an explanation.
- **Plan scenes:** opens the storyboard in the editor without rendering. Review the scene text/visual prompts, then Export. **Generate video** plans and renders the MP4.

Auto shots first interprets the prompt's subject, purpose, audience, tone, required examples and visual approach. With Online references enabled, factual topics use a focused Wikipedia query and up to two introductory extracts. The writer receives the original prompt, interpreted brief and available sources; the shot director and duration revisions retain that brief. Stories keep their requested creative direction. The production report records the interpretation and source availability. If interpretation fails twice, planning uses the original prompt with a progress notice. Finished scripts keep their supplied scene boundaries.

Planning then runs a writer followed by a separate shot director, character-reference checks and storyboard QA. The workflow and exact model/tool responsibilities are documented in `AGENT_WORKFLOW_GUIDE.md`. These are integrated stages and role prompts, not newly trained models.

Validation uses the real UI, real FFmpeg encoding and external-AI fixtures. Live Colab model availability and output quality must be verified on the connected runtime; passing local tests alone does not prove GPU generation is ready.

Normal video editing and MP4 export run on your PC with FFmpeg. Colab is not required for uploaded footage. AI generation and automatic transcription are separate features; transcription may need its first model download.

After an update, save existing work and reopen **🚀 2. LAUNCH SmartEdit.bat**. Startup automatically replaces an idle backend from this folder when its source version changes. Wait for active exports/generation to finish before relaunching.

1. Upload a video and choose **Open in Editor**. The first clip is selected automatically. For speech captions, select the upload language, enable **Transcribe speech into captions**, and use **Import video** instead. The transcription checkbox is off by default; imported source audio does not request AI narration.
2. Click a clip in the **VIDEO** track. Drag its edges to trim, or enter exact **Source in / Source out** seconds in the right panel and click **Apply clip changes**.
3. Move the playhead and press **S** to split. Use Delete, Duplicate, Cut/Paste, or the Move arrows. Clips can also be dragged onto another clip to reorder them. **+ Media** appends more videos or images.
4. Set clip speed, volume, mute, full-frame fit/center crop, mirror and caption text in the right panel. Under **Video settings**, choose aspect ratio, color, captions, watermark, noise reduction and music volume. **+ Audio** attaches a background track; **Remove music** removes it.
5. Play or scrub the timeline to preview the edited source ranges. The playback speed pills and volume slider are monitoring controls; use **Clip properties** to change exported speed or volume.
6. Click **Export**, choose 720p/1080p and subtitle settings, then **Export MP4**. After completion, **Download edited MP4** opens the native save dialog. A new edit hides the previous download link until another export completes.

**Save project** / Ctrl+S saves the editable project to this PC. Open it again from Saved projects on the dashboard. Ctrl+Z / Ctrl+Shift+Z undo/redo edits, including project settings. Ctrl+C / Ctrl+V copy/paste clips. Space plays/pauses; Left/Right seek by one output frame, Shift+Left/Right by five seconds. Shortcuts do not change the video while typing in a field.

Preview follows trim, split, reorder, speed, mute, volume, mirror and crop. Captions and watermark preview as overlays. Brightness, contrast, saturation and sharpening are available in Clip properties and through the edit assistant. Color and sharpening are approximate in the browser; final filters, audio denoising and music ducking are applied by export.

## Natural-language edit assistant

Choose **Whole video** or **Selected clip**, type a request and click **Apply edits**. The change summary lists the operations actually applied. Each request is one undo/redo step. Review the preview, save your project, then Export to download the edited MP4. Cancel discards a pending response; a response is also discarded if you changed the timeline while it was being planned.

These examples work locally without Colab:

- `Reel banao, volume 50%, thoda bright karo`
- `Video ko natural aur clean banao` — restrained brightness, contrast, saturation, sharpening and audio noise reduction; preserves the original footage.
- `Keep 2 to 8 seconds` or `Remove 1 to 3 seconds` — times refer to the current output timeline, accounting for clip speeds.
- `Clip 2 ko 1.5x speed do`
- `Caption "Welcome, everyone" lagao`
- `Black and white`, `Mute`, `Split at 3 seconds`, `Title "My video" lagao`

Flexible English/Hindi/Hinglish wording uses the configured free Colab/Ollama model through **Connect AI**. The model returns only validated editing operations; it cannot execute commands or replace source assets. If any part is unsupported or ambiguous, nothing is applied. Color look, aspect ratio and noise reduction are whole-project settings; clip speed, exposure, crop and volume obey the selected scope. The assistant receives timeline metadata and existing caption text, not visual analysis of video frames.

This is a sequential source-video editor. The edit box supports `Fade through black`, `Fade white` and `Remove transitions`. The clip panel also provides colored-screen background replacement and manual moving blur/image overlays; see `VIDEO_EFFECTS_GUIDE.md`. Arbitrary background/object/face replacement, lip sync, automatic tracking and recovering missing detail remain unavailable. Speech transcription and text translation are separate tools. The local examples work offline, while unrecognized wording needs a reachable AI connection.

Supported source containers include MP4, MOV, MKV and WebM. When the browser cannot play the original codec, a cached H.264/AAC preview is made; export uses the original file. Each upload is limited to 500 MB; a project has up to 30 clips and a maximum final duration of 30 minutes. Keep the local backend running through preview, export and download.

## Verification

Desktop startup now compares the loaded backend's source fingerprint with the installed files, including when started through `npm start`. An idle backend from this same folder is replaced automatically after an update. Active generation/export jobs and unrelated processes are never stopped by this update check. Preview failures offer **Retry preview**, and an incompatible backend cannot accept new uploads or exports that would silently ignore editing settings. If an already-open editor still shows the old error, reopen the app and select the saved project; the source video does not need another upload.

`powershell -NoProfile -ExecutionPolicy Bypass -File tests/desktop-launcher.ps1` checks legacy/current backend detection, source updates, active jobs and process ownership. Set `SMARTEDIT_TEST_LIVE=1` when running `tests/editor-e2e.cjs` to test the actual backend on port 8000, including the previously failing saved avatar upload. The test creates a separate demonstration project and verifies preview retry after a network failure and rejection of an old backend before export.

`tests/editor-e2e.cjs` launches an isolated backend and imports the supplied avatar reference video through the real UI. It trims, splits, reorders, changes speed/mute/crop/mirror/captions, checks actual Chromium playback across an edit, saves/reopens the project, exports, and clicks Download. It also checks drag trim, extra media, undo and recovery from an empty timeline. No AI responses or source media are mocked in this test.

Each test run writes a unique `backend/studio-data/verification/edited-avatar-<job-id>.mp4` (latest path in `editor-e2e-result.json`): **5.5 seconds, 720×1280, H.264/AAC**, with two reordered clips, first-clip speed/mute/mirror/crop, black-and-white color, caption and a test watermark. The original source remains untouched. Test outputs and the isolated backend data are ignored by Git.

```powershell
backend/.venv/Scripts/python.exe -m unittest discover -s backend -p test_studio.py -v
node_modules/electron/dist/electron.exe tests/editor-e2e.cjs
node_modules/electron/dist/electron.exe tests/ui-smoke.cjs
```

Backend checks additionally inspect decoded pixels for crop/mirror, measure exported audio volume, and verify a browser-compatible preview for lossless MKV with HTTP range requests.

## Save protection and repeatable checks

The editor marks unsaved work. Opening another project or closing the desktop window offers Save and continue, Discard changes, or Keep editing. A save failure keeps the current project open. Reloading unsaved work is blocked until you explicitly discard it or return and save.

Generated previews are retained with saved projects. Changing narration or visual direction invalidates the old preview. Generated clips keep effective speed and mute when split or trimmed. Clip speed is 0.5–2×; playback speed is only for monitoring. A previous export is labeled separately when saved edits need a new render.

Damaged job/project records are retained for recovery and skipped individually. The dashboard warns about them while healthy records remain usable.

From the app folder, run `backend/.venv/Scripts/python.exe -m pip install -r tests/requirements.txt`, then `npm test`. `npm run test:audit` runs the dedicated repair and real export checks. Tests create their own portable media fixture; `SMARTEDIT_TEST_VIDEO` optionally supplies another source. Summary: `backend/studio-data/verification/checks-result.json`; detailed logs: `check-*.log`. Tests use isolated renderer profiles and an isolated editor backend; AI/GPU responses remain fixtures unless explicitly tested live.


## Translate and dub an imported video

In Import options, select the language spoken in the source video. Enable **Translate & dub video**, select a different target language (Hindi, English, Spanish, French or German), and enable **Add translated captions** if wanted. Press **Translate & dub video** to transcribe, translate, generate replacement narration and export the result. The source upload remains available; the new video uses replacement audio. Restart the desktop/backend after this update (API 16).

Translation uses the configured planner with reasoning enabled, followed by a source-grounded review of terminology, meaning, negation and direction before generating speech. Translation and review can each take several minutes on Colab; review processes one speech segment at a time. Requests use a constrained JSON schema and compact scene IDs. Review instructions ask for brief English analysis before the Hindi result to conserve the model's output budget. Qwen3.5 thinking requests use its recommended general-task sampling profile rather than temperature-zero decoding (https://huggingface.co/Qwen/Qwen3.5-9B#best-practices). Truncated responses are rejected, with one retry requesting shorter analysis for incomplete or invalid JSON. There is no silent retry with reasoning disabled. Hindi output must contain Devanagari. Review important content before publishing, since model reasoning does not guarantee translation accuracy. Dubbing uses the same saved voice engine as voice preview, including OmniVoice through the running Colab bridge. Whisper runs locally for source transcription. The selected voice service is checked before transcription; an offline Colab shows a reconnect instruction without doing the expensive work. The current importer accepts up to 30 speech segments; trim longer recordings first. Select the actual source language, not the desired output language.

Original audio, including background music and sound effects, is replaced. Existing subtitles printed into the picture remain visible; this is not subtitle erasure, speaker voice cloning or lip-sync. The new captions align the exact translated words to the generated speech, then transform their timestamps to the source timeline and dubbing speed. Original visuals and timeline duration are preserved; the initial dubbed export chooses the nearest supported landscape, portrait or square format from the source video. Generated speech may accelerate by up to 25% to fit its source slot. If it does not fit, one more concise translation is generated from the original speech and measured again. If that still does not fit, the job stops instead of cutting words or overlapping speech. The source project is retained on failure.

Local integration checks use real FFmpeg and substituted translation/TTS providers. They check audio replacement, duration, Hindi Unicode captions, caption-off export, invalid translation responses and overlong speech. Actual translation quality and OmniVoice voice quality require a live Colab run.

## Colab narration caption alignment

Generated scenes using Colab narration now align the supplied script to the actual audio with local Whisper before rendering captions. This preserves the script's spelling instead of substituting recognition guesses. Cached timings are tied to both text and audio hashes. The current alignment supports narration up to 30 seconds per scene; split longer scenes or disable captions. If alignment cannot produce valid timings, export stops with an error instead of silently presenting estimated synchronization. Imported dubbing uses the same alignment and accounts for the source offset and any speech acceleration.

Restart the backend to load this change. The live review found the old bridge path displayed the word “water” around 0.49 seconds late; the re-export placed its caption at 2.32 seconds, compared with an independent speech estimate of 2.34 seconds. This sample does not guarantee perfect alignment or pronunciation for every voice or language.
