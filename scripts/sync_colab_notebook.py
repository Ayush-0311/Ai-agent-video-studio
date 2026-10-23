"""Keep the one-cell uploadable notebook aligned with its reviewed Python source."""
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1] / 'colab'
path = root / 'SmartEdit_Colab.ipynb'
notebook = json.loads(path.read_text(encoding='utf-8'))
source_path = root/'SmartEdit_Colab.py'
source = source_path.read_text(encoding='utf-8')
import re
ltx_support = (root/'ltx_support.py').read_text(encoding='utf-8-sig')
source = re.sub(r'^LTX_SUPPORT_SOURCE = .*$', lambda _: 'LTX_SUPPORT_SOURCE = '+repr(ltx_support), source, flags=re.MULTILINE)
support = (root/'musetalk_support.py').read_text(encoding='utf-8-sig')
source = re.sub(r'^MUSETALK_SUPPORT_SOURCE = .*$', lambda _: 'MUSETALK_SUPPORT_SOURCE = '+repr(support), source, flags=re.MULTILINE)
voice_support = (root/'voice_support.py').read_text(encoding='utf-8-sig')
source = re.sub(r'^VOICE_SUPPORT_SOURCE = .*$', lambda _: 'VOICE_SUPPORT_SOURCE = '+repr(voice_support), source, flags=re.MULTILINE)
omni_support = (root/'omnivoice_support.py').read_text(encoding='utf-8-sig')
source = re.sub(r'^OMNIVOICE_SUPPORT_SOURCE = .*$', lambda _: 'OMNIVOICE_SUPPORT_SOURCE = '+repr(omni_support), source, flags=re.MULTILINE)
source_path.write_text(source,encoding='utf-8')
# Extract the literal manifest without importing optional GPU libraries.
import ast
# Validate the complete cell before updating any deliverable. Colab currently
# uses Python 3.13; parsing alone would miss errors such as return outside a def.
tree = ast.parse(source, filename=str(source_path), feature_version=(3, 13))
compile(tree, str(source_path), 'exec')
source_path.write_text(source, encoding='utf-8', newline='\n')
requirements = next(ast.literal_eval(node.value) for node in tree.body
                    if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'COLAB_REQUIREMENTS' for t in node.targets))
