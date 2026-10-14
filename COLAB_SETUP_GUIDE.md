# SmartEdit Colab setup

## Update: 2026-10-14 — OmniVoice narration

The default Colab speech engine is now **upstream OmniVoice 0.2.1**, installed in `/content/smartedit-omnivoice/venv` with Python 3.11, PyTorch/Torchaudio 2.8.0 and Transformers 5.3.0. This does not install the VoiceStudio desktop application or modify the image pipeline's Transformers 4 environment. Select **OmniVoice / Colab** in desktop voice settings and save. Existing explicitly saved Edge preferences remain selectable. New settings default to the bridge.

GPU jobs share one lock. Before OmniVoice synthesis, the bridge releases SDXL/Wan state and unloads running Ollama models. Each speech worker exits after generation to release its GPU allocation. Generation errors remain errors instead of silently switching voices. Installer and worker diagnostics are in `/content/smartedit-omnivoice/runtime.log`. First setup downloads the CUDA runtime and model weights; subsequent successful downloads are reused.

Male/female narrator profiles use a self-generated reference, persisted per language and reused across scenes. This improves continuity but does not guarantee perceptual identity or pronunciation. No reference-recording upload UI is included. Edge-specific named voices, pitch/delivery and normalization controls are disabled in bridge mode. Hindi, English and a mixed Hindi/English startup sample must decode and contain non-silent audio. Listen to `/content/smartedit-voice-check-hi.mp3`, `-en.mp3` and `-hinglish.mp3` before production. These checks cannot establish pronunciation quality automatically.

Bridge captions still use estimated phrase timing; word alignment is not implemented in this change. OmniVoice weights remain non-commercial (CC-BY-NC), and the audio tokenizer has separate upstream terms: https://huggingface.co/k2-fsa/OmniVoice. Generated profiles and downloaded models live on the Colab runtime disk and may be lost when that runtime is deleted.

Legacy speech can be explicitly requested with `SMARTEDIT_VOICE_ENGINE=auto`, `edge` or `mms`; the default is `omnivoice`. Changing the voice engine invalidates the old bridge cache through the updated cache version. An already installed old notebook must be replaced with the full updated `.ipynb`.

## Update: 2026-10-12 — resilient neural voice

The `502: Neural voice service could not produce audio` failure came from the Edge speech path, not MuseTalk. Its previous code discarded the provider exception and retried the same service. The explicitly selected legacy mode `SMARTEDIT_VOICE_ENGINE=auto` tries Edge with bounded retries, then Meta MMS neural speech on CPU. An Edge failure starts a ten-minute cooldown so subsequent scenes do not repeat the same network delay. Full failure of both providers remains an error, never a successful empty soundtrack.

Both Hindi and English startup samples are decoded and checked for non-silent audio before the connection is advertised ready. Listen to `/content/smartedit-voice-check-hi.mp3` and `/content/smartedit-voice-check-en.mp3`; decoding alone does not establish pronunciation quality. Provider diagnostics appear in the cell and `/content/smartedit-voice.log`. Health and audio response headers identify the provider actually used. Worker processes release MMS model memory on exit, and long scripts are synthesized in bounded chunks.

