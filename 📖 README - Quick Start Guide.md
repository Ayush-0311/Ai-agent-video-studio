# SmartEdit desktop software — Quick Start

The original Electron desktop UI is retained. The local Python backend encodes your videos; Colab supplies AI scripts, motion shots, images and narration.

## First run, or after updating this project

1. Install Python 3.11+ and Node.js LTS. Enable Python on PATH.
2. Install the full FFmpeg package, including FFprobe, and add its bin directory to PATH.
3. Double-click **🔧 1. SETUP (First Time Run).bat**. Internet access is required for dependencies.
4. Wait for **SETUP COMPLETE**. Setup checks Python libraries, the Electron executable, production files, FFmpeg and FFprobe. Missing requirements produce an error, not a success message.

## Daily use

**Uploaded footage:** Colab is not required. Launch the app, upload your video → **Open in Editor** → select/trim/split/reorder clips → **Export MP4** → **Download edited MP4**. See **VIDEO_EDITOR_GUIDE.md** for the clip controls and shortcuts. Restart both the app and local backend after this editor update.

1. Upload **colab/SmartEdit_Colab.ipynb** to Google Colab. Choose a T4 GPU runtime.
2. Add **NGROK_AUTHTOKEN** to Colab Secrets with notebook access, then Run all.
3. Wait for **SMARTEDIT CONNECTION READY** after Hinglish edit-planning, image and Hindi/English voice checks. Motion testing is optional and disabled by default; the first motion request tests inference. Progress appears in the cell.
4. Double-click **🚀 2. LAUNCH SmartEdit.bat**. This checks the local installation, starts the backend hidden, and opens the original desktop app.
5. Copy the complete **ONE-PASTE CONNECTION LINK** from Colab into the app's Colab URL box and click **Connect & Test**. A new Colab session requires its new link. Connection is not automatic until this step.
6. Select **AI motion**, enter your topic, choose a visual style, and start with **10 seconds**. For animated characters choose **3D animation / avatar**. Narration and subtitles are optional. Click **Generate video**, then preview/download the MP4 or edit the scenes. Keep the PC and Colab running until completion.

Models are selected automatically for GPU/RAM: a free T4 uses Qwen3.5 9B, SDXL and Wan2.1 1.3B. Larger supported runtimes can use Qwen3.5 27B, FLUX.2 Klein 4B and Wan2.2 5B. See **COLAB_SETUP_GUIDE.md** for the exact thresholds, overrides and run steps. Motion is 480p-class or 720p-class and resized for export; exact reference quality, character identity and lip-sync are not guaranteed. This update passed offline tests; actual GPU inference must pass in your Colab session. When the optional motion startup test is enabled, its sample is saved as `/content/smartedit-motion-check.mp4` for visual review.

After updating: let active jobs finish, relaunch the app, and run the updated notebook in a fresh Colab GPU session. The launcher replaces this project's idle stale backend automatically. Reconnect with the new Colab link.

The Python copy **colab/SmartEdit_Colab.py** contains the same setup. Use the files in **colab/** as the current setup source.

## Stopping and troubleshooting

- Closing the app leaves the backend running so an export is not interrupted. After exports finish, use **Stop SmartEdit Backend.bat**. It checks this project's backend identity before stopping it; it does not kill arbitrary processes on port 8000.
- Backend startup logs: **backend/studio-data/launcher/backend-error.log** and **backend-out.log**.
- If port 8000 belongs to an old backend or another app, close that process yourself and launch again. The launcher will not silently reuse an unrelated server.
- If dependencies are missing, rerun SETUP. For a Colab/AI failure, check the running notebook and reconnect with its latest link.
- Saved projects and connection settings are in **backend/studio-data**. Keep that folder private.

This is the runnable project-folder desktop setup. A standalone Windows installer with bundled Python and FFmpeg is not included in this update; the existing electron-builder packaging command alone does not provide those runtimes.

See **RUN_FIXED_PIPELINE.md** for model choices, production features, tests and limitations.

Save project stores editable work. Export creates an MP4; Download saves that export to your chosen folder. Unsaved edits prompt before opening another project or closing. Uploaded video formats: MP4, MOV, MKV, WebM, up to 500 MiB. Clip speed: 0.5×–2×. Export: H.264, 30 fps, 720p/1080p.