(root/'requirements-colab.txt').write_text('\n'.join(requirements)+'\n', encoding='utf-8', newline='\n')
introduction = """# SmartEdit — prompt to motion video with free Colab
**Build 2026-10-21 / timed scripts and image references:** the desktop can preserve timestamped scenes, separate spoken narration from screen text, and compose a local instrumental. The image route now accepts a main-character reference: SDXL loads `h94/IP-Adapter` (`sdxl_models/ip-adapter_sdxl.bin`) on first reference use; FLUX.2 Klein uses its image input. Weights download into the Colab cache without a paid provider key. This conditions image appearance; identical faces are not guaranteed, and Wan motion still uses written character descriptions. Upload this complete notebook and rerun its setup cell to enable the new image route. Reference inference has local route tests; verify actual GPU quality in your connected runtime.
**Build 2026-10-24 / optional LTX image-to-video:** set the notebook `MOTION_ENGINE` selector to `ltx-13b` only on a native-BF16 GPU with at least 38 GiB VRAM, 48 GiB RAM, and about 52 GiB free disk. It animates generated scene reference images in seven distilled steps; it is unavailable on the free T4. `auto` keeps a T4 on Wan2.1 and chooses the existing Wan route. The engine downloads only the pipeline components it needs, one file at a time, checks free disk before starting, and saves the upstream license locally. Review the [LTX open-weights license](https://huggingface.co/Lightricks/LTX-Video-0.9.8-13B-distilled/blob/main/LTX-Video-Open-Weights-License-0.X.txt) before using or distributing it; it includes use restrictions and special terms for commercial entities with at least $10M annual revenue. This is an optional, unverified-on-Colab route until a GPU render completes; use the opt-in feature report to test it.
**Build 2026-10-14 / OmniVoice narration:** default speech now uses upstream OmniVoice 0.2.1 in a separate Python 3.11 environment. Requires a T4 GPU or larger; first installation/download takes time. Voice jobs release image/motion/planner GPU memory before loading OmniVoice; workers exit after synthesis. Hindi and English startup samples must pass decoding/non-silence tests. Select **OmniVoice / Colab** in desktop voice settings and save. Male/female voice design is supported; named Edge presets do not apply. Word-level subtitle alignment and custom reference-voice upload are not supplied by this integration. Captions on bridge audio remain estimated. Weights are non-commercial (CC-BY-NC); see the upstream model/tokenizer licenses. Runtime log: `/content/smartedit-omnivoice/runtime.log`. Failures do not silently switch voices. Legacy modes remain available only through explicit `SMARTEDIT_VOICE_ENGINE=auto`, `edge` or `mms` overrides.
**Build 2026-10-12 / resilient neural voice:** Edge TTS failures now retain diagnostics and automatically try Meta MMS neural speech on CPU. Hindi and English must both produce decodable, non-silent audio before startup reports ready. Listen to `/content/smartedit-voice-check-hi.mp3` and `/content/smartedit-voice-check-en.mp3`. Logs: `/content/smartedit-voice.log`. MMS downloads each language model once into the Hugging Face cache; it uses a fixed voice (male/female selection does not apply) and is licensed **CC-BY-NC-4.0, non-commercial**. Set `SMARTEDIT_VOICE_ENGINE=edge` to disable fallback or `mms` to use local speech directly. This is the legacy `auto` mode; the current default is `omnivoice`. This changes Colab bridge speech; select **OmniVoice / Colab** in desktop voice settings to use it for generation.
**Build 2026-10-11 / MuseTalk recovery:** isolated GPU and compiled dependency checks run before checkpoint downloads. Setup output, including the actual Python exception, is printed and saved to `/content/smartedit-musetalk/setup.log`. Existing installations are rechecked; downloaded checkpoints are reused. If MuseTalk fails, other services can still start, and talking presenter remains unavailable until repaired. A successful import check is not a lip-sync inference test.
**Updating an existing session:** stop the old setup cell, upload this complete notebook, and run its code cell. Do not run both setup cells together. Keep the current runtime to reuse downloads; if the setup explicitly requests a session restart, restart it and rerun. Do not delete the runtime solely for a MuseTalk import error. To inspect its saved diagnostic, run `!tail -n 80 /content/smartedit-musetalk/setup.log` in a separate cell.
**Build 2026-10-03 / motion-speed-presets:** speed presets, prepared storyboard embeddings and motion-model reuse; retains the ngrok fix: corrected the version argument to `v3` for pinned pyngrok 7.5.1. The previous `3` value caused `PyngrokError` before authentication. Tested against the actual pinned package. Underlying ngrok failures are now shown and logged with the token redacted.
**Installer fix:** this notebook uses compatible Diffusers 0.37.1 / Transformers 4.57.6 / Hub 0.36.2 pins and automatically installs missing Ollama system tools, including `zstd`. Replace any older setup cell; restart the session if older Python libraries were already imported. Dependency resolution runs first; full pip, import, OS-package and Ollama installer diagnostics are saved to `/content/smartedit-install.log` and printed in the cell.
**RAM/download fix:** Hugging Face files download one at a time with Xet disabled, then load from disk with parallel shard loading disabled. Previous completed files are reused if the runtime disk survives. Replace the old cell and restart the session after a RAM crash; do not delete the download cache. This reduces peak RAM usage but live inference must still fit your available memory.
**Avoid copy/paste errors:** upload this `.ipynb` using Colab's **File → Upload notebook**. Its complete code cell is syntax-checked when generated; do not merge snippets into an older setup cell. If using the Python file instead, upload `Colab_Ollama_Setup.py` to Colab's Files panel and run `%run /content/Colab_Ollama_Setup.py` in a new cell.
**Ngrok token fix:** `NGROK_AUTHTOKEN` must contain only plain token text, not a dictionary/JSON, URL or command. Invalid values trigger a hidden prompt. A separate typed ngrok configuration is used, and agent authentication is checked before large model downloads.
1. **MuseTalk is enabled by default** for talking presenters. Leave **ENABLE_REALISTIC_PRESENTER** checked when running. This installs MuseTalk separately (several GB); no paid provider key. In SmartEdit choose Avatar explainer → AI talking avatar, then enter a topic. The image model creates the face automatically; no upload is needed. Run the 5-second test to review lip-sync. This animates the mouth, not head or body gestures.
1. Select a T4 GPU runtime (or larger). Add NGROK_AUTHTOKEN to Colab Secrets and enable notebook access.
2. Run the next cell in a fresh runtime. Choose `MOTION_ENGINE=auto` for automatic Wan selection, `ltx-13b` only on a supported A100-class runtime, or an explicit Wan option. Hinglish edit planning, images and Hindi/English voice startup tests must pass. Motion self-test is OFF by default so connecting does not render an unused clip. The first real motion request tests inference. Progress is printed in the cell.
3. Paste the complete private ONE-PASTE CONNECTION LINK into SmartEdit → Colab URL → Connect & Test. Keep the notebook and PC backend running.
4. Select **Hybrid** for one motion shot plus animated images, or **Full AI motion** for motion in every shot. Use **Image preview** to review the planned video first. Narration and subtitles are optional. Use **3D animation / avatar** for animated character topics.
5. If you enabled the optional startup test, review `/content/smartedit-motion-check.mp4`. A successful encode/decode is a functionality check; inspect it yourself for visual quality. Every ~5-second shot can take many minutes on free GPU.

| Runtime | Planner | Images | Motion |
|---|---|---|---|
| Free T4, ~15 GiB GPU / ~12 GiB RAM | Qwen3.5 9B | SDXL 1.0 | Wan2.1 1.3B, 480p-class / 16 fps |
| Native BF16, >=22 GiB GPU / >=32 GiB RAM | Qwen3.5 9B | FLUX.2 Klein 4B | Wan2.2 5B, 720p-class / 24 fps |
| >=30 GiB GPU / >=32 GiB RAM | Qwen3.5 27B | FLUX.2 Klein 4B if native BF16 | Wan2.2 5B if native BF16 |
| >=38 GiB native-BF16 GPU / >=48 GiB RAM | Qwen3.5 27B | FLUX.2 Klein 4B | optional LTX 0.9.8 13B image-to-video when explicitly selected |

These are conservative application selection rules, not measured memory guarantees. Lower-memory GPUs use Qwen3.5 4B; Wan motion is disabled below 14 GiB GPU or 11 GiB RAM. T4 uses FP32 Wan inference and an 8-bit text encoder released before the transformer loads; a measured balanced shot took about 46 minutes on the connected T4, so choose preview or Hybrid with one motion opening for shorter jobs. Models run sequentially. Do not force LTX or larger Wan models onto a T4.

Desktop speed presets are Fast draft (12 steps, 512x288, 49 frames), Balanced (30 steps, 640x352, 81 frames), and High detail (50 steps at native model size). Portrait/square equivalents are selected automatically. Optional environment variables before running the file: `SMARTEDIT_VIDEO_QUALITY=balanced` (30 steps), `SMARTEDIT_TEST_MOTION=1` (optional startup motion test; otherwise motion remains explicitly untested until generation), `SMARTEDIT_VIDEO_MODEL=wan2.1` or `wan2.2`, `SMARTEDIT_IMAGE_MODEL=sdxl` or `flux`, `SMARTEDIT_COLAB_MODEL=qwen3.5:4b`, `qwen3.5:9b` or `qwen3.5:27b`. Leave overrides unset for automatic selection.

1080p export resizes generated clips; native 1080p detail, character continuity and reference-video quality are not guaranteed. Wan has no native soundtrack or lip-sync; the MuseTalk presenter mode adds lip-sync to automatically generated portraits (and legacy saved presenter clips). Narration is separate, and music can be uploaded in the editor. The editor's AI text box uses the selected Qwen planner for supported timeline edits, not arbitrary video-to-video object/background replacement.
**Image story** uses SDXL or FLUX.2 for images with pan/zoom. Free Colab availability, disk space and session duration vary; no paid video API is used. Files and profiles have offline tests; live inference must pass on your Colab runtime.
"""
for cell in notebook['cells']:
    if cell['cell_type'] == 'code':
        cell.update(source=source.splitlines(keepends=True),
                    execution_count=None, outputs=[])
    elif cell['cell_type'] == 'markdown':
        cell['source'] = introduction.splitlines(keepends=True)
path.write_text(json.dumps(notebook, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
(root.parent/'Colab_Ollama_Setup.py').write_text(source, encoding='utf-8', newline='\n')