MMS has a fixed speaker per language: selected Edge gender/voice does not carry over. Hindi fallback needs Hindi script; Romanized Hinglish and mixed scripts are not guaranteed. The model weights use **CC-BY-NC-4.0 (non-commercial)**. Use `SMARTEDIT_VOICE_ENGINE=edge` to disallow this fallback, or `mms` to skip the online Edge service. First use downloads approximately 145 MB of weights per language; cached models can be reused. See [Meta's Hindi model card](https://huggingface.co/facebook/mms-tts-hin).

Current alternatives were reviewed: [Qwen3-TTS 0.6B](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice) does not list Hindi among its ten supported languages; [Chatterbox](https://huggingface.co/ResembleAI/chatterbox) has multilingual Hindi support but would require a separate integration. This update chooses the existing Transformers-compatible CPU model to address the failing speech service without another GPU workload. It does not claim MMS is the newest or highest-quality voice model.

Stop the old cell, upload the updated notebook, and verify the first line says `2026-10-14 / OmniVoice narration`. Select **OmniVoice / Colab** in desktop voice settings to use this speech path for generation. Desktop **Direct neural voice** is a separate provider path. Do not delete your runtime or model cache for this error.

## Update: 2026-10-11 — MuseTalk recovery

Stop the previous setup cell and upload the complete `colab/SmartEdit_Colab.ipynb` using Colab's File → Upload notebook. Select a T4 GPU and enable notebook access to the `NGROK_AUTHTOKEN` secret. Run the single setup cell. The first line must say `2026-10-11 / MuseTalk recovery`. Use only one setup cell at a time.

MuseTalk now streams child-process stdout and stderr into the cell and appends them to `/content/smartedit-musetalk/setup.log`. CUDA allocation and compiled dependency checks run before checkpoint downloads. Reused installations are checked again, and failed checks cannot retain a successful installation marker. Downloaded files remain available for reruns. Its dependency versions remain unchanged because the supplied screenshot does not show the underlying import exception.

If MuseTalk fails, the other services continue their startup checks; talking presenter stays unavailable. Read the actual exception with `!tail -n 80 /content/smartedit-musetalk/setup.log`, fix that reported cause, then stop and rerun setup. Do not delete the runtime merely for an import failure. A successful installation still needs the five-second presenter test to verify real lip-sync inference.

Use `colab/SmartEdit_Colab.ipynb` in Google Colab. The root `Colab_Ollama_Setup.py` and `colab/SmartEdit_Colab.py` contain the same setup code; use one entry point per runtime.

## Run it

**Colab says READY but the desktop connection fails:** copy the complete private **ONE-PASTE CONNECTION LINK** from the currently running cell into the desktop Colab URL box, then click **Connect & Test**. The plain ngrok URL does not contain the bridge token. This is the SmartEdit **bridge access token**, not your ngrok account authtoken. Rerunning setup creates a new bridge token even when ngrok keeps the same URL; reconnect with the new full link. Keep an already working Colab cell running—an authentication failure does not require downloading the models again.

The desktop accepts a full connection link in either its Colab URL box or the matching server's Bridge access token field, extracts its token/model and stores the normalized values. It rejects links for a different server rather than forwarding their credentials. **TOKEN REQUIRED / HTTP 401 or 403** means the server answered but rejected the credential; an offline tunnel, timeout, failed startup check or missing model now has its own diagnostic. Motion stays **Not checked** until the bridge is authenticated, instead of incorrectly recommending a different GPU. Refresh preserves a newly pasted link, and Connect & Test does not change your video edits.

**Fix for the generic `Ngrok setup failed (PyngrokError)` screenshot:** the previous setup incorrectly passed `ngrok_version='3'` to pyngrok 7.5.1, which accepts `'v3'`. This was a setup-code bug, not proof that your token was wrong. The error was reproduced using the actual 7.5.1 wheel. The setup now pins that version, uses `'v3'`, checks configuration compatibility in the fresh import probe, and preserves the underlying error/output with the token redacted. Diagnostics are saved to `/content/.smartedit-ngrok/startup-error.log`. The version-argument fix is retained in build `2026-10-03 / motion-speed-presets`. Upload the updated notebook and run its cell; do not run an older setup cell afterward.

Verification: 35 offline tests passed with the real pyngrok 7.5.1 wheel, including reproducing the old error, creating the real YAML configuration, validating CLI arguments, and testing redacted diagnostics. Network/CLI process boundaries were mocked; live ngrok authentication and GPU inference are still checked on your Colab runtime. The Gradio/Hub warning is a separate preinstalled-package conflict and did not stop the model imports in the screenshot.

**If ngrok reports `TypeError: expected str, bytes or os.PathLike object, not dict`:** one of the token/config arguments passed to the ngrok command is a dictionary. This is one traceback, not several independent model errors. The updated setup validates the token before installation, prompts privately again if the stored value is invalid, and uses its own explicit string paths for ngrok instead of a possibly modified default configuration. In Colab Secrets, set **NGROK_AUTHTOKEN** to only the authtoken value, without a JSON object, quotes, URL or `ngrok config add-authtoken` command; enable notebook access. Replace the old cell by uploading the current notebook. The ngrok agent now authenticates before Ollama installation/model downloads, so token, network and account-session errors surface early. Tests exercise these failure paths with mocks; live account authentication still needs your Colab runtime.

**If the pasted cell reports `SyntaxError` near `progress(...)`:** the full distributed files and notebook cell are syntax-checked together for Python 3.13 grammar. The highlighted line alone may be valid; an incomplete call or quote above it can produce this error. Use **File → Upload notebook** with `colab/SmartEdit_Colab.ipynb` instead of merging text into an existing cell. Alternatively, upload the complete `Colab_Ollama_Setup.py` through Colab's Files panel, then run `%run /content/Colab_Ollama_Setup.py` in a new code cell. A syntax error happens before this setup downloads or loads models; clearing the model cache will not fix it.

**If Colab says it crashed after using all available RAM while fetching model shards:** replace the setup cell with the current file and **restart the session** before running it. Downloads now use one Hugging Face file worker, disable Xet/accelerated transfers, and complete before loading model weights. All image and motion loaders use local files only; parallel weight loading is disabled. Freed model memory is returned to Linux between stages. This reduces overlapping allocations, but cannot guarantee every model fits in a free session. GPU RAM and system RAM are separate limits.

Completed files are reused from the Hugging Face cache on the same runtime disk; interrupted HTTP transfers can resume when supported. Do not delete the cache to retry. A runtime replacement/deletion may remove its disk and require downloads again. Download progress may list several finished files, but only one file is actively downloading. Required SDXL FP16 or Wan/FLUX components are fetched; duplicate ONNX, Flax and original-checkpoint files are excluded. Models run sequentially. When enabled, startup motion is a real inference test.

**If imports pass but setup stops with `Command ['sh'] returned non-zero exit status 1`:** this is the Ollama Linux installer, not the Python package resolver or video inference. Replace your old setup cell with the updated `Colab_Ollama_Setup.py` and rerun. The setup now checks and installs missing system tools (including `zstd`) before running Ollama's installer, and captures the installer's actual output in the cell and `/content/smartedit-install.log`. Current [official Ollama installers](https://github.com/ollama/ollama/blob/main/scripts/install.sh) require `zstd` for `.tar.zst` downloads. A bare `sh` exit code alone cannot confirm which prerequisite or download failed; the updated log preserves that detail. A Gradio/Hub compatibility warning is separate: SmartEdit does not use Gradio, and successful model imports mean that warning did not stop this setup stage.

**If you previously saw `CalledProcessError` during pip installation:** replace the old setup cell with the updated file, then choose **Runtime → Restart session** and run it again. The earlier combination of Diffusers 0.40.0 and Transformers 4 had incompatible Hub requirements. The corrected setup pins **Diffusers 0.37.1, Transformers 4.57.6 and huggingface-hub 0.36.2**. Do not rerun the old cell after installing the fix, because it requests the conflicting version again.

The installer now resolves the complete dependency set before changing packages, prints pip's actual errors, writes `/content/smartedit-install.log`, and checks SDXL/Wan/FLUX imports in a clean child process before downloading model weights. System package installation, the Ollama installer and planner downloads also write to this log. Python 3.13/Linux wheel resolution for this manifest passed; offline tests cover dependency order and installer failure diagnostics, but do not replace a live Colab run. The manifest is also available as `colab/requirements-colab.txt`.

The conflict is documented in the official [Diffusers 0.40.0 package metadata](https://pypi.org/pypi/diffusers/0.40.0/json) (`huggingface-hub>=1.23,<2`) and [Transformers 4.57.6 metadata](https://pypi.org/pypi/transformers/4.57.6/json) (`huggingface-hub>=0.34,<1`). Diffusers 0.37.1 accepts the selected Hub 0.36.2 release and includes the Wan and FLUX.2 Klein pipelines used here.

1. Open [Google Colab](https://colab.research.google.com/), choose **File → Upload notebook**, and select `colab/SmartEdit_Colab.ipynb`.
2. Choose **Runtime → Change runtime type → T4 GPU**. Start a fresh runtime after updating the setup; do not mix old imported libraries with the new installation.
3. Add only your ngrok account's plain authtoken value to **Secrets → NGROK_AUTHTOKEN**, and enable notebook access. Invalid or missing values trigger a hidden prompt; dictionaries/JSON and shell commands are not accepted.
4. Run the code cell. It prints the detected GPU/RAM, selected model IDs, and download/inference progress. Models run one at a time to share VRAM.
5. Wait for **SMARTEDIT CONNECTION READY**. Startup tests Hinglish JSON edit planning, Hindi/English narration and an image. Motion testing is opt-in; the first actual motion job tests inference. The first download and T4 video generation can take many minutes; do not stop the cell while it is progressing.
6. If you opted into the motion startup test, preview `/content/smartedit-motion-check.mp4` using Colab's Files panel. This is the generated startup sample. Successful encoding/decoding is not a subjective quality guarantee.
7. Copy the full private **ONE-PASTE CONNECTION LINK** into SmartEdit's Colab URL field and click **Connect & Test**. This carries the selected language model and bridge token. Keep the Colab cell and your PC backend running.
8. Start with **Image preview** to check composition. Choose **Hybrid** for one motion opening plus animated images, or **Full AI motion** for motion in every scene. Select Fast draft, Balanced or High detail in Motion detail. Use **Image story** for generated stills with pan/zoom. In the editor, use **Connect AI** to configure the same planner for flexible editing requests.

The link contains a private access token. A new runtime creates a new connection; paste the new link instead of reusing yesterday's connection.

## Automatic model choices

| Hardware detected | Planning and edits | Images | Motion |
|---|---|---|---|
| Free T4, about 15 GiB GPU / 12 GiB RAM | Qwen3.5 9B | SDXL 1.0 FP16 | Wan2.1 T2V 1.3B, 480p-class, 16 fps |
| Native BF16, at least 22 GiB GPU / 32 GiB RAM | Qwen3.5 9B | FLUX.2 Klein 4B | Wan2.2 TI2V 5B, 720p-class, 24 fps |
| At least 30 GiB GPU / 32 GiB RAM, native BF16 | Qwen3.5 27B | FLUX.2 Klein 4B | Wan2.2 TI2V 5B, 720p-class, 24 fps |

Smaller supported GPUs use Qwen3.5 4B and SDXL. Motion is disabled below 14 GiB GPU memory or 11 GiB RAM. Image and video upgrade thresholds are independent: FLUX can be selected from 24 GiB system RAM, while the 5B motion path requires 32 GiB. These thresholds are conservative application policies, not measured guarantees for every runtime. Free Colab does not guarantee a particular GPU or session duration.

Selection favors an integrated model that fits the available runtime. It does not download every large model or claim these are universally the highest-scoring models. Larger model downloads, hidden GPU allocations and long sessions can still exhaust resources. Restart a clean runtime if an actual inference check fails.

The choices follow the official [Qwen3.5 Ollama model catalog](https://ollama.com/library/qwen3.5), [Wan2.1 model card](https://huggingface.co/Wan-AI/Wan2.1-T2V-1.3B), [Wan2.2 5B model card](https://huggingface.co/Wan-AI/Wan2.2-TI2V-5B-Diffusers), and [FLUX.2 Klein 4B model card](https://huggingface.co/black-forest-labs/FLUX.2-klein-4B). In particular, the official Wan2.2 5B instructions target a 24 GB-class GPU with offloading; the new model is not forced onto a free T4.

## Optional overrides

Leave these unset for automatic selection. To override, add `os.environ['NAME']='value'` after `import os` in the code cell, before `main()` runs.

| Variable | Values | Effect |
|---|---|---|
| `SMARTEDIT_COLAB_MODEL` | `qwen3.5:4b`, `qwen3.5:9b`, `qwen3.5:27b` | Explicit language model; memory checks still apply |
| `SMARTEDIT_IMAGE_MODEL` | `auto`, `sdxl`, `flux` | FLUX is guarded by native BF16 and memory requirements |
| `SMARTEDIT_VIDEO_MODEL` | `auto`, `wan2.1`, `wan2.2` | Explicit motion family with memory checks |
| `SMARTEDIT_VIDEO_QUALITY` | `quality`, `balanced` | Legacy base profile. Desktop requests explicitly select 12/30/50 steps via Fast draft/Balanced/High detail |
| `SMARTEDIT_TEST_MOTION` | `1`, `0` | Default `0`: connect without rendering an unused motion clip. Set `1` to opt in. Motion health stays **NOT TESTED** until real inference succeeds |

FLUX.2 Klein's distilled checkpoint uses its documented **4 steps / guidance 1.0**; SDXL uses the app's 28/40-step quality setting. T4 runs Wan in FP32 because it lacks native BF16; the motion text encoder is loaded in 8-bit, used, and released before the video transformer loads. Modern supported GPUs use BF16 Wan transformers. The selected model's own scheduler is preserved for Wan2.2.

## What is and is not verified

- Offline tests cover model selection, resource guards, image-call parameters, JSON planner validation, motion profiles, queue/cancellation behavior, and exact synchronization of both Python entry points and the notebook.
- This PC has not executed these models on a live Colab GPU. Installation, memory fit and generated-video quality must pass on your actual runtime. The image/planning/voice startup tests advertise their own readiness; motion availability and a passed motion inference test are reported separately.
- Generated footage is 480p-class or 720p-class depending on the selected model. A 1080p export resizes it; it does not recover native 1080p detail.
- Character continuity, cinematic reference quality and lip-sync are not guaranteed. Voice is a separate Edge neural speech track using an online service; these Wan paths do not generate synchronized speech or a native soundtrack.
- The edit planner applies supported timeline operations. Choosing a stronger planner does not add object/background replacement or arbitrary video-to-video generation to the editor.

To maintain the notebook after source edits, run `backend/.venv/Scripts/python.exe scripts/sync_colab_notebook.py`. Verify with `backend/.venv/Scripts/python.exe -m unittest discover -s colab -p "test_colab_*.py"`.
