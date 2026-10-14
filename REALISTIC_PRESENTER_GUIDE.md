# Automatic talking avatar — no paid AI API key

Enter a topic such as **Explain machine learning**, select **Avatar explainer → AI talking avatar · Colab**, choose Alex or Maya, duration, language and layout, then Generate video. No photo or presenter clip upload is needed.

## First setup
1. Upload `colab/SmartEdit_Colab.ipynb` to Google Colab and choose a T4 GPU runtime.
2. Tick **ENABLE_REALISTIC_PRESENTER** before running the cell. MuseTalk installs in an isolated Python 3.10 environment and downloads several GB on first setup.
3. Paste the complete ONE-PASTE connection link into SmartEdit and Connect & Test. Ngrok authentication is still needed to connect your PC; no paid video-provider API key is required.
4. Save your work and reopen SmartEdit after updating the app. Choose Avatar explainer and AI talking avatar.
5. Select a presenter, language and voice. Check setup, then Test 5 seconds. The app creates the face automatically. Review voice and mouth movement before making a full video.
6. Enter your topic and duration, then Generate video. Plan scenes produces only a storyboard. Draft video preview makes a 720p MP4, including the selected avatar and voice.

## Connected flow
Topic research and script planning → duration-fitted narration → automatic face creation → MuseTalk lip-sync → relevant supporting images/slides → presenter composition → captions and MP4 export.

The image model creates a centered front-facing fictional adult educator. Alex and Maya select appearance; the color theme sets the portrait background. Supporting visuals follow the topic and visual style independently. Voice is chosen in Voice settings & preview.

The same portrait is cached across scenes, the five-second test, draft and final export. Appearance or theme changes create a different face. Changing narration, timing or tempo invalidates the lip-sync cache. The duration-fitted voice is used for both lip-sync and final audio. No silent or illustrated fallback is substituted on failure.

New requests ignore old clip preferences. Existing saved projects containing a presenter clip remain renderable for compatibility.

Side-by-side and both bottom-corner layouts support landscape, portrait and square. The entire portrait fits the presenter panel; this is not automatic background removal.

## What this mode can produce
A generated talking portrait beside or over educational visuals, with speech-driven mouth movement. It does not generate natural head movement, hand gestures, walking, or a full-body performance. Illustrated · Fast remains available for the lightweight drawn presenter with simple animated gestures.

## Verification and limits
Local tests exercise real FFmpeg encoding, audible output, exact 20-second output, all nine aspect-ratio/layout combinations, automatic portrait reuse, cache changes, failure handling and upload-free UI controls. Image generation, voice and MuseTalk inference are simulated in those tests; their visual and speech quality cannot be inferred from these checks.

Actual MuseTalk installation and lip-sync still require a live Colab GPU test. No GPU quality/speed benchmark has been completed on this PC. The installer follows the official MuseTalk repository pinned to revision `0a89dec45a0192b824e3cf4daf96c239440c5ed8`.

First setup and GPU inference can take minutes. This mode is not fully offline: the Colab bridge, neural voice and optional references need connectivity. Models are pretrained; this update does not train agents.

Official model: https://github.com/TMElyralab/MuseTalk
