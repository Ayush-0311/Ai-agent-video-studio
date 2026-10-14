# Live generation quality and timing — 10 October 2026

This report records actual requests through the user's connected Colab and local desktop backend. It does not claim every prompt, language, resolution or mode has passed.

## Connected hardware and services

- Google Colab Tesla T4: 14.6 GiB GPU memory; 12.7 GiB system RAM.
- Qwen3.5 9B planning; SDXL images; Wan 2.1 1.3B motion available for requests.
- Realistic presenter was disabled in the connected runtime. A green connection indicator does not mean MuseTalk has been installed or tested.
- The current app source refreshes presenter status when the main connection is refreshed. Save open work and reload the app to load updated JavaScript.

## Measured results

| Test | Output | Measured generation time | Result |
|---|---|---:|---|
| Image story, full automatic planning | 20 s, 2 scenes, 1080p/30 fps | 285.72 s (4 min 46 s) | Completed; real SDXL images, neural narration, captions and MP4 export |
| Illustrated presenter, initial existing storyboard | 20 s, 2 scenes, 1080p/30 fps | 87.21 s (1 min 27 s) | Completed; reused image/voice assets, composed presenter and slides |
| Illustrated presenter, polished Alex sample | 20 s, 2 scenes, 1080p/30 fps | 78.35 s (1 min 18 s) | Completed; matching male voice, concise slide headings and points, cached image/voice assets |
| Direct neural English sample | 9.504 s audio | 4.32 s | Decodes; audible |
| Direct neural Hindi sample | 12.264 s audio | 4.10 s | Decodes; audible |
| Colab voice English sample | 8.616 s audio | 3.67 s | Decodes; audible |
| Colab voice Hindi sample | 12.264 s audio | 5.60 s | Decodes; audible |
| Full motion, balanced preset | 20 s target, 2 scenes | Stopped at 823.68 s (13 min 44 s) | User chose Fast draft after measured 96.7 s and 78.2 s steps; no finished motion clip |
| Full motion, Fast draft | 12 s, 2 scenes, 1080p/30 fps export | 754.74 s (12 min 35 s) | Encoded and decoded successfully; FAILED visual quality review |
| Hybrid, Fast draft opening | 12 s, 2 scenes, 1080p/30 fps | 87.52 s (1 min 28 s) | Technical pass using cached sources; poor motion opening remains |
| Realistic talking presenter | Not run | Not measured | Disabled in connected Colab |

Times are individual observations, not promises. Image generation included planning. Hybrid reused the already-generated motion and image sources; its time excludes new motion inference. The illustrated sample reused the completed storyboard and cached media, so its time is not directly comparable with a first run. Polling adds up to roughly three seconds to recorded stages.

Image-story stage observations: planning/visual review about 111 s; voice preflight finished by 120 s; visual generation and scene composition finished by 268 s; final export/validation finished by 286 s.

## Output inspection

All four completed modes contain H.264 video at 1920 × 1080, 30 fps, and AAC audio at 48 kHz. Full-file FFmpeg decoding passed. Frames inspected at 3 and 13 seconds show the requested forest river and tree roots. Captions are readable and stay within the frame. The illustrated presenter, slide text and subtitles are visible without overlap in these sampled landscape frames.

Image story animates still images using camera effects. The illustrated presenter uses drawn animation. Neither result establishes that the Wan motion generator or realistic MuseTalk lip-sync works.

The initial illustrated benchmark used Maya with the saved male voice settings. The polished Alex sample completed in 78.35 seconds and passed full decoding and frame inspection at 3 and 13 seconds. It uses concise slide headings/points and the matching male voice. The original sample is retained with the avatar-initial prefix. Appearance and voice are independent controls.

1080p is the export size. It does not establish native 1080p generative detail. Balanced Wan generates a 640 × 352 source with 81 frames at 16 fps on this profile; longer scenes stretch the source footage. High detail increases workload and still uses a 480p-class source on T4.

## Voice settings

Selected direct neural voice, Natural delivery, -5% speech rate and normalization. English automatically uses a language-matching male voice when the saved Hindi profile is selected; Hindi uses Madhur. Both direct and Colab voice currently use Edge TTS. Direct neural generation applies the app's named voice, delivery and normalization controls.

Audio was checked for decoding, nonzero duration and audibility. Human likeness, pronunciation and emotional delivery still need listening review. These checks do not establish that the voice is indistinguishable from a human. Samples are saved with the benchmark media.

## Problems found and changes

1. Main Colab reconnection could leave an old presenter error visible. Connection refresh now refreshes realistic presenter availability; the UI regression test covers it.
2. The initial 10-second automatic trial failed narration-length validation after 78.23 s. Its requested 22 words exceeded the conservative 19-word total budget, and the model's rewrite still exceeded the limit. A bounded second rewrite attempt now handles over-budget replies. Invalid scene IDs and malformed replies still fail; spoken words are never silently truncated. The successful 20-second run does not prove a live retry succeeds in every tight-duration case.
3. Changed the successful connection message from Motion test passed to Motion encoded; review visual quality. Technical encoding success is not a perceptual quality verdict. The UI regression checks that distinction.
4. Clarified that Colab is required (rather than always saying Connect first while already connected), and added help stating that presenter appearance and voice are selected separately.
5. Updated the demo guide to remove stale claims that lip-sync is not integrated and that all connected services remain offline.

Validation after these changes: 127 backend tests passed; UI 206 and presenter 14 checks passed; static checks and all 41 Colab offline tests passed. The final UI/presenter rerun passed after the motion-quality wording update. An initial sandboxed Electron attempt failed to access its browser cache; rerunning with approved desktop access passed. Offline tests simulate external model boundaries and are distinct from the measured GPU runs above.

## Evidence

Artifacts are under `backend/studio-data/verification/live-quality-2026-10-10/`: completed MP4s, voice MP3s, extracted frames, FFprobe JSON, per-stage events, result summaries and the preserved first failed trial. These local verification files may be ignored by Git.

Balanced motion observations: the first visible download stage began at 45 s; encoder loading began at 487 s; inference settings appeared around 595 s. Steps 1 and 2 took 96.7 and 78.2 seconds, respectively, with reported peak allocation 11.3 GiB. This is the process peak reported by the current callback, not an isolated per-shot VRAM measurement. The estimate after step 2 was 40.8 minutes remaining in the first shot. The user requested Fast draft instead; this incomplete Balanced test is not a successful quality benchmark.

Fast draft first-shot inspection: three source frames at 0.3, 1.5 and 2.7 seconds show movement but severe softness, dark exposure and horizontal banding. This sample fails the visual quality review. The second shot shows recognizable roots but excessive brightness/saturation and poor detail. Low steps/resolution are a possible contributor, but the cause is not isolated; there is no controlled 30/50-step comparison yet. Do not use this result as a polished final video.

Desktop-control limitation: Colab API requests work, but Chrome screen capture times out and clicking reports unavailable coordinate geometry, even after the user restored Chrome. Realistic presenter installation cannot be completed reliably through that control path. It remains disabled.

The completed Fast draft file decodes successfully and has the exact 12-second target duration, but its quality verdict remains FAIL. The 49-frame source is roughly 3 seconds per shot; each is slowed to the six-second narration budget. Most inference steps took 20–23 s, followed by about 60 s decoding per shot.

The [official Diffusers Wan reference](https://huggingface.co/docs/diffusers/en/api/pipelines/wan) uses 50 inference steps with 832 × 480, 81-frame defaults. That is substantially different from this reduced draft. High detail remains unverified here; higher steps are not a guaranteed fix for the observed artifacts. A controlled comparison is required.

For a polished result on this tested configuration, use the image-story sample or illustrated presenter. Motion is technically functional but not validated for final presentation quality. Realistic lip-sync remains untested. No new model has been installed and represented as an improvement without a live quality check.


## What remains before every mode can be called ready

- Motion quality: a controlled higher-step/reference-resolution comparison, or a separately tested distilled video model. The current Fast draft sample is not presentation quality. Balanced was stopped at the user's request; High detail was not run.
- Realistic avatar: enable ENABLE_REALISTIC_PRESENTER in the Colab setup, rerun, reconnect with the complete new connection link, and run Test 5 seconds. There are no benchmark jobs active now. This installer downloads several GB; it has not been run during this check. Desktop automation could not reliably operate the setup controls.
- Voice: listen to the supplied English/Hindi samples for pronunciation and naturalness. Decoding and audible output passed; subjective human likeness is not certified.
- Save open work and reopen SmartEdit to load the updated interface and persisted voice settings.

The working tree already contains broad changes from earlier work. A whole-tree git diff --check reports existing whitespace issues in several files; this does not change the passing functional checks above.

## Review the generated samples

- [Image story — strongest tested visual result](<S:/smart-multimedia-editor (1)/smart-multimedia-editor/smart-multimedia-editor/backend/studio-data/verification/live-quality-2026-10-10/images.mp4>)
- [Polished illustrated Alex explainer](<S:/smart-multimedia-editor (1)/smart-multimedia-editor/smart-multimedia-editor/backend/studio-data/verification/live-quality-2026-10-10/avatar.mp4>)
- [Motion draft — quality failure, kept for diagnosis](<S:/smart-multimedia-editor (1)/smart-multimedia-editor/smart-multimedia-editor/backend/studio-data/verification/live-quality-2026-10-10/motion.mp4>)
- [Hybrid — cached draft motion opening and clear image scene](<S:/smart-multimedia-editor (1)/smart-multimedia-editor/smart-multimedia-editor/backend/studio-data/verification/live-quality-2026-10-10/hybrid.mp4>)
- [English neural voice sample](<S:/smart-multimedia-editor (1)/smart-multimedia-editor/smart-multimedia-editor/backend/studio-data/verification/live-quality-2026-10-10/neural-en.mp3>)
- [Hindi neural voice sample](<S:/smart-multimedia-editor (1)/smart-multimedia-editor/smart-multimedia-editor/backend/studio-data/verification/live-quality-2026-10-10/neural-hi.mp3>)


## Follow-up: caption and silence inspection

The earlier visual inspection established readable captions, not speech synchronization. A follow-up waveform check confirms that captions can appear late: in scene 1 of the image story, audible speech ends around 7.435 s while the final caption starts at 8.750 s. The renderer spreads caption chunks over the full scene, including padded silence. See UPGRADE_PLAN_2026-10-10.md and audio-timing-inspection.json for measurements and the proposed fix. Caption timing is therefore an outstanding issue.
