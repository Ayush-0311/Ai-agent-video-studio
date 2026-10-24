"""Run this complete file in a Google Colab GPU cell (or %run the uploaded file).

Colab: Runtime > Change runtime type > T4 GPU. Add NGROK_AUTHTOKEN to
Colab Secrets, with notebook access enabled. No paid image API is required.
Models are selected for the detected GPU/RAM: T4 uses Qwen3.5 9B, SDXL and
Wan2.1 1.3B; larger native-BF16 GPUs can use Qwen3.5 27B, FLUX.2 Klein 4B
and Wan2.2 5B. Optional LTX 0.9.8 image-to-video is guarded to A100-class GPUs;
the default `auto` engine keeps T4 on Wan2.1. Motion self-test is opt-in.
Keep this cell running during production. See COLAB_SETUP_GUIDE.md for overrides.
Paste the printed ONE-PASTE CONNECTION LINK into SmartEdit's Colab URL box.
Neural speech defaults to isolated OmniVoice; final MP4 encoding runs on your PC.
"""
import gc
import base64
import io
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import threading
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Literal

MOTION_ENGINE = "auto" #@param ["auto", "ltx-13b", "wan2.1", "wan2.2"]
ENABLE_REALISTIC_PRESENTER = True #@param {type:"boolean"}
OMNIVOICE_SUPPORT_SOURCE = '"""Isolated upstream OmniVoice runtime. No VoiceStudio application dependency."""\nimport json\nimport os\nfrom pathlib import Path\nimport subprocess\nimport sys\nimport tempfile\n\nROOT = Path(\'/content/smartedit-omnivoice\')\nVERSION = \'0.2.1\'\nMODEL = \'k2-fsa/OmniVoice\'\nANCHORS = {\n    \'hi\': \'नमस्ते। आज हम एक नई कहानी सुनेंगे। आइए इस विषय को आसान भाषा में समझते हैं।\',\n    \'en\': \'Hello. Today we will explore a new story. Let us understand this topic together.\',\n    \'es\': \'Hola. Hoy vamos a explorar una nueva historia y aprender juntos.\',\n    \'fr\': \'Bonjour. Nous allons découvrir une nouvelle histoire et apprendre ensemble.\',\n    \'de\': \'Hallo. Heute entdecken wir eine neue Geschichte und lernen gemeinsam.\'}\n\n\ndef python_path():\n    return ROOT/\'venv/bin/python\'\n\n\ndef environment():\n    env = os.environ.copy()\n    for key in (\'PYTHONPATH\', \'PYTHONHOME\'):\n        env.pop(key, None)\n    env.update(PYTHONNOUSERSITE=\'1\', USE_TF=\'0\', USE_FLAX=\'0\', MPLBACKEND=\'Agg\',\n               HF_HUB_DISABLE_XET=\'1\', HF_ENABLE_PARALLEL_LOADING=\'false\')\n    return env\n\n\ndef run(args, timeout=1800):\n    ROOT.mkdir(parents=True, exist_ok=True)\n    log_path = ROOT/\'runtime.log\'\n    with log_path.open(\'a\', encoding=\'utf-8\') as log:\n        log.write(\'\\nOmniVoice operation starting\\n\')\n        log.flush()\n        try:\n            result = subprocess.run([str(x) for x in args], stdout=log, stderr=subprocess.STDOUT,\n                                    env=environment(), timeout=timeout)\n        except subprocess.TimeoutExpired:\n            raise RuntimeError(f\'OmniVoice timed out; worker stopped. Diagnostic: {log_path}\') from None\n    if result.returncode:\n        with log_path.open(\'rb\') as log:\n            log.seek(max(0, log_path.stat().st_size-6000))\n            detail = log.read().decode(\'utf-8\', errors=\'replace\')\n        print(detail, flush=True)\n        raise RuntimeError(f\'OmniVoice failed. Diagnostic: {log_path}\\n{detail[-2000:]}\')\n\n\ndef install(worker_source):\n    if sys.platform != \'linux\':\n        raise RuntimeError(\'Automatic OmniVoice installation requires the Colab Linux GPU runtime.\')\n    ROOT.mkdir(parents=True, exist_ok=True)\n    (ROOT/\'worker.py\').write_text(worker_source, encoding=\'utf-8\')\n    marker = ROOT/\'installed.json\'\n    expected = {\'omnivoice\': VERSION, \'torch\': \'2.8.0\', \'transformers\': \'5.3.0\'}\n    try:\n        reuse = json.loads(marker.read_text()) == expected and python_path().is_file()\n    except (OSError, ValueError):\n        reuse = False\n    marker.unlink(missing_ok=True)\n    if not reuse:\n        print(\'Installing OmniVoice in separate Python 3.11. Log: \'+str(ROOT/\'runtime.log\'), flush=True)\n        run([sys.executable, \'-m\', \'pip\', \'install\', \'uv==0.8.22\'])\n        if not python_path().exists():\n            run([sys.executable, \'-m\', \'uv\', \'venv\', \'--python\', \'3.11\', ROOT/\'venv\'])\n        py = python_path()\n        run([sys.executable, \'-m\', \'uv\', \'pip\', \'install\', \'--python\', py,\n             \'torch==2.8.0\', \'torchaudio==2.8.0\', \'--index-url\', \'https://download.pytorch.org/whl/cu128\'])\n        constraints = ROOT/\'constraints.txt\'\n        constraints.write_text(\'torch==2.8.0\\ntorchaudio==2.8.0\\ntransformers==5.3.0\\n\')\n        run([sys.executable, \'-m\', \'uv\', \'pip\', \'install\', \'--python\', py, \'-c\', constraints,\n             \'omnivoice==\'+VERSION, \'transformers==5.3.0\'])\n    run([python_path(), \'-c\', "import torch; from omnivoice import OmniVoice; "\n         "assert torch.cuda.is_available(), \'OmniVoice requires a GPU runtime\'; "\n         "x=torch.ones(1, device=\'cuda\'); torch.cuda.synchronize(); print(\'OmniVoice CUDA/imports passed\')"])\n    marker.write_text(json.dumps(expected))\n\n\nclass OmniVoiceService:\n    mode = \'omnivoice\'\n\n    def __init__(self, validate_audio):\n        self.validate_audio = validate_audio\n        self.providers = {}\n\n    def synthesize(self, text, language, selected, rate, startup=False):\n        if language not in (\'hi\', \'en\', \'es\', \'fr\', \'de\') or not text.strip() or len(text)>5000:\n            raise ValueError(\'Invalid narration language or text length.\')\n        gender = \'female\' if selected in (\'female\', \'hi-IN-SwaraNeural\', \'en-US-JennyNeural\',\n                    \'es-ES-ElviraNeural\', \'fr-FR-DeniseNeural\', \'de-DE-KatjaNeural\') else \'male\'\n        self.providers.pop(language, None)\n        with tempfile.TemporaryDirectory(prefix=\'speech-\', dir=ROOT) as directory:\n            work = Path(directory)\n            request = work/\'request.json\'\n            request.write_text(json.dumps({\'text\':text, \'language\':language, \'gender\':gender,\n                                           \'rate\':rate}), encoding=\'utf-8\')\n            print(f\'OmniVoice: generating {language} / {gender}. First use downloads model weights.\', flush=True)\n            run([python_path(), ROOT/\'worker.py\', request, work/\'speech.wav\'], timeout=1800 if startup else 900)\n            self.validate_audio(work/\'speech.wav\')\n            run([\'ffmpeg\', \'-y\', \'-v\', \'error\', \'-i\', work/\'speech.wav\', \'-codec:a\',\n                 \'libmp3lame\', \'-b:a\', \'192k\', work/\'speech.mp3\'], timeout=30)\n            self.validate_audio(work/\'speech.mp3\')\n            self.providers[language] = \'omnivoice\'\n            return (work/\'speech.mp3\').read_bytes(), MODEL+\'/\'+gender, \'omnivoice\'\n\n\ndef worker(request_path, output_path):\n    import numpy as np\n    import soundfile as sf\n    import torch\n    from huggingface_hub import snapshot_download\n    from omnivoice import OmniVoice, VoiceClonePrompt\n    request = json.loads(Path(request_path).read_text(encoding=\'utf-8\'))\n    torch.set_num_threads(2)\n    torch.manual_seed(42)\n    # Complete the serial download before allocating GPU weights.\n    model_marker = ROOT/\'model-path.json\'\n    try:\n        local = json.loads(model_marker.read_text())[\'path\']\n        if not (Path(local)/\'config.json\').is_file():\n            raise FileNotFoundError(\'Model cache no longer exists\')\n    except (OSError, ValueError, KeyError):\n        local = snapshot_download(MODEL, max_workers=1)\n        model_marker.write_text(json.dumps({\'path\':local}))\n    model = OmniVoice.from_pretrained(local, device_map=\'cuda:0\', dtype=torch.float16,\n                                     attn_implementation=\'sdpa\', load_asr=False)\n    # Reuse a self-generated reference instead of redesigning the narrator per scene.\n    profiles = ROOT/(\'profiles-\'+VERSION)\n    profiles.mkdir(parents=True, exist_ok=True)\n    profile = profiles/(request[\'language\']+\'-\'+request[\'gender\']+\'.pt\')\n    with torch.inference_mode():\n        if profile.exists():\n            prompt = VoiceClonePrompt.load(str(profile))\n        else:\n            anchor = ANCHORS[request[\'language\']]\n            reference = model.generate(text=anchor, language=request[\'language\'],\n                                       instruct=request[\'gender\'], num_step=32)[0]\n            reference = np.asarray(reference, dtype=np.float32).reshape(-1)\n            if not np.isfinite(reference).all() or reference.size < model.sampling_rate or np.max(np.abs(reference)) < .001:\n                raise RuntimeError(\'OmniVoice narrator reference is empty or silent.\')\n            with tempfile.TemporaryDirectory(prefix=\'reference-\', dir=ROOT) as folder:\n                path = Path(folder)/\'reference.wav\'\n                sf.write(str(path), reference, model.sampling_rate)\n                prompt = model.create_voice_clone_prompt(ref_audio=str(path), ref_text=anchor)\n            pending = profile.with_suffix(\'.partial\')\n            prompt.save(str(pending))\n            pending.replace(profile)\n        audio = model.generate(text=request[\'text\'], language=request[\'language\'],\n                               voice_clone_prompt=prompt, speed=1+request[\'rate\']/100,\n                               num_step=32)[0]\n    audio = np.asarray(audio, dtype=np.float32).reshape(-1)\n    if audio.size < model.sampling_rate/10 or not np.isfinite(audio).all():\n        raise RuntimeError(\'OmniVoice returned empty or invalid samples.\')\n    sf.write(str(output_path), audio, model.sampling_rate, subtype=\'PCM_16\')\n\n\nif __name__ == \'__main__\':\n    worker(sys.argv[1], sys.argv[2])\n'
VOICE_SUPPORT_SOURCE = '"""Validated Edge speech with a CPU MMS fallback, shared by notebook and worker."""\nimport array\nimport json\nimport os\nfrom pathlib import Path\nimport re\nimport subprocess\nimport sys\nimport tempfile\nimport threading\nimport time\nimport wave\n\nMMS_LANGUAGES = {\'en\': \'eng\', \'hi\': \'hin\', \'es\': \'spa\', \'fr\': \'fra\', \'de\': \'deu\'}\n\n\ndef chunks(text, limit=220):\n    text = re.sub(r\'\\s+\', \' \', text).strip()\n    if not text:\n        raise ValueError(\'Narration text is empty.\')\n    result = []\n    while text:\n        cut = len(text)\n        if cut > limit:\n            candidates = [m.end() for m in re.finditer(r\'[.!?।;]\\s|\\s\', text[:limit+1])]\n            cut = candidates[-1] if candidates else limit\n        result.append(text[:cut].strip())\n        text = text[cut:].strip()\n    return result\n\n\ndef validate_audio(path):\n    """Decode the whole clip and reject corrupt, empty or effectively silent audio."""\n    result = subprocess.run([\'ffmpeg\', \'-v\', \'error\', \'-xerror\', \'-i\', str(path),\n                             \'-ac\', \'1\', \'-ar\', \'16000\', \'-f\', \'s16le\', \'-\'],\n                            capture_output=True, timeout=15)\n    if result.returncode or len(result.stdout) < 3200:\n        raise RuntimeError(\'Speech audio is missing, too short or cannot be decoded.\')\n    samples = array.array(\'h\', result.stdout)\n    if sys.byteorder != \'little\':\n        samples.byteswap()\n    if max(abs(x) for x in samples) < 32:\n        raise RuntimeError(\'Speech provider returned silent audio.\')\n\n\nclass VoiceService:\n    def __init__(self, worker, log_path=\'/content/smartedit-voice.log\', mode=\'auto\'):\n        if mode not in (\'auto\', \'edge\', \'mms\'):\n            raise ValueError(\'SMARTEDIT_VOICE_ENGINE must be auto, edge or mms.\')\n        self.worker = str(worker)\n        self.log_path = Path(log_path)\n        self.mode = mode\n        self.lock = threading.Lock()\n        self.edge_retry_at = 0\n        self.providers = {}\n\n    def log(self, message):\n        # Never log input narration, tokens or full child tracebacks containing text.\n        print(\'[Voice] \'+message, flush=True)\n        self.log_path.parent.mkdir(parents=True, exist_ok=True)\n        with self.log_path.open(\'a\', encoding=\'utf-8\') as output:\n            output.write(time.strftime(\'%Y-%m-%d %H:%M:%S\')+\' \'+message+\'\\n\')\n\n    def run(self, command, timeout):\n        result = subprocess.run(command, capture_output=True, timeout=timeout,\n                                text=True, encoding=\'utf-8\', errors=\'replace\')\n        if result.returncode:\n            # Keep exception type and diagnostic, with bounded output.\n            detail = (result.stderr or result.stdout or \'No diagnostic returned\').strip().splitlines()[-1]\n            raise RuntimeError(detail[-1200:])\n\n    def synthesize(self, text, language, selected, rate, startup=False):\n        if language not in MMS_LANGUAGES or not text.strip() or len(text) > 5000:\n            raise ValueError(\'Use non-empty narration (up to 5000 characters) and a supported language.\')\n        with self.lock, tempfile.TemporaryDirectory(prefix=\'smartedit-voice-\') as directory:\n            work = Path(directory)\n            output = work/\'speech.mp3\'\n            source = work/\'text.txt\'\n            source.write_text(text, encoding=\'utf-8\')\n            failures = []\n            if self.mode != \'mms\' and (self.mode == \'edge\' or time.monotonic() >= self.edge_retry_at):\n                for attempt in range(2):\n                    try:\n                        output.unlink(missing_ok=True)\n                        self.run([sys.executable, \'-m\', \'edge_tts\', \'--voice\', selected,\n                                  \'--file\', str(source), f\'--rate={rate:+d}%\',\n                                  \'--write-media\', str(output)], 35)\n                        validate_audio(output)\n                        self.providers[language] = \'edge-tts\'\n                        return output.read_bytes(), selected, \'edge-tts\'\n                    except (RuntimeError, OSError, subprocess.TimeoutExpired) as exc:\n                        detail = str(exc).replace(text, \'[narration]\')\n                        # TimeoutExpired includes argv, which contains only the text file path.\n                        failures.append(\'Edge: \'+detail[-1200:])\n                        self.log(f\'Edge attempt {attempt+1} failed: \'+detail[-1200:])\n                self.edge_retry_at = time.monotonic()+600\n            if self.mode != \'edge\':\n                model = \'facebook/mms-tts-\'+MMS_LANGUAGES[language]\n                self.log(f\'Using {model} on CPU (CC-BY-NC-4.0; fixed voice, gender selection unavailable).\')\n                request = work/\'request.json\'\n                request.write_text(json.dumps({\'text\': text, \'language\': language, \'rate\': rate}), encoding=\'utf-8\')\n                try:\n                    self.run([sys.executable, self.worker, str(request), str(work/\'speech.wav\')],\n                             900 if startup else 150)\n                    self.run([\'ffmpeg\', \'-y\', \'-v\', \'error\', \'-i\', str(work/\'speech.wav\'),\n                              \'-af\', f\'atempo={1+rate/100:.2f}\', \'-codec:a\', \'libmp3lame\',\n                              \'-b:a\', \'128k\', str(output)], 30)\n                    validate_audio(output)\n                    self.providers[language] = \'mms\'\n                    return output.read_bytes(), model, \'mms\'\n                except (RuntimeError, OSError, subprocess.TimeoutExpired) as exc:\n                    detail = str(exc).replace(text, \'[narration]\')\n                    failures.append(\'MMS: \'+detail[-1200:])\n                    self.log(\'MMS failed: \'+detail[-1200:])\n            self.providers.pop(language, None)\n            raise RuntimeError(\'Voice generation failed. \'+ \' | \'.join(failures)\n                               +f\' Full diagnostic: {self.log_path}\')\n\n\ndef mms_worker(request_path, output_path):\n    # A short-lived CPU process releases model RAM after every request.\n    os.environ.update(CUDA_VISIBLE_DEVICES=\'\', USE_TF=\'0\', USE_FLAX=\'0\', HF_HUB_DISABLE_XET=\'1\')\n    import numpy as np\n    import torch\n    from transformers import AutoTokenizer, VitsModel\n    from huggingface_hub import snapshot_download\n    torch.set_num_threads(2)\n    request = json.loads(Path(request_path).read_text(encoding=\'utf-8\'))\n    model_id = \'facebook/mms-tts-\'+MMS_LANGUAGES[request[\'language\']]\n    patterns = [\'*.json\', \'model.safetensors\']\n    try:\n        local = snapshot_download(model_id, local_files_only=True, allow_patterns=patterns)\n        if not all((Path(local)/name).is_file() for name in\n                   (\'model.safetensors\', \'config.json\', \'tokenizer_config.json\', \'vocab.json\')):\n            raise FileNotFoundError(\'Incomplete voice model cache\')\n    except (OSError, ValueError):\n        local = snapshot_download(model_id, max_workers=1, allow_patterns=patterns)\n    tokenizer = AutoTokenizer.from_pretrained(local, local_files_only=True)\n    model = VitsModel.from_pretrained(local, local_files_only=True, use_safetensors=True).cpu().eval()\n    torch.manual_seed(42)\n    with wave.open(str(output_path), \'wb\') as audio:\n        audio.setnchannels(1)\n        audio.setsampwidth(2)\n        audio.setframerate(model.config.sampling_rate)\n        for text in chunks(request[\'text\']):\n            inputs = tokenizer(text, return_tensors=\'pt\')\n            if inputs[\'input_ids\'].numel() < 2:\n                raise RuntimeError(\'Text is unsupported by this voice tokenizer; use the selected language script.\')\n            with torch.inference_mode():\n                data = model(**inputs).waveform.squeeze().float().numpy()\n            if not np.isfinite(data).all() or data.size == 0:\n                raise RuntimeError(\'MMS returned invalid audio samples.\')\n            audio.writeframes((np.clip(data, -1, 1)*32767).astype(\'<i2\').tobytes())\n            audio.writeframes(bytes(int(model.config.sampling_rate*.12)*2))\n\n\nif __name__ == \'__main__\':\n    mms_worker(sys.argv[1], sys.argv[2])\n'
# Optional runtime source is embedded by scripts/sync_colab_notebook.py.
LTX_SUPPORT_SOURCE = '"""LTX 0.9.8 13B distilled image-to-video, embedded in the standalone notebook.\n\nSingle-pass schedule follows Lightricks\' distilled demo/config. This is not\nthe optional multi-scale upsampler. Dependencies are imported only on Colab.\n"""\nimport base64\nimport io\nimport time\n\nMODEL = \'Lightricks/LTX-Video-0.9.8-13B-distilled\'\n# Official first_pass timesteps, in Diffusers\' 0..1000 units.\n# https://github.com/Lightricks/LTX-Video/blob/main/configs/ltxv-13b-0.9.8-distilled.yaml\nTIMESTEPS = [1000.0, 993.7, 987.5, 981.2, 975.0, 909.4, 725.0]\n\n\ndef profile(vram_gb, ram_gb, native_bf16):\n    # Conservative application guard for unquantized BF16 + model CPU offload.\n    # This is not a measured minimum or a promise that every workload will fit.\n    available = native_bf16 and vram_gb >= 38 and ram_gb >= 48\n    return {\'available\': available, \'engine\': \'ltx-13b\', \'family\': \'ltx\',\n            \'image_to_video\': True, \'model\': MODEL, \'dtype\': \'bfloat16\',\n            \'frames\': 161, \'fps\': 30, \'steps\': len(TIMESTEPS), \'guidance\': 1.0,\n            \'sizes\': {\'16:9\': (1216, 704), \'9:16\': (704, 1216), \'1:1\': (832, 832)},\n            \'quality\': \'quality\', \'native_resolution\': \'704p-class\',\n            \'unavailable_reason\': \'\' if available else\n                \'LTX 13B BF16 in this setup requires native BF16, at least 38 GiB GPU memory \'\n                \'and 48 GiB system RAM (A100-class Colab). Choose a larger runtime or explicitly select Wan.\'}\n\n\ndef settings(profile, preset):\n    if preset not in (\'preview\', \'balanced\', \'quality\'):\n        raise ValueError(\'Choose preview, balanced or quality motion.\')\n    result = dict(profile, quality=preset)\n    # Keep the distilled schedule intact. Speed presets change pixels/frames.\n    if preset == \'preview\':\n        result.update(frames=97, sizes={\'16:9\': (512, 288), \'9:16\': (288, 512), \'1:1\': (384, 384)},\n                      native_resolution=\'288p-class preview\')\n    elif preset == \'balanced\':\n        result.update(sizes={\'16:9\': (832, 480), \'9:16\': (480, 832), \'1:1\': (640, 640)},\n                      native_resolution=\'480p-class balanced\')\n    return result\n\n\ndef decode_image(encoded):\n    from PIL import Image\n    if not encoded or len(encoded) > 8000000:\n        raise ValueError(\'LTX motion requires a scene image (maximum 8 MB base64). Update the desktop app.\')\n    try:\n        with Image.open(io.BytesIO(base64.b64decode(encoded, validate=True))) as source:\n            if source.width * source.height > 1536 * 1536 or min(source.size) < 64:\n                raise ValueError(\'Unsupported dimensions\')\n            source.load()\n            return source.convert(\'RGB\')\n    except Exception as exc:\n        raise ValueError(\'Invalid LTX scene image. Use a PNG/JPEG up to 1536 x 1536 pixels.\') from exc\n\n\ndef generate(state, folder, payload, options, progress):\n    """Caller owns the shared GPU lock and releases other model families first."""\n    import torch\n    from PIL import Image, ImageOps\n    from diffusers import LTXConditionPipeline\n\n    image = decode_image(payload.get(\'source_image\', \'\'))\n    width, height = options[\'sizes\'][payload[\'aspect_ratio\']]\n    image = ImageOps.fit(image, (width, height), method=Image.Resampling.LANCZOS)\n    if state[\'motion_pipe\'] is None:\n        progress(\'Loading LTX 13B distilled from cache; BF16 with model CPU offload\')\n        pipe = LTXConditionPipeline.from_pretrained(folder, torch_dtype=torch.bfloat16,\n            low_cpu_mem_usage=True, local_files_only=True, use_safetensors=True)\n        pipe.vae.enable_tiling()\n        pipe.enable_model_cpu_offload()\n        state[\'motion_pipe\'] = pipe\n    pipe = state[\'motion_pipe\']\n    progress(f"LTX image-to-video: {width}x{height}, {options[\'frames\']} frames, {len(TIMESTEPS)} distilled steps")\n    started = time.monotonic()\n\n    def on_step(pipeline, step, timestep, tensors):\n        elapsed = time.monotonic() - started\n        remaining = elapsed / (step + 1) * (len(TIMESTEPS) - step - 1)\n        progress(f\'Generating motion: step {step+1}/{len(TIMESTEPS)} · \'\n                 f\'estimated {remaining/60:.1f} min left in this shot\')\n        return tensors\n\n    with torch.inference_mode():\n        return pipe(image=image, frame_index=0, strength=1.0, prompt=payload[\'prompt\'],\n            width=width, height=height, num_frames=options[\'frames\'], frame_rate=options[\'fps\'],\n            timesteps=TIMESTEPS, num_inference_steps=len(TIMESTEPS), guidance_scale=1.0,\n            decode_timestep=0.05, decode_noise_scale=0.025, image_cond_noise_scale=0.15,\n            generator=torch.Generator(\'cpu\').manual_seed(payload[\'seed\']),\n            callback_on_step_end=on_step, output_type=\'np\').frames[0]\n'
LTX_RUNTIME = {'__name__': 'smartedit_ltx_runtime'}
exec(compile(LTX_SUPPORT_SOURCE, 'ltx_support.py', 'exec'), LTX_RUNTIME)
MUSETALK_SUPPORT_SOURCE = '"""Optional isolated MuseTalk 1.5 runtime for the SmartEdit Colab bridge.\nNo provider API key. This module uses only the standard library until setup.\n"""\nimport base64\nfrom collections import deque\nimport json\nimport os\nfrom pathlib import Path\nimport shutil\nimport subprocess\nimport sys\nimport tempfile\nimport time\nimport uuid\n\nREVISION = \'0a89dec45a0192b824e3cf4daf96c239440c5ed8\'\nINSTALLER_VERSION = \'2026-10-11.2\'\nROOT = Path(\'/content/smartedit-musetalk\')\nCHECKPOINTS = (\'musetalkV15/unet.pth\',\'musetalkV15/musetalk.json\',\n    \'sd-vae/config.json\',\'sd-vae/diffusion_pytorch_model.bin\',\n    \'whisper/config.json\',\'whisper/pytorch_model.bin\',\'whisper/preprocessor_config.json\',\n    \'dwpose/dw-ll_ucoco_384.pth\',\'face-parse-bisent/79999_iter.pth\',\n    \'face-parse-bisent/resnet18-5c106cde.pth\')\n\n\ndef python_path():\n    return ROOT/\'venv/bin/python\'\n\n\ndef child_environment():\n    """Keep notebook-specific imports and plotting backends out of GPU workers."""\n    env = os.environ.copy()\n    for name in (\'PYTHONPATH\', \'PYTHONHOME\'):\n        env.pop(name, None)\n    env.update(PYTHONNOUSERSITE=\'1\', PYTHONUNBUFFERED=\'1\', MPLBACKEND=\'Agg\')\n    return env\n\n\ndef run(args, cwd=None, stage=\'MuseTalk setup\'):\n    """Surface child stderr in notebooks and retain diagnostics across reruns."""\n    ROOT.mkdir(parents=True, exist_ok=True)\n    log_path = ROOT/\'setup.log\'\n    tail = deque(maxlen=60)\n    env = child_environment()\n    print(f\'\\n[MuseTalk] {stage}\', flush=True)\n    with log_path.open(\'a\', encoding=\'utf-8\') as log:\n        log.write(f\'\\n[{time.strftime("%Y-%m-%d %H:%M:%S")}] {stage}\\n\')\n        log.flush()\n        process = subprocess.Popen([str(x) for x in args], cwd=cwd, env=env,\n                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT,\n                                   text=True, encoding=\'utf-8\', errors=\'replace\', bufsize=1)\n        try:\n            for line in process.stdout:\n                print(line, end=\'\', flush=True)\n                log.write(line)\n                log.flush()\n                tail.append(line[-2000:])\n            code = process.wait()\n        finally:\n            process.stdout.close()\n            if process.poll() is None:\n                process.terminate()\n                try:\n                    process.wait(timeout=10)\n                except subprocess.TimeoutExpired:\n                    process.kill()\n                    process.wait()\n    if code:\n        detail = \'\'.join(tail)[-8000:]\n        raise RuntimeError(f\'{stage} failed (exit {code}). Full log: {log_path}\\n{detail}\')\n\n\ndef verify_runtime():\n    run([python_path(), \'-c\',\n         "import torch; print(\'Torch:\', torch.__version__, \'CUDA:\', torch.version.cuda, flush=True); "\n         "assert torch.cuda.is_available(), \'CUDA unavailable in MuseTalk Python; select a GPU runtime\'; "\n         "print(\'GPU:\', torch.cuda.get_device_name(0), flush=True); "\n         "x = torch.ones(1, device=\'cuda\'); torch.cuda.synchronize()"],\n        stage=\'Checking isolated CUDA runtime\')\n\n\ndef verify_imports():\n    # Upstream preprocessing loads DWPose on import, so this runs after downloads.\n    run([python_path(), \'-c\', "import scripts.inference; print(\'MuseTalk imports passed\', flush=True)"],\n        ROOT/\'repo\', stage=\'Loading MuseTalk and face detection checkpoints\')\n\n\ndef check():\n    try:\n        verified = json.loads((ROOT/\'verified.json\').read_text())\n        return (verified.get(\'revision\') == REVISION and\n                verified.get(\'installer_version\') == INSTALLER_VERSION and python_path().is_file() and\n                all((ROOT/\'repo/models\'/name).is_file() and (ROOT/\'repo/models\'/name).stat().st_size>10 for name in CHECKPOINTS))\n    except (OSError,ValueError):\n        return False\n\n\ndef install():\n    if check():\n        (ROOT/\'verified.json\').unlink(missing_ok=True)\n        verify_runtime()\n        verify_imports()\n        write_verified()\n        print(\'Reusing isolated MuseTalk installation.\',flush=True)\n        return\n    if sys.platform != \'linux\':\n        raise RuntimeError(\'This automatic installer is for Google Colab Linux GPU runtimes.\')\n    if shutil.disk_usage(\'/content\').free < 12*1024**3:\n        raise RuntimeError(\'MuseTalk setup needs at least 12 GiB free disk. Use a fresh Colab runtime.\')\n    ROOT.mkdir(parents=True,exist_ok=True)\n    (ROOT/\'verified.json\').unlink(missing_ok=True)\n    print(\'Installing optional MuseTalk in its own Python 3.10 environment. First setup downloads several GB.\',flush=True)\n    run([sys.executable,\'-m\',\'pip\',\'install\',\'uv==0.8.22\'])\n    if not python_path().exists():\n        run([sys.executable,\'-m\',\'uv\',\'venv\',\'--python\',\'3.10\',str(ROOT/\'venv\')])\n    py = python_path()\n    run([sys.executable,\'-m\',\'uv\',\'pip\',\'install\',\'--python\',py,\'pip==24.3.1\',\'setuptools==69.5.1\',\'wheel\'])\n    repo = ROOT/\'repo\'\n    if not (repo/\'.git\').exists():\n        run([\'git\',\'clone\',\'--filter=blob:none\',\'--no-checkout\',\'https://github.com/TMElyralab/MuseTalk.git\',repo])\n    run([\'git\',\'checkout\',REVISION],repo)\n    run([py,\'-m\',\'pip\',\'install\',\'torch==2.0.1\',\'torchvision==0.15.2\',\'torchaudio==2.0.2\',\'--index-url\',\'https://download.pytorch.org/whl/cu118\'])\n    verify_runtime()\n    # Inference-only environment; avoid Gradio/TensorFlow dependencies that conflict\n    # with the modern SDXL/FLUX environment in the parent notebook.\n    run([py,\'-m\',\'pip\',\'install\',\'numpy==1.23.5\',\'diffusers==0.30.2\',\'accelerate==0.28.0\',\n        \'opencv-python==4.9.0.80\',\'soundfile==0.12.1\',\'transformers==4.39.2\',\'huggingface-hub==0.30.2\',\n        \'librosa==0.11.0\',\'einops==0.8.1\',\'omegaconf==2.3.0\',\'ffmpeg-python==0.2.0\',\n        \'imageio[ffmpeg]\',\'gdown==5.2.0\',\'requests\',\'numba==0.60.0\',\'mmengine==0.10.7\'])\n    constraints = ROOT/\'constraints.txt\'\n    constraints.write_text(\'numpy==1.23.5\\ntorch==2.0.1\\ntorchvision==0.15.2\\ntorchaudio==2.0.2\\nopencv-python==4.9.0.80\\n\')\n    run([py,\'-m\',\'pip\',\'install\',\'-c\',constraints,\'mmcv==2.0.1\',\'--only-binary=mmcv\',\'-f\',\n         \'https://download.openmmlab.com/mmcv/dist/cu118/torch2.0/index.html\'])\n    run([py,\'-m\',\'pip\',\'install\',\'-c\',constraints,\'mmdet==3.1.0\',\'mmpose==1.1.0\'])\n    run([py,\'-m\',\'pip\',\'check\'])\n    run([py, \'-c\', \'import numpy, cv2, diffusers, transformers, librosa; import mmcv.ops; import mmpose.apis\'],\n        repo, stage=\'Checking Python dependencies and compiled MMCV operators\')\n    downloader = r\'\'\'\nfrom pathlib import Path\nfrom huggingface_hub import snapshot_download\nimport gdown, urllib.request\nroot = Path(\'models\')\nfor repo, folder, names in [\n (\'TMElyralab/MuseTalk\',\'\',[\'musetalkV15/unet.pth\',\'musetalkV15/musetalk.json\']),\n (\'stabilityai/sd-vae-ft-mse\',\'sd-vae\',[\'config.json\',\'diffusion_pytorch_model.bin\']),\n (\'openai/whisper-tiny\',\'whisper\',[\'config.json\',\'pytorch_model.bin\',\'preprocessor_config.json\']),\n (\'yzd-v/DWPose\',\'dwpose\',[\'dw-ll_ucoco_384.pth\'])]:\n snapshot_download(repo,local_dir=str(root/folder),allow_patterns=names,max_workers=1)\nface=root/\'face-parse-bisent\'; face.mkdir(parents=True,exist_ok=True)\nif not (face/\'79999_iter.pth\').exists():\n target=face/\'79999_iter.partial\'\n if not gdown.download(id=\'154JgKpzCPW82qINcVieuPH3fZ2e0P812\',output=str(target),quiet=False):\n  raise RuntimeError(\'Face parsing checkpoint download failed; rerun setup.\')\n target.replace(face/\'79999_iter.pth\')\nif not (face/\'resnet18-5c106cde.pth\').exists():\n target=face/\'resnet18.partial\'\n urllib.request.urlretrieve(\'https://download.pytorch.org/models/resnet18-5c106cde.pth\',target)\n target.replace(face/\'resnet18-5c106cde.pth\')\n\'\'\'\n    run([py,\'-c\',downloader],repo,stage=\'Downloading or reusing MuseTalk checkpoints\')\n    verify_imports()\n    if not all((repo/\'models\'/p).is_file() and (repo/\'models\'/p).stat().st_size>10 for p in CHECKPOINTS):\n        raise RuntimeError(\'A MuseTalk checkpoint did not download. Rerun setup.\')\n    write_verified()\n    print(\'MuseTalk dependencies ready; run the 5-second presenter test in SmartEdit to verify inference.\',flush=True)\n\n\ndef write_verified():\n    (ROOT/\'verified.json\').write_text(json.dumps({\'revision\': REVISION,\n        \'installer_version\': INSTALLER_VERSION, \'inference_tested\': False}))\n\n\ndef decode_media(value,limit):\n    if not isinstance(value,str) or len(value)>limit*4//3+4:\n        raise ValueError(\'Presenter media exceeds the upload limit.\')\n    try:\n        result=base64.b64decode(value,validate=True)\n    except Exception as exc:\n        raise ValueError(\'Invalid presenter media encoding.\') from exc\n    if not result or len(result)>limit:\n        raise ValueError(\'Empty or oversized presenter media.\')\n    return result\n\n\ndef infer(payload,progress):\n    if not check():\n        raise RuntimeError(\'MuseTalk is not installed. Enable realistic presenter in the notebook and rerun.\')\n    repo=ROOT/\'repo\'\n    runs=repo/\'smartedit_runs\';runs.mkdir(exist_ok=True)\n    with tempfile.TemporaryDirectory(prefix=\'job_\',dir=runs) as directory:\n        work=Path(directory)\n        (work/\'source.mp4\').write_bytes(decode_media(payload[\'video\'],21_000_000))\n        (work/\'audio.wav\').write_bytes(decode_media(payload[\'audio\'],6_000_000))\n        # Upstream uses shell-based FFmpeg: only generated relative ASCII paths\n        # are handed to it. User filenames and commands never enter those strings.\n        relative=work.relative_to(repo).as_posix()\n        def probe(file):\n            return json.loads(subprocess.check_output([\'ffprobe\',\'-v\',\'error\',\'-show_streams\',\'-show_format\',\'-of\',\'json\',str(file)]))\n        source=probe(work/\'source.mp4\'); audio=probe(work/\'audio.wav\')\n        video=next((s for s in source[\'streams\'] if s[\'codec_type\']==\'video\'),None)\n        duration=float(audio[\'format\'][\'duration\'])\n        if not video or max(video[\'width\'],video[\'height\'])>512 or not 2<=float(source[\'format\'][\'duration\'])<=30.1:\n            raise ValueError(\'Use a normalized presenter clip between 2 and 30 seconds.\')\n        if not .1<=duration<=180 or not any(s[\'codec_type\']==\'audio\' for s in audio[\'streams\']):\n            raise ValueError(\'Invalid presenter narration duration.\')\n        config={\'presenter\':{\'video_path\':relative+\'/source.mp4\',\'audio_path\':relative+\'/audio.wav\',\'result_name\':\'result.mp4\'}}\n        (work/\'task.json\').write_text(json.dumps(config))\n        args=[str(python_path()),\'-m\',\'scripts.inference\',\'--inference_config\',relative+\'/task.json\',\n              \'--result_dir\',relative+\'/output\',\'--unet_model_path\',\'models/musetalkV15/unet.pth\',\n              \'--unet_config\',\'models/musetalkV15/musetalk.json\',\'--version\',\'v15\',\n              \'--use_float16\',\'--batch_size\',\'2\',\'--fps\',\'25\']\n        progress(\'Loading MuseTalk and checking the presenter face. Animating the mouth to match narration.\')\n        with (work/\'inference.log\').open(\'w\') as log:\n            process=subprocess.Popen(args,cwd=repo,stdout=log,stderr=subprocess.STDOUT,\n                                     env=child_environment())\n            started=time.monotonic()\n            try:\n                while process.poll() is None:\n                    if time.monotonic()-started>3500:\n                        raise RuntimeError(\'MuseTalk timed out. Try a shorter presenter test.\')\n                    progress(f\'Lip-sync generation running: {int(time.monotonic()-started)} seconds elapsed.\')\n                    time.sleep(2)\n                if process.returncode:\n                    raise RuntimeError(\'MuseTalk inference failed. Check Colab GPU memory and use a clear face clip.\')\n            finally:\n                if process.poll() is None:\n                    process.terminate()\n                    try: process.wait(timeout=10)\n                    except subprocess.TimeoutExpired:\n                        process.kill();process.wait()\n        result=work/\'output/v15/result.mp4\'\n        # Upstream can catch exceptions and exit zero: validate the actual file.\n        if not result.is_file():\n            raise RuntimeError(\'MuseTalk produced no video. Use one clearly visible face, with no cuts or occlusion.\')\n        info=probe(result)\n        if abs(float(info[\'format\'][\'duration\'])-duration)>.25 or not any(s[\'codec_type\']==\'video\' for s in info[\'streams\']):\n            raise RuntimeError(\'MuseTalk output failed the duration/video check.\')\n        subprocess.run([\'ffmpeg\',\'-v\',\'error\',\'-xerror\',\'-i\',str(result),\'-f\',\'null\',\'-\'],check=True,timeout=180)\n        progress(\'Presenter clip encoded and validated.\')\n        return result.read_bytes()\n'

IMAGE_MODEL = 'stabilityai/stable-diffusion-xl-base-1.0'
VIDEO_MODEL = 'Wan-AI/Wan2.1-T2V-1.3B-Diffusers'
VIDEO_MODEL_HD = 'Wan-AI/Wan2.2-TI2V-5B-Diffusers'
IMAGE_MODEL_FLUX = 'black-forest-labs/FLUX.2-klein-4B'
PORT = 7860
# Keep the shared Hub requirement compatible across the two Hugging Face libraries.
# Diffusers 0.40 requires Hub >=1.23; Transformers 4 requires Hub <1.
COLAB_REQUIREMENTS = (
    'fastapi>=0.115,<1', 'uvicorn>=0.30,<1', 'pyngrok==7.5.1',
    'diffusers==0.37.1', 'transformers==4.57.6', 'huggingface-hub==0.36.2',
    'accelerate==1.12.0', 'bitsandbytes==0.49.2', 'sentencepiece==0.2.1',
    'safetensors>=0.5,<1', 'requests>=2.32,<3', 'ftfy>=6,<7',
    'imageio[ffmpeg]>=2.37,<3', 'edge-tts>=7.2.8,<8', 'numpy>=1.26,<3',
    'scipy>=1.13,<2',
)


def configure_low_memory_downloads():
    # Set before HF/Transformers imports, including the installer import probe.
    # HTTP streams files to disk; Xet's concurrent reconstruction is unnecessary
    # on a 12 GiB Colab runtime. Model shard loading must also stay serial.
    os.environ.update(HF_HUB_DISABLE_XET='1', HF_HUB_ENABLE_HF_TRANSFER='0',
                      HF_ENABLE_PARALLEL_LOADING='false', HF_PARALLEL_LOADING_WORKERS='1',
                      USE_TF='0', USE_FLAX='0')
    # A rerun may already have imported Hub constants with the previous settings.
    constants = sys.modules.get('huggingface_hub.constants')
    if constants is not None:
        constants.HF_HUB_DISABLE_XET = True
        constants.HF_HUB_ENABLE_HF_TRANSFER = False


def model_download_patterns(family):
    if family not in ('sdxl', 'flux', 'wan', 'ltx'):
        raise ValueError('Unknown model download family: '+family)
    components = ('text_encoder', 'text_encoder_2', 'tokenizer', 'tokenizer_2',
                  'scheduler', 'vae', 'unet' if family == 'sdxl' else 'transformer')
    # Avoid original checkpoints, ONNX/Flax copies and unused SDXL FP32 weights.
    suffixes = ('*.json', '*.txt', '*.model', '*.fp16.safetensors' if family == 'sdxl' else '*.safetensors')
    patterns = ['model_index.json', *[f'{component}/{suffix}' for component in components for suffix in suffixes]]
    if family == 'ltx':
        patterns.append('LTX-Video-Open-Weights-License-0.X.txt')
    return patterns


def download_model_serially(model_id, family, progress=print):
    configure_low_memory_downloads()
    from huggingface_hub import snapshot_download
    if family == 'ltx':
        preflight_ltx_disk(model_id)
    progress(f'Downloading {model_id}: ONE file at a time; existing cached files are reused')
    folder = snapshot_download(model_id, allow_patterns=model_download_patterns(family), max_workers=1)
    progress(f'Download complete: {model_id}. Loading will use local files only.')
    return folder


def preflight_ltx_disk(model_id, free_bytes=None, api=None, reserve_bytes=8*1024**3):
    """Reject an LTX download before it can fill Colab's disk with partial shards."""
    import fnmatch
    if api is None:
        from huggingface_hub import HfApi
        api = HfApi()
    patterns = model_download_patterns('ltx')
    info = api.model_info(model_id, files_metadata=True)
    files = [item for item in info.siblings
             if any(fnmatch.fnmatchcase(item.rfilename, pattern) for pattern in patterns)]
    if not files or any(not isinstance(item.size, int) or item.size <= 0 for item in files):
        raise RuntimeError('Could not verify LTX model download size. No files were downloaded; check the Colab network and retry.')
    required = sum(item.size for item in files)
    free = shutil.disk_usage('/content').free if free_bytes is None else free_bytes
    if free < required + reserve_bytes:
        raise RuntimeError(f'LTX needs about {required/1024**3:.1f} GiB for selected model files plus '
            f'{reserve_bytes/1024**3:.0f} GiB working reserve; this Colab runtime has only {free/1024**3:.1f} GiB free. '
            'No model files were downloaded. Use a runtime with more disk or select Wan.')
    return required


def release_model_memory(torch):
    gc.collect()
    torch.cuda.empty_cache()
    # Return freed CPU heap pages to Linux after a model is discarded.
    if sys.platform == 'linux':
        import ctypes
        try:
            ctypes.CDLL(None).malloc_trim(0)
        except (AttributeError, OSError):
            pass


def validate_ngrok_token(value):
    """Reject structured inputs without exposing a credential in an exception."""
    if not isinstance(value, str):
        raise ValueError('NGROK_AUTHTOKEN must be plain text, not a dictionary/list or other object.')
    token = value.strip()
    if (not token or not token.isascii() or any(c.isspace() for c in token)
            or any(c in token for c in '{}[]\"\':/\\')):
        raise ValueError('Paste only the ngrok authtoken value, without JSON, quotes, a URL or a shell command.')
    return token


def read_ngrok_token(secret_getter=None, prompt=None):
    """Use Colab Secrets, recovering bad/missing values through a hidden prompt."""
    value = os.environ.get('NGROK_AUTHTOKEN')
    if value is None:
        try:
            if secret_getter is None:
                from google.colab import userdata
                secret_getter = userdata.get
            value = secret_getter('NGROK_AUTHTOKEN')
        except Exception:
            value = None
    try:
        return validate_ngrok_token(value)
    except ValueError:
        print('NGROK_AUTHTOKEN is missing or has an invalid format. Enter only the plain authtoken below.', flush=True)
    if prompt is None:
        from getpass import getpass
        prompt = getpass
    for _ in range(2):
        try:
            return validate_ngrok_token(prompt('Paste ngrok authtoken only (hidden): '))
        except ValueError as exc:
            print(str(exc), flush=True)
    raise RuntimeError('Set NGROK_AUTHTOKEN in Colab Secrets to the plain token text, enable notebook access, '
                       'then rerun. Do not paste a dictionary or the ngrok config command.') from None


def ngrok_error_details(exc, token):
    """Retain actionable library/CLI output while removing the credential."""
    parts = [f'{type(exc).__name__}: {exc}']
    for name in ('ngrok_error', 'stderr', 'output'):
        value = getattr(exc, name, None)
        if value:
            if isinstance(value, bytes):
                value = value.decode('utf-8', errors='replace')
            parts.append(str(value))
    return '\n'.join(dict.fromkeys(parts)).replace(token, '[REDACTED]')[-16000:]


def prepare_ngrok(token, directory='/content/.smartedit-ngrok'):
    """Check the agent before large downloads, using our own typed configuration."""
    token = validate_ngrok_token(token)
    from pyngrok import conf, ngrok
    folder = Path(directory)
    folder.mkdir(parents=True, exist_ok=True)
    # Do not inherit a default config mutated by a previous notebook cell.
    # pyngrok 7.x requires "v3"; "3" is an incompatible 8.x convention.
    config = conf.PyngrokConfig(ngrok_path=str(folder/'ngrok'), config_path=str(folder/'ngrok.yml'),
                               auth_token=token, ngrok_version='v3', config_version='2', startup_timeout=60)
    print('Checking ngrok authentication before model downloads', flush=True)
    stage = 'installing ngrok and saving its configuration'
    try:
        ngrok.set_auth_token(token, pyngrok_config=config)
        stage = 'starting and authenticating the ngrok agent'
        ngrok.get_ngrok_process(pyngrok_config=config)
    except Exception as exc:
        detail = ngrok_error_details(exc, token)
        diagnostic = f'Ngrok failed while {stage}.\n{detail}\nNo model downloads have started.'
        log_path = folder/'startup-error.log'
        try:
            log_path.write_text(diagnostic+'\n', encoding='utf-8')
            diagnostic += f'\nDiagnostic log (token redacted): {log_path}'
        except OSError:
            pass  # Keep the original failure if writing its diagnostic also fails.
        raise RuntimeError(diagnostic) from None
    print('Ngrok agent connected. Continuing with model setup.', flush=True)
    return config


def run_setup_step(command, log_path, label):
    """Stream the actual diagnostic and preserve it instead of a bare subprocess error."""
    from collections import deque
    tail = deque(maxlen=25)
    print(label, flush=True)
    with Path(log_path).open('a', encoding='utf-8') as log:
        log.write('\n'+label+'\n')
        with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              text=True, encoding='utf-8', errors='replace', bufsize=1) as process:
            for line in process.stdout:
                print(line, end='', flush=True)
                log.write(line); log.flush(); tail.append(line)
            code = process.wait()
    if code:
        raise RuntimeError(f'{label} failed (exit {code}). Read the setup error above. '
                           f'Full log: {log_path}\n'+''.join(tail))


def install_ollama(log_path='/content/smartedit-install.log'):
    """Prepare Colab's OS tools before running the official Linux installer."""
    import requests
    if sys.platform != 'linux':
        raise RuntimeError('Run this setup in a Google Colab Linux GPU runtime.')
    # Recent official archives are .tar.zst. The installer exits immediately
    # when zstd is missing; pip cannot install this OS command for us.
    packages = {'curl':'curl', 'zstd':'zstd', 'tar':'tar', 'awk':'mawk',
                'grep':'grep', 'sed':'sed', 'tee':'coreutils', 'xargs':'findutils',
                'ffmpeg':'ffmpeg'}
    missing = sorted({package for command, package in packages.items() if not shutil.which(command)})
    if missing:
        if not shutil.which('apt-get'):
            raise RuntimeError('Missing Ollama system packages: '+', '.join(missing)+
                               '. Use a standard Google Colab runtime with apt-get.')
        prefix = [] if os.geteuid() == 0 else ['sudo', '-n']
        run_setup_step([*prefix, 'apt-get', 'update'], log_path, 'Updating system package list for Ollama')
        run_setup_step([*prefix, 'apt-get', 'install', '-y', '--no-install-recommends', *missing],
                       log_path, 'Installing Ollama system dependencies: '+', '.join(missing))
        remaining = [command for command in packages if not shutil.which(command)]
        if remaining:
            raise RuntimeError('Ollama system commands are still missing: '+', '.join(remaining))
    print('Downloading the official Ollama installer', flush=True)
    try:
        response = requests.get('https://ollama.com/install.sh', timeout=60)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(f'Could not download the official Ollama installer: {exc}. '
                           'Check the Colab network connection and rerun this cell.') from exc
    # Running a file with merged stdout/stderr makes installer diagnostics
    # visible in notebook output and in the log (unlike an uncaptured sh call).
    with tempfile.TemporaryDirectory(prefix='smartedit-ollama-') as directory:
        script = Path(directory)/'install.sh'
        script.write_bytes(response.content)
        run_setup_step(['sh', str(script)], log_path, 'Installing Ollama from ollama.com')
    if not shutil.which('ollama'):
        raise RuntimeError(f'Ollama installer finished but its executable is missing. See {log_path}.')
    run_setup_step(['ollama', '--version'], log_path, 'Checking installed Ollama executable')


def install_dependencies(log_path='/content/smartedit-install.log'):
    print(f'Python {sys.version.split()[0]} · checking the complete dependency set before installation', flush=True)
    command = [sys.executable, '-m', 'pip', 'install', '--disable-pip-version-check',
               '--progress-bar', 'off', *COLAB_REQUIREMENTS]
    # Resolution failures stop here, before changing the environment.
    run_setup_step([*command, '--dry-run'], log_path, 'Checking Colab dependency compatibility')
    run_setup_step(command, log_path, 'Installing compatible Colab dependencies')
    for name, expected in [('diffusers','0.37.1'),('transformers','4.57.6'),('huggingface_hub','0.36.2'),('pyngrok','7.5.1')]:
        loaded = sys.modules.get(name)
        if loaded is not None and getattr(loaded,'__version__',None) != expected:
            raise RuntimeError(f'{name} was already loaded with an older/different version. '
                               'Choose Runtime > Restart session, then rerun this updated setup cell.')
    run_setup_step([sys.executable, '-c',
        'from diffusers import DiffusionPipeline, WanPipeline, LTXConditionPipeline, Flux2KleinPipeline; '
        'from transformers import UMT5EncoderModel, Qwen3ForCausalLM, BitsAndBytesConfig, VitsModel, AutoTokenizer; '
        'import bitsandbytes, sentencepiece; '
        'from pyngrok import conf, installer; '
        'c = conf.PyngrokConfig(ngrok_version="v3", config_version="2"); '
        'installer.get_default_config(c.ngrok_version, c.config_version); '
        'print("Ngrok configuration compatibility: OK"); '
        'print("SDXL, Wan, LTX, FLUX and quantized text-encoder imports: OK")'],
        log_path, 'Checking model pipeline imports (no model weights downloaded)')


def motion_profile(vram_gb, ram_gb, bf16_supported, requested='auto', quality='quality'):
    if quality not in ('quality', 'balanced'):
        raise ValueError('SMARTEDIT_VIDEO_QUALITY must be quality or balanced.')
    if requested == 'ltx-13b':
        return LTX_RUNTIME['profile'](vram_gb, ram_gb, bf16_supported)
    hd = vram_gb >= 22 and ram_gb >= 32 and bf16_supported
    if requested not in ('auto', 'wan2.1', 'wan2.2'):
        raise ValueError('MOTION_ENGINE must be auto, ltx-13b, wan2.1 or wan2.2.')
    if requested == 'wan2.2' and not hd:
        raise ValueError('Wan 2.2 needs a native-BF16 GPU with at least 22 GiB VRAM and 32 GiB RAM in this setup.')
    hd = hd and requested != 'wan2.1'
    return {'available': vram_gb >= 14 and ram_gb >= 11,
            'engine': 'wan2.2' if hd else 'wan2.1', 'image_to_video': False,
            'dtype': 'bfloat16' if bf16_supported else 'float32',
            'model': VIDEO_MODEL_HD if hd else VIDEO_MODEL,
            'frames': 121 if hd else 81, 'fps': 24 if hd else 16,
            'steps': 50 if quality == 'quality' else 30,
            'flow_shift': None if hd else 3.0, 'guidance': 5.0,
            'sizes': {'16:9':(1280,704), '9:16':(704,1280), '1:1':(960,960)} if hd else
                     {'16:9':(832,480), '9:16':(480,832), '1:1':(624,624)},
            'quality': quality, 'native_resolution': '720p-class' if hd else '480p-class'}


def motion_settings(profile, preset='balanced'):
    """Per-request workload; export resolution never changes inference resolution."""
    if preset not in ('preview', 'balanced', 'quality'):
        raise ValueError('Choose preview, balanced or quality motion.')
    if profile.get('engine') == 'ltx-13b':
        return LTX_RUNTIME['settings'](profile, preset)
    result = dict(profile, quality=preset)
    if preset == 'quality':
        result['steps'] = 50
    else:
        result.update(steps=12 if preset == 'preview' else 30,
                      frames=49 if preset == 'preview' else 81, fps=16,
                      sizes={'16:9': (512,288), '9:16': (288,512), '1:1': (384,384)} if preset == 'preview' else
                            {'16:9': (640,352), '9:16': (352,640), '1:1': (480,480)},
                      native_resolution='288p-class preview' if preset == 'preview' else '352p-class balanced')
    return result


def image_profile(vram_gb, ram_gb, bf16_supported, requested='auto'):
    modern = bf16_supported and vram_gb >= 22 and ram_gb >= 24
    if requested not in ('auto','sdxl','flux'):
        raise ValueError('SMARTEDIT_IMAGE_MODEL must be auto, sdxl or flux.')
    if requested == 'flux' and not modern:
        raise ValueError('FLUX.2 requires native BF16, 22 GiB VRAM and 24 GiB RAM in this setup. Use auto on T4.')
    modern = modern and requested != 'sdxl'
    return {'model':IMAGE_MODEL_FLUX if modern else IMAGE_MODEL,
            'family':'flux' if modern else 'sdxl', 'dtype':'bfloat16' if modern else 'float16'}


def image_options(profile, prompt, width, height, steps):
    options = {'prompt':prompt, 'width':width//32*32, 'height':height//32*32}
    if profile['family'] == 'flux':
        options.update(num_inference_steps=4, guidance_scale=1.0)
    else:
        options.update(num_inference_steps=steps, guidance_scale=6.5,
                       negative_prompt='blurry, low quality, distorted anatomy, extra limbs, watermark, letters, typography')
    return options


def prepare_sdxl_reference(state, reference, torch):
    """Encode an SDXL reference before the diffusion pipeline claims GPU memory."""
    import hashlib
    digest = hashlib.sha256(reference.tobytes()+str(reference.size).encode()).hexdigest()
    cache = state.setdefault('sdxl_reference_cache', {})
    if digest in cache:
        return cache[digest]
    state['pipe'] = None
    release_model_memory(torch)
    configure_low_memory_downloads()
    from huggingface_hub import snapshot_download
    from transformers import CLIPImageProcessor, CLIPVisionModelWithProjection
    folder = snapshot_download('h94/IP-Adapter', max_workers=1,
        allow_patterns=['models/image_encoder/*.json', 'models/image_encoder/*.safetensors',
                        'models/image_encoder/*.txt'])
    encoder = CLIPVisionModelWithProjection.from_pretrained(folder, subfolder='models/image_encoder',
        torch_dtype=torch.float16, low_cpu_mem_usage=True, local_files_only=True, use_safetensors=True)
    processor = CLIPImageProcessor()
    pixels = processor(images=reference, return_tensors='pt').pixel_values.to(device='cuda', dtype=torch.float16)
    encoder.to('cuda')
    with torch.inference_mode():
        positive = encoder(pixels).image_embeds.unsqueeze(0)
        paired = torch.cat([torch.zeros_like(positive), positive], dim=0).cpu()
    encoder = processor = pixels = positive = None
    release_model_memory(torch)
    result = (folder, [paired])
    cache[digest] = result
    while len(cache) > 4:
        cache.pop(next(iter(cache)))
    return result


def verify_extra_features(image_fn, motion_fn, presenter_fn, video_profile,
                          presenter_ready, output_dir, progress=print):
    """Opt-in, isolated image/motion/presenter checks; one failure never masks another."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    report = {name: {'status': 'pending'} for name in ('image', 'avatar', 'motion')}
    if not video_profile.get('available'):
        reason = video_profile.get('unavailable_reason') or 'Motion is unavailable on this GPU profile.'
        for result in report.values():
            result.update(status='unavailable', reason=reason)
        target = output_dir/'smartedit-feature-checks.json'
        target.write_text(json.dumps(report, indent=2), encoding='utf-8')
        return report

    image_bytes = b''
    image_path = output_dir/'smartedit-image-check.png'
    try:
        progress('Testing the selected image model at production resolution.')
        image_bytes = image_fn({'prompt':'A clear friendly presenter portrait, natural light, plain background, no text',
                                'width':1344, 'height':768, 'steps':8, 'seed':42})
        if not image_bytes:
            raise RuntimeError('Image service returned no image bytes.')
        image_path.write_bytes(image_bytes)
        report['image'] = {'status':'passed', 'path':str(image_path)}
    except Exception as exc:
        report['image'] = {'status':'failed', 'error':str(exc)[-1000:]}

    if not presenter_ready:
        report['avatar'] = {'status':'unavailable', 'reason':'MuseTalk presenter setup is unavailable.'}
    elif image_bytes:
        try:
            audio_path = output_dir/'smartedit-presenter-check.wav'
            video_path = output_dir/'smartedit-presenter-check-input.mp4'
            subprocess.run(['ffmpeg','-y','-v','error','-f','lavfi','-i',
                'sine=frequency=440:sample_rate=16000:duration=5','-ac','1','-ar','16000',str(audio_path)],
                check=True, timeout=30)
            subprocess.run(['ffmpeg','-y','-v','error','-loop','1','-i',str(image_path),'-i',str(audio_path),
                '-t','5','-vf','scale=512:512:force_original_aspect_ratio=increase,crop=512:512',
                '-r','25','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac','-shortest',str(video_path)],
                check=True, timeout=90)
            presenter_payload = {'video':base64.b64encode(video_path.read_bytes()).decode('ascii'),
                                 'audio':base64.b64encode(audio_path.read_bytes()).decode('ascii')}
            progress('Testing the 5-second talking presenter path.')
            output = presenter_fn(presenter_payload, progress)
            if not output:
                raise RuntimeError('Presenter returned no video bytes.')
            result_path = output_dir/'smartedit-avatar-check.mp4'
            result_path.write_bytes(output)
            report['avatar'] = {'status':'passed', 'path':str(result_path)}
        except Exception as exc:
            report['avatar'] = {'status':'failed', 'error':str(exc)[-1000:]}
    else:
        report['avatar'] = {'status':'unavailable', 'reason':'The image test did not produce a presenter frame.'}

    try:
        motion_payload = {'prompt':'A paper boat drifts slowly across a calm pond, gentle ripples, steady camera, natural daylight.',
            'source_image':base64.b64encode(image_bytes).decode('ascii') if image_bytes else '',
            'aspect_ratio':'16:9', 'seed':42, 'preset':'preview', 'following_prompts':[]}
        progress('Testing a short motion preview on the selected Colab model.')
        output = motion_fn(motion_payload, progress)
        if not output:
            raise RuntimeError('Motion service returned no video bytes.')
        report['motion'] = {'status':'passed', 'bytes':len(output)}
    except Exception as exc:
        report['motion'] = {'status':'failed', 'error':str(exc)[-1000:]}

    target = output_dir/'smartedit-feature-checks.json'
    target.write_text(json.dumps(report, indent=2), encoding='utf-8')
    return report


def validate_planner_probe(content):
    try:
        data = json.loads(content)
        operations = data['operations']
        if len(operations) != 1 or operations[0]['op'] != 'clip' or operations[0]['target'] != 'all':
            raise ValueError('Unexpected operation')
        if operations[0]['changes'] != {'volume': .5}:
            raise ValueError('Wrong volume')
    except (ValueError, TypeError, KeyError, IndexError) as exc:
        raise RuntimeError('Language model failed the Hinglish JSON edit-planning test. Retry a fresh runtime.') from exc


def planner_diagnostic(value, secret=''):
    """Keep useful Ollama runner errors while removing private tunnel credentials."""
    text = str(value or '').strip()
    if secret:
        text = text.replace(secret, '[redacted]')
    text = re.sub(r'(?i)Bearer\s+\S+', 'Bearer [redacted]', text)
    text = re.sub(r'https?://[^\s\"\']+', '[remote endpoint]', text)
    return text[:500] or 'No diagnostic details were returned by Ollama.'


def record_planner_result(state, status_code, body, secret=''):
    """Keep live planner readiness tied to inference responses, not /api/tags."""
    if status_code == 200:
        state['planner_tested'] = True
        state['planner_error'] = ''
        state['planner_retry_after'] = 0
    else:
        state['planner_tested'] = False
        state['planner_error'] = f'Ollama returned HTTP {status_code}: {planner_diagnostic(body, secret)}'
        state['planner_retry_after'] = time.time() + 30
    return state['planner_tested']


class VideoJobs:
    """Bounded, idempotent GPU jobs; polling and cancellation never wait for inference."""
    def __init__(self, generate, label="Motion"):
        self.generate = generate
        self.label = label
        self.jobs = {}
        self.lock = threading.RLock()
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='wan')

    def submit(self, ident, payload):
        with self.lock:
            if ident in self.jobs:
                if self.jobs[ident]['payload'] != payload:
                    raise ValueError('This job ID already belongs to a different request.')
                return self.snapshot(ident)
            if any(j['status'] in ('queued', 'running') for j in self.jobs.values()):
                raise ValueError('A motion job is already running. Wait or cancel it first.')
            while len(self.jobs) >= 8:
                self.jobs.pop(next(iter(self.jobs)))
            self.jobs[ident] = {'id': ident, 'status': 'queued', 'message': 'Waiting for GPU',
                                'payload': payload, 'cancel': False}
            self.pool.submit(self.work, ident)
            return self.snapshot(ident)

    def snapshot(self, ident):
        with self.lock:
            return {k: v for k, v in self.jobs[ident].items() if k not in ('payload', 'data', 'cancel')}

    def update(self, ident, message):
        with self.lock:
            if self.jobs[ident]['cancel']:
                raise RuntimeError('Cancelled by user.')
            self.jobs[ident]['message'] = message

    def cancel(self, ident):
        with self.lock:
            if self.jobs[ident]['status'] in ('queued', 'running'):
                self.jobs[ident]['cancel'] = True
            return self.snapshot(ident)

    def data(self, ident):
        with self.lock:
            if self.jobs[ident]['status'] != 'completed':
                raise ValueError('Motion video is not completed.')
            return self.jobs[ident]['data']

    def work(self, ident):
        try:
            with self.lock:
                self.jobs[ident]['status'] = 'running'
                payload = self.jobs[ident]['payload']
            self.update(ident, f'Preparing {self.label.lower()} model; first setup can take several minutes')
            data = self.generate(payload, lambda message: self.update(ident, message))
            with self.lock:
                self.update(ident, f'{self.label} clip encoded')
                self.jobs[ident].update(status='completed', data=data)
        except Exception as exc:
            with self.lock:
                self.jobs[ident].update(status='cancelled' if self.jobs[ident]['cancel'] else 'failed', error=str(exc))


def select_profile(vram_gb, ram_gb, requested_model=''):
    """Conservative memory budgets, not a guarantee of available runtime memory."""
    if vram_gb < 7 or ram_gb < 10:
        raise ValueError('This setup needs a GPU with at least 7 GiB VRAM and 10 GiB system RAM. Select a fresh T4 GPU runtime.')
    model = requested_model.strip() or ('qwen3.5:27b' if vram_gb >= 30 and ram_gb >= 32 else
                                      'qwen3.5:9b' if vram_gb >= 14 and ram_gb >= 11 else 'qwen3.5:4b')
    if model not in ('qwen3.5:27b', 'qwen3.5:9b', 'qwen3.5:4b'):
        raise ValueError('Supported models: qwen3.5:27b, qwen3.5:9b or qwen3.5:4b. Remove SMARTEDIT_COLAB_MODEL to select automatically.')
    if model == 'qwen3.5:27b' and (vram_gb < 30 or ram_gb < 32):
        raise ValueError('The 27B profile needs at least 30 GiB VRAM and 32 GiB RAM. Use automatic selection on free T4.')
    if model == 'qwen3.5:9b' and (vram_gb < 14 or ram_gb < 11):
        raise ValueError('The 9B profile needs at least 14 GiB VRAM and 11 GiB RAM. Use qwen3.5:4b or automatic selection.')
    return {'model': model, 'image_model': IMAGE_MODEL,
            'offload': 'model' if vram_gb >= 14 else 'sequential',
            'context_length': 4096 if model.endswith(':4b') else 8192}


def bounded_chat_options(options, context_length):
    # Agent requests cannot accidentally allocate the model's full context window.
    result = dict(options or {})
    for key, default, maximum in [('num_ctx', context_length, context_length),
                                  ('num_predict', 6000, 6000)]:
        value = result.get(key, default)
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            value = default
        result[key] = min(value, maximum)
    return result


def main():
    print('SmartEdit Colab setup: 2026-10-24 / warm planner and direct structured generation', flush=True)
    configure_low_memory_downloads()
    subprocess.run(['nvidia-smi', '--query-gpu=name,memory.total', '--format=csv'], check=True)
    ngrok_token = read_ngrok_token()
    install_dependencies()
    import requests
    import torch
    import uvicorn
    from diffusers import DiffusionPipeline, DPMSolverMultistepScheduler
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.responses import JSONResponse, Response
    from pydantic import BaseModel, Field
    from pyngrok import ngrok

    if not torch.cuda.is_available():
        raise RuntimeError('Select a GPU runtime in Colab before running this setup.')
    if tuple(int(x) for x in torch.__version__.split('+')[0].split('.')[:2]) < (2,6):
        raise RuntimeError('This notebook needs PyTorch 2.6 or later. Use a fresh current Colab GPU runtime.')
    free_disk = shutil.disk_usage('/content').free / 1024**3
    if free_disk < 5:
        raise RuntimeError('Less than 5 GiB disk space remains. Start a fresh Colab runtime before downloading models.')
    vram_gb = torch.cuda.get_device_properties(0).total_memory / 1024**3
    ram_gb = os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES') / 1024**3
    profile = select_profile(vram_gb, ram_gb, os.getenv('SMARTEDIT_COLAB_MODEL', ''))
    # Capability >= 8 is native BF16; torch may report emulated BF16 on a T4.
    native_bf16 = torch.cuda.get_device_capability(0)[0] >= 8
    video_profile = motion_profile(vram_gb, ram_gb, native_bf16,
        os.getenv('SMARTEDIT_VIDEO_MODEL', MOTION_ENGINE), os.getenv('SMARTEDIT_VIDEO_QUALITY','quality'))
    ltx_runtime = LTX_RUNTIME
    visual_profile = image_profile(vram_gb, ram_gb, native_bf16, os.getenv('SMARTEDIT_IMAGE_MODEL','auto'))
    MODEL = profile['model']
    print(f"GPU: {torch.cuda.get_device_name(0)} ({vram_gb:.1f} GiB), RAM: {ram_gb:.1f} GiB", flush=True)
    print(f"Planning/editing: {MODEL}; images: {visual_profile['model']}; voice: {os.getenv('SMARTEDIT_VOICE_ENGINE', 'omnivoice')}", flush=True)
    print(f"Motion: {video_profile['engine']} · {video_profile['model']} · {video_profile['native_resolution']} · {video_profile['steps']} steps", flush=True)
    if not video_profile['available'] and video_profile.get('unavailable_reason'):
        print('Motion unavailable: '+video_profile['unavailable_reason'], flush=True)
    print(f"Free disk: {free_disk:.1f} GiB. First downloads can consume tens of GB. Models run one at a time.", flush=True)
    print('Low-memory downloads: one Hugging Face file at a time; parallel shard loading and Xet disabled.', flush=True)
    ngrok_config = prepare_ngrok(ngrok_token)
    presenter_runtime = {}
    exec(compile(MUSETALK_SUPPORT_SOURCE, 'musetalk_support.py', 'exec'), presenter_runtime)
    presenter_ready = False
    presenter_setup_error = ''
    if ENABLE_REALISTIC_PRESENTER:
        try:
            presenter_runtime['install']()
            presenter_ready = presenter_runtime['check']()
            if not presenter_ready:
                raise RuntimeError('MuseTalk installation checks did not pass.')
        except Exception as exc:
            presenter_setup_error = str(exc)[-1000:]
            print('MuseTalk setup failed; other services will still start. ' + presenter_setup_error, flush=True)
            print('Talking presenter is unavailable. Full diagnostic: /content/smartedit-musetalk/setup.log. '
                  'After fixing the reported error, stop this cell and rerun; downloaded files are reused.', flush=True)
    # Install/update Ollama from its official distribution, never a third-party binary.
    install_ollama()
    os.environ.update(OLLAMA_HOST='127.0.0.1:11434', OLLAMA_MAX_LOADED_MODELS='1', OLLAMA_NUM_PARALLEL='1')
    try:
        requests.get('http://127.0.0.1:11434/api/version', timeout=3).raise_for_status()
    except requests.RequestException:
        log = open('/tmp/smartedit-ollama.log', 'a')
        subprocess.Popen(['ollama', 'serve'], stdout=log, stderr=log)
        for _ in range(60):
            try:
                requests.get('http://127.0.0.1:11434/api/version', timeout=2).raise_for_status()
                break
            except requests.RequestException:
                time.sleep(1)
        else:
            raise RuntimeError('Ollama did not start. Inspect /tmp/smartedit-ollama.log.')
    run_setup_step(['ollama', 'pull', MODEL], '/content/smartedit-install.log', 'Downloading planner model '+MODEL)
    bridge_token = secrets.token_urlsafe(32)
    inference_lock = threading.Lock()
    state = {'motion_pipe': None, 'motion_embeddings': {}, 'pipe': None, 'image_tested': False, 'voice_tested': False, 'video_tested': False, 'planner_tested': False, 'planner_error': '', 'planner_retry_after': 0, 'presenter_tested': False}
    voice_runtime = {'__name__': 'smartedit_voice_runtime'}
    exec(compile(VOICE_SUPPORT_SOURCE, 'voice_support.py', 'exec'), voice_runtime)
    voice_worker = Path('/content/smartedit-voice-worker.py')
    voice_worker.write_text(VOICE_SUPPORT_SOURCE, encoding='utf-8')
    voice_mode = os.getenv('SMARTEDIT_VOICE_ENGINE', 'omnivoice')
    if voice_mode == 'omnivoice':
        omni_runtime = {'__name__': 'smartedit_omnivoice'}
        exec(compile(OMNIVOICE_SUPPORT_SOURCE, 'omnivoice_support.py', 'exec'), omni_runtime)
        omni_runtime['install'](OMNIVOICE_SUPPORT_SOURCE)
        voice_service = omni_runtime['OmniVoiceService'](voice_runtime['validate_audio'])
    else:
        voice_service = voice_runtime['VoiceService'](voice_worker, mode=voice_mode)

    def synthesize_voice(text, language, selected, rate, startup=False):
        # Voice, image, motion and presenter jobs share the same GPU lock.
        with inference_lock:
            if voice_service.mode == 'omnivoice':
                state['pipe'] = state['motion_pipe'] = None
                state['motion_embeddings'] = {}
                release_model_memory(torch)
                running = requests.get('http://127.0.0.1:11434/api/ps', timeout=15)
                running.raise_for_status()
                for item in running.json().get('models', []):
                    unloaded = requests.post('http://127.0.0.1:11434/api/generate',
                        json={'model':item['name'], 'keep_alive':0}, timeout=60)
                    unloaded.raise_for_status()
            return voice_service.synthesize(text, language, selected, rate, startup=startup)
    bridge = FastAPI(title='SmartEdit GPU Bridge')

    @bridge.middleware('http')
    async def authenticate(request: Request, call_next):
        if not secrets.compare_digest(request.headers.get('authorization', ''), 'Bearer '+bridge_token):
            return JSONResponse({'detail': 'Invalid bridge access token.'}, status_code=401)
        return await call_next(request)

    @bridge.get('/health')
    def health():
        return {'image_ready': state['image_tested'], 'voice_ready': state['voice_tested'],
                'image_model': visual_profile['model'], 'image_profile':visual_profile, 'reference_images':True,
                'voice_engine': voice_service.mode, 'voice_providers': dict(voice_service.providers),
                'voice_model_license': 'CC-BY-NC' if voice_service.mode == 'omnivoice' else 'provider-specific', 'bridge_version': 11,
                'planner_keep_alive': '5m',
                'presenter_available': presenter_ready, 'presenter_tested': state['presenter_tested'], 'edit_planner_ready':state['planner_tested'],
                'planner_error': state['planner_error'], 'presenter_setup_error': presenter_setup_error,
                'motion_presets': ['preview', 'balanced', 'quality'],
                'video_available': video_profile['available'], 'video_tested': state['video_tested'],
                'video_profile': video_profile,
                'profile': profile, 'system_memory_gb': round(ram_gb, 1),
                'ollama_model': MODEL, 'gpu': torch.cuda.get_device_name(0),
                'gpu_memory_gb': round(torch.cuda.get_device_properties(0).total_memory/1024**3,1)}

    def run_planner_probe():
        """Verify real chat inference, not just that Ollama lists the model."""
        with inference_lock:
            state['motion_pipe'] = None
            state['motion_embeddings'] = {}
            state['pipe'] = None
            release_model_memory(torch)
            response = requests.post('http://127.0.0.1:11434/api/chat', json={
                'model': MODEL, 'messages': [
                    {'role':'system','content':'Translate editing requests into JSON. Return only {"operations":[{"op":"clip","target":"all","changes":{"volume":NUMBER}}]}. Volume is a fraction from 0 to 1.'},
                    {'role':'user','content':'Poori video ki awaaz 50% kar do.'}],
                'format':'json', 'think':False, 'keep_alive':'5m',
                'options':{'num_ctx':profile['context_length'],'num_predict':256,'temperature':0}},
                timeout=120)
            if response.status_code != 200:
                state['planner_tested'] = False
                state['planner_error'] = f'Ollama returned HTTP {response.status_code}: {planner_diagnostic(response.text, bridge_token)}'
                raise RuntimeError(state['planner_error'])
            try:
                content = response.json().get('message',{}).get('content','')
                validate_planner_probe(content)
            except Exception as exc:
                state['planner_tested'] = False
                state['planner_error'] = planner_diagnostic(exc, bridge_token)
                raise RuntimeError(state['planner_error']) from None
            state['planner_tested'] = True
            state['planner_error'] = ''
            state['planner_retry_after'] = 0

    @bridge.post('/planner/check')
    def planner_check():
        if time.time() < state['planner_retry_after']:
            raise HTTPException(503, state['planner_error'] or 'Planner recovery check is cooling down. Retry shortly.')
        try:
            run_planner_probe()
        except Exception as exc:
            state['planner_tested'] = False
            state['planner_error'] = planner_diagnostic(exc, bridge_token)
            state['planner_retry_after'] = time.time() + 30
            raise HTTPException(503, state['planner_error']) from None
        return {'planner_ready': True}

    @bridge.get('/api/tags')
    def tags():
        response = requests.get('http://127.0.0.1:11434/api/tags', timeout=15)
        return Response(response.content, status_code=response.status_code, media_type='application/json')

    @bridge.post('/api/chat')
    def chat(payload: dict):
        with inference_lock:
            state['motion_pipe'] = None
            release_model_memory(torch)
            if state['pipe'] is not None:
                state['pipe'] = None
                release_model_memory(torch)
            if payload.get('model') != MODEL:
                raise HTTPException(400, f'This bridge is configured for {MODEL}. Change MODEL in the Colab setup to use another model.')
            # Keep consecutive planning stages warm, but bound idle VRAM use.
            # Image, voice, motion and presenter routes unload Ollama under this lock.
            payload.update(stream=False, keep_alive='5m')
            payload['options'] = bounded_chat_options(payload.get('options'), profile['context_length'])
            try:
                response = requests.post('http://127.0.0.1:11434/api/chat', json=payload, timeout=600)
            except requests.Timeout:
                state['planner_tested'] = False
                state['planner_error'] = 'Ollama planner inference timed out. Check the Colab Ollama log and GPU memory.'
                state['planner_retry_after'] = time.time() + 30
                raise HTTPException(504, state['planner_error']) from None
            except requests.RequestException as exc:
                state['planner_tested'] = False
                state['planner_error'] = planner_diagnostic(exc, bridge_token)
                state['planner_retry_after'] = time.time() + 30
                raise HTTPException(502, 'Colab could not reach Ollama: '+state['planner_error']) from None
            record_planner_result(state, response.status_code, response.text, bridge_token)
            return Response(response.content, status_code=response.status_code, media_type='application/json')

    class ImageRequest(BaseModel):
        prompt: str = Field(min_length=3, max_length=5000)
        width: int = Field(1344, ge=256, le=1536)
        height: int = Field(768, ge=256, le=1536)
        seed: int = Field(42, ge=0, le=4294967295)
        steps: int = Field(40, ge=4, le=50)
        reference_image: str = Field('',max_length=8000000)

    @bridge.post('/image')
    def image(payload: ImageRequest):
        if payload.width*payload.height > 1536*768:
            raise HTTPException(400, 'Use an image bucket near one megapixel to fit the selected GPU profile.')
        reference=None
        if payload.reference_image:
            try:
                from PIL import Image
                reference=Image.open(io.BytesIO(base64.b64decode(payload.reference_image,validate=True)))
                if reference.width*reference.height > 1536*1536:
                    raise ValueError('Reference too large')
                reference.load()
                reference=reference.convert('RGB')
            except Exception:
                raise HTTPException(400,'Invalid character reference image.')
        with inference_lock:
            state['motion_pipe'] = None
            release_model_memory(torch)
            # Explicitly unload all Ollama runners before loading SDXL into shared VRAM.
            running = requests.get('http://127.0.0.1:11434/api/ps', timeout=15)
            running.raise_for_status()
            for model in running.json().get('models', []):
                unload = requests.post('http://127.0.0.1:11434/api/generate',
                    json={'model': model['name'], 'keep_alive': 0}, timeout=120)
                unload.raise_for_status()
            try:
                reference_embeds = None
                if reference is not None and visual_profile['family'] == 'sdxl':
                    _, reference_embeds = prepare_sdxl_reference(state, reference, torch)
                if state['pipe'] is not None and visual_profile['family']!='flux' and (
                    bool(getattr(state['pipe'],'_smartedit_reference',False)) != bool(reference)):
                    state['pipe']=None
                    release_model_memory(torch)
                if state['pipe'] is None:
                    release_model_memory(torch)
                    model_folder = download_model_serially(visual_profile['model'], visual_profile['family'],
                                                           lambda message: print(message, flush=True))
                    if visual_profile['family'] == 'flux':
                        from diffusers import Flux2KleinPipeline
                        pipe = Flux2KleinPipeline.from_pretrained(model_folder,
                            torch_dtype=torch.bfloat16, low_cpu_mem_usage=True, local_files_only=True, use_safetensors=True)
                    else:
                        pipe = DiffusionPipeline.from_pretrained(model_folder, torch_dtype=torch.float16,
                            variant='fp16', use_safetensors=True, low_cpu_mem_usage=True, local_files_only=True)
                        pipe.scheduler = DPMSolverMultistepScheduler.from_config(
                            pipe.scheduler.config, algorithm_type='dpmsolver++', use_karras_sigmas=True)
                        if reference is not None:
                            pipe.load_ip_adapter('h94/IP-Adapter',subfolder='sdxl_models',weight_name='ip-adapter_sdxl.bin')
                            pipe.set_ip_adapter_scale(.65)
                            pipe._smartedit_reference=True
                    state['pipe'] = pipe
                    if profile['offload'] == 'sequential':
                        pipe.enable_sequential_cpu_offload()
                    else:
                        pipe.enable_model_cpu_offload()
                    if visual_profile['family'] == 'flux':
                        pipe.vae.enable_tiling()
                    else:
                        pipe.enable_vae_slicing()
                        pipe.enable_vae_tiling()
                    del pipe
                reference_args = ({'image': reference} if visual_profile['family'] == 'flux' else
                                  {'ip_adapter_image_embeds': reference_embeds}) if reference is not None else {}
                result = state['pipe'](**image_options(visual_profile,payload.prompt,payload.width,payload.height,payload.steps),**reference_args,
                    generator=torch.Generator('cpu').manual_seed(payload.seed)).images[0]
                import numpy as np
                pixels = np.asarray(result)
                if not np.isfinite(pixels).all() or float(np.std(pixels)) < 1:
                    raise RuntimeError('Image model produced a blank or invalid frame. Retry in a fresh runtime.')
                output = io.BytesIO()
                result.save(output, format='PNG')
                state['image_tested'] = True
                return Response(output.getvalue(), media_type='image/png')
            except torch.cuda.OutOfMemoryError:
                state['pipe'] = None
                if 'pipe' in locals():
                    del pipe
                release_model_memory(torch)
                raise HTTPException(503, 'GPU memory exhausted. Restart a fresh GPU runtime, run only this cell, and choose Balanced image quality in SmartEdit.')

    def generate_motion(payload, progress):
        from diffusers import AutoencoderKLWan, WanPipeline, UniPCMultistepScheduler
        from diffusers.utils import export_to_video
        from transformers import AutoTokenizer, UMT5EncoderModel, BitsAndBytesConfig
        import numpy as np
        options = motion_settings(video_profile, payload.get('preset', 'balanced'))

        with inference_lock:
            progress('Releasing image and language models for motion generation')
            state['pipe'] = None
            release_model_memory(torch)
            running = requests.get('http://127.0.0.1:11434/api/ps', timeout=15)
            running.raise_for_status()
            for model in running.json().get('models', []):
                unload = requests.post('http://127.0.0.1:11434/api/generate',
                    json={'model': model['name'], 'keep_alive': 0}, timeout=120)
                unload.raise_for_status()
            encoder = encoder_pipe = tokenizer = pipe = vae = frames = positive = negative = None
            try:
                if video_profile['engine'] == 'ltx-13b':
                    model_folder = download_model_serially(video_profile['model'], 'ltx', progress)
                    frames = ltx_runtime['generate'](state, model_folder, payload, options, progress)
                    if not np.isfinite(frames).all() or float(np.std(frames)) < .001:
                        raise RuntimeError('LTX returned invalid or blank frames. Retry in a fresh GPU runtime.')
                    progress('Encoding generated LTX motion to MP4')
                    with tempfile.TemporaryDirectory(prefix='smartedit-motion-') as directory:
                        output = Path(directory)/'motion.mp4'
                        export_to_video(frames, str(output), fps=options['fps'])
                        import imageio.v2 as imageio
                        reader = imageio.get_reader(str(output))
                        try:
                            decoded = reader.get_data(0)
                            if decoded.shape[:2] != (options['sizes'][payload['aspect_ratio']][1],
                                                     options['sizes'][payload['aspect_ratio']][0]):
                                raise RuntimeError('LTX MP4 dimensions do not match the requested aspect ratio.')
                        finally:
                            reader.close()
                        data = output.read_bytes()
                    if len(data) < 1000:
                        raise RuntimeError('LTX encoder returned an empty video.')
                    state['video_tested'] = True
                    return data
                # Finish every download before allocating any motion-model weights.
                # from_pretrained cannot start its own parallel network downloads.
                model_folder = download_model_serially(video_profile['model'], 'wan', progress)
                # UMT5 alone is too large in FP32 for free Colab RAM. Quantize on GPU,
                # encode, then release it completely before loading the video transformer.
                if payload['prompt'] not in state['motion_embeddings']:
                    state['motion_pipe'] = None
                    state['motion_embeddings'].clear()
                    release_model_memory(torch)
                    progress('Loading 8-bit motion text encoder from disk, one shard at a time')
                    encoder = UMT5EncoderModel.from_pretrained(model_folder, subfolder='text_encoder',
                        quantization_config=BitsAndBytesConfig(load_in_8bit=True), device_map={'': 0},
                        torch_dtype=torch.float32, low_cpu_mem_usage=True, local_files_only=True, use_safetensors=True)
                    tokenizer = AutoTokenizer.from_pretrained(model_folder, subfolder='tokenizer', local_files_only=True)
                    encoder_pipe = WanPipeline(tokenizer=tokenizer, text_encoder=encoder, vae=None,
                                               transformer=None, scheduler=None)
                    prompts = list(dict.fromkeys([payload['prompt'], *payload.get('following_prompts', [])]))
                    for prompt_index, shot_prompt in enumerate(prompts):
                        progress(f'Preparing storyboard prompt {prompt_index+1}/{len(prompts)} with one loaded text encoder')
                        with torch.inference_mode():
                            positive, negative = encoder_pipe.encode_prompt(prompt=shot_prompt,
                                negative_prompt='static image, slideshow, blurry, distorted anatomy, extra limbs, '
                                                'deformed face, watermark, subtitles, letters, sudden cuts',
                                device=torch.device('cuda'), dtype=torch.float32, max_sequence_length=512)
                            positive, negative = positive.cpu(), negative.cpu()
                        if not torch.isfinite(positive).all() or not torch.isfinite(negative).all():
                            raise RuntimeError('Motion text encoder produced invalid values. Restart the runtime.')
                        state['motion_embeddings'][shot_prompt] = (positive, negative)
                    encoder_pipe = encoder = tokenizer = None
                    release_model_memory(torch)
                positive, negative = state['motion_embeddings'][payload['prompt']]
                dtype = torch.bfloat16 if video_profile['dtype'] == 'bfloat16' else torch.float32
                pipe = state['motion_pipe']
                if pipe is None:
                    progress(f"Loading {video_profile['model']}; inference can take many minutes per shot")
                    # T4 has no native BF16. FP32 avoids overflowing Wan weights in FP16.
                    vae = AutoencoderKLWan.from_pretrained(model_folder, subfolder='vae', torch_dtype=torch.float32,
                        low_cpu_mem_usage=True, local_files_only=True, use_safetensors=True)
                    pipe = WanPipeline.from_pretrained(model_folder, text_encoder=None, tokenizer=None,
                        vae=vae, torch_dtype=dtype, low_cpu_mem_usage=True, local_files_only=True, use_safetensors=True)
                    vae = None
                    # TI2V-5B retains its own scheduler config and expand_timesteps setting.
                    if video_profile['flow_shift'] is not None:
                        pipe.scheduler = UniPCMultistepScheduler.from_config(pipe.scheduler.config,
                            flow_shift=video_profile['flow_shift'])
                    pipe.vae.enable_tiling()
                    pipe.enable_model_cpu_offload()
                    state['motion_pipe'] = pipe
                else:
                    progress('Reusing the loaded motion model and prepared storyboard prompts')
                width, height = options['sizes'][payload['aspect_ratio']]
                progress(f"Motion preset: {options['quality']}, {width}x{height}, {options['frames']} frames, {options['steps']} steps")
                started = last_step = time.monotonic()

                def step_callback(pipeline, step, timestep, tensors):
                    nonlocal last_step
                    now = time.monotonic()
                    average = (now-started)/(step+1)
                    remaining = average * (options['steps']-step-1)
                    allocated = torch.cuda.max_memory_allocated()/1024**3
                    progress(f"Generating motion: step {step + 1}/{options['steps']} · {now-last_step:.1f}s/step · "
                             f"estimated {remaining/60:.1f} min left in this shot · peak GPU {allocated:.1f} GiB")
                    last_step = now
                    return tensors

                with torch.inference_mode():
                    frames = pipe(prompt_embeds=positive.to(device='cuda', dtype=dtype),
                        negative_prompt_embeds=negative.to(device='cuda', dtype=dtype),
                        width=width, height=height, num_frames=options['frames'],
                        num_inference_steps=options['steps'], guidance_scale=video_profile['guidance'],
                        generator=torch.Generator('cpu').manual_seed(payload['seed']),
                        callback_on_step_end=step_callback).frames[0]
                if not np.isfinite(frames).all() or float(np.std(frames)) < .001:
                    raise RuntimeError('Motion model returned invalid or blank frames. Retry in a fresh GPU runtime.')
                progress('Encoding generated motion to MP4')
                with tempfile.TemporaryDirectory(prefix='smartedit-motion-') as directory:
                    output = Path(directory)/'motion.mp4'
                    export_to_video(frames, str(output), fps=options['fps'])
                    import imageio.v2 as imageio
                    reader = imageio.get_reader(str(output))
                    try:
                        decoded = reader.get_data(0)
                        if decoded.shape[:2] != (height,width) or float(np.std(decoded)) < 1:
                            raise RuntimeError('Encoded motion did not pass the decoded-frame check.')
                    finally:
                        reader.close()
                    data = output.read_bytes()
                if len(data) < 1000:
                    raise RuntimeError('Motion encoder returned an empty video.')
                state['video_tested'] = True
                return data
            except torch.cuda.OutOfMemoryError:
                state['motion_pipe'] = None
                state['motion_embeddings'].clear()
                raise RuntimeError('GPU memory exhausted during motion generation. Try Fast draft with a shorter storyboard.') from None
            except Exception:
                state['motion_pipe'] = None
                raise
            finally:
                encoder_pipe = encoder = tokenizer = pipe = vae = frames = positive = negative = None
                release_model_memory(torch)

    video_jobs = VideoJobs(generate_motion)

    class VideoRequest(BaseModel):
        id: str = Field(pattern=r'^[a-f0-9]{32}$')
        prompt: str = Field(min_length=3, max_length=5000)
        aspect_ratio: Literal['16:9', '9:16', '1:1'] = '16:9'
        seed: int = Field(42, ge=0, le=4294967295)
        preset: Literal['preview', 'balanced', 'quality'] = 'balanced'
        following_prompts: list[str] = Field(default_factory=list, max_length=12)
        source_image: str = Field('', max_length=8000000)

    @bridge.post('/video/jobs')
    def submit_video(payload: VideoRequest):
        if any(not 3 <= len(prompt) <= 5000 for prompt in payload.following_prompts):
            raise HTTPException(422, 'Storyboard prompts must contain 3 to 5000 characters.')
        if video_profile['engine'] == 'ltx-13b':
            if not video_profile['available']:
                raise HTTPException(503, video_profile.get('unavailable_reason') or 'LTX motion is unavailable on this GPU.')
            try:
                ltx_runtime['decode_image'](payload.source_image)
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from None
        elif not video_profile['available']:
            raise HTTPException(503, 'Motion generation needs at least 14 GiB GPU memory and 11 GiB system RAM. Select a T4 or larger runtime.')
        try:
            return video_jobs.submit(payload.id, payload.model_dump())
        except ValueError as exc:
            raise HTTPException(409, str(exc))

    @bridge.get('/video/jobs/{ident}')
    def video_status(ident: str):
        try:
            return video_jobs.snapshot(ident)
        except KeyError:
            raise HTTPException(404, 'Motion job not found; the Colab runtime may have restarted.')

    @bridge.post('/video/jobs/{ident}/cancel')
    def cancel_video(ident: str):
        try:
            return video_jobs.cancel(ident)
        except KeyError:
            raise HTTPException(404, 'Motion job not found.')

    @bridge.get('/video/jobs/{ident}/file')
    def download_video(ident: str):
        try:
            return Response(video_jobs.data(ident), media_type='video/mp4')
        except KeyError:
            raise HTTPException(404, 'Motion job not found.')
        except ValueError as exc:
            raise HTTPException(409, str(exc))

    def generate_presenter(payload, progress):
        with inference_lock:
            progress('Releasing image and motion models before lip-sync.')
            state['pipe'] = state['motion_pipe'] = None
            state['motion_embeddings'] = {}
            release_model_memory(torch)
            running = requests.get('http://127.0.0.1:11434/api/ps',timeout=15)
            running.raise_for_status()
            for model in running.json().get('models',[]):
                response = requests.post('http://127.0.0.1:11434/api/generate',
                    json={'model':model['name'],'keep_alive':0},timeout=60)
                response.raise_for_status()
            output = presenter_runtime['infer'](payload, progress)
            state['presenter_tested'] = True
            return output

    presenter_jobs = VideoJobs(generate_presenter, label="Presenter")

    class PresenterRequest(BaseModel):
        id: str = Field(pattern=r'^[a-f0-9]{32}$')
        video: str = Field(min_length=4,max_length=28_000_004)
        audio: str = Field(min_length=4,max_length=8_000_004)

    @bridge.post('/presenter/jobs')
    def submit_presenter(payload: PresenterRequest):
        if not presenter_ready:
            raise HTTPException(503,'Enable realistic presenter in the updated notebook and rerun setup.')
        try:
            return presenter_jobs.submit(payload.id,payload.model_dump())
        except ValueError as exc:
            raise HTTPException(409,str(exc))

    @bridge.get('/presenter/jobs/{ident}')
    def presenter_status(ident: str):
        try: return presenter_jobs.snapshot(ident)
        except KeyError: raise HTTPException(404,'Presenter job not found. Colab may have restarted.')

    @bridge.post('/presenter/jobs/{ident}/cancel')
    def presenter_cancel(ident: str):
        try: return presenter_jobs.cancel(ident)
        except KeyError: raise HTTPException(404,'Presenter job not found.')

    @bridge.get('/presenter/jobs/{ident}/file')
    def presenter_file(ident: str):
        try: return Response(presenter_jobs.data(ident),media_type='video/mp4')
        except KeyError: raise HTTPException(404,'Presenter job not found.')
        except ValueError as exc: raise HTTPException(409,str(exc))

    class VoiceRequest(BaseModel):
        text: str = Field(min_length=1, max_length=5000)
        language: Literal['en', 'hi', 'es', 'fr', 'de'] = 'en'
        gender: Literal['male', 'female'] = 'male'
        rate: int = Field(-5, ge=-20, le=20)

    voice_names = {
        'en': {'male': 'en-US-ChristopherNeural', 'female': 'en-US-JennyNeural'},
        'hi': {'male': 'hi-IN-MadhurNeural', 'female': 'hi-IN-SwaraNeural'},
        'es': {'male': 'es-ES-AlvaroNeural', 'female': 'es-ES-ElviraNeural'},
        'fr': {'male': 'fr-FR-HenriNeural', 'female': 'fr-FR-DeniseNeural'},
        'de': {'male': 'de-DE-KillianNeural', 'female': 'de-DE-KatjaNeural'},
    }

    @bridge.post('/voice')
    def voice(payload: VoiceRequest):
        selected = voice_names[payload.language][payload.gender]
        try:
            data, actual_voice, provider = synthesize_voice(
                payload.text, payload.language, selected, payload.rate)
        except (RuntimeError, ValueError) as exc:
            state['voice_tested'] = all(lang in voice_service.providers for lang in ('hi', 'en'))
            raise HTTPException(502, str(exc)) from None
        state['voice_tested'] = all(lang in voice_service.providers for lang in ('hi', 'en'))
        return Response(data, media_type='audio/mpeg', headers={
            'X-SmartEdit-Voice': actual_voice, 'X-SmartEdit-Voice-Provider': provider,
            'X-SmartEdit-Voice-License': 'CC-BY-NC' if provider == 'omnivoice' else ('CC-BY-NC-4.0' if provider == 'mms' else 'online-service')})

    # Do not advertise a connection as ready before its actual services work.
    print('Testing Hinglish edit planning, Hindi/English voice, and the selected image model. First downloads take time…', flush=True)
    run_planner_probe()
    for language, text in [('hi', 'नमस्ते। आपकी वीडियो की आवाज़ तैयार है।'),
                           ('en', 'Your video narration is ready.')]:
        data, actual_voice, provider = synthesize_voice(
            text, language, voice_names[language]['male'], -5, startup=True)
        Path('/content/smartedit-voice-check-'+language+'.mp3').write_bytes(data)
        print(f'Voice startup test passed: {language} / {actual_voice}', flush=True)
    state['voice_tested'] = True
    if voice_service.mode == 'omnivoice':
        mixed, _, _ = synthesize_voice('आज हम AI video editing सीखेंगे। Let us start with a simple example.',
                                       'hi', 'male', -5, startup=True)
        Path('/content/smartedit-voice-check-hinglish.mp3').write_bytes(mixed)
        print('Hinglish audio check passed; listen to the sample to review pronunciation.', flush=True)
    # Exercise the production image size, not a tiny image that conceals memory failures.
    image(ImageRequest(prompt='A cinematic sunlit mountain landscape, natural colors, no text', width=1344, height=768, steps=8))
    # Image, avatar and motion checks remain opt-in because they consume GPU time.
    # Each route gets its own result so one unavailable feature cannot hide another.
    if os.getenv('SMARTEDIT_TEST_MOTION','0') == '1':
        checks = verify_extra_features(
            lambda payload: image(ImageRequest(**payload)).body,
            generate_motion, generate_presenter, video_profile, presenter_ready,
            '/content', lambda message: print(message, flush=True))
        state['video_tested'] = checks['motion']['status'] == 'passed'
        state['presenter_tested'] = checks['avatar']['status'] == 'passed'
        print('Feature check report: /content/smartedit-feature-checks.json', flush=True)
        print('Motion test:', checks['motion']['status'], '· avatar test:', checks['avatar']['status'], flush=True)

    tunnel = ngrok.connect(PORT, 'http', pyngrok_config=ngrok_config)
    server = uvicorn.Server(uvicorn.Config(bridge, host='0.0.0.0', port=PORT, log_level='warning'))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(60):
        if server.started:
            break
        if not thread.is_alive():
            raise RuntimeError('Bridge could not start. Restart the Colab runtime to clear the old server.')
        time.sleep(.5)
    else:
        raise RuntimeError('Bridge startup timed out.')
    connection = base64.urlsafe_b64encode(json.dumps({'token':bridge_token,'model':MODEL}).encode()).decode().rstrip('=')
    print('\nSMARTEDIT CONNECTION READY — edit planning, images and voice passed startup tests')
    print('ONE-PASTE CONNECTION LINK (private, includes the access token):')
    print(tunnel.public_url+'/#smartedit='+connection)
    print('Ollama URL AND Image bridge URL:', tunnel.public_url)
    print('Model:', MODEL)
    print('Bridge access token:', bridge_token)
    print('Paste the ONE-PASTE link into the existing Colab URL box in SmartEdit, then Connect & Test.')
    print('Keep this cell running. Select AI motion for Wan shots, or Image story for the selected image model.')
    print('Motion test:', 'PASSED' if state['video_tested'] else 'NOT TESTED (or unavailable on this GPU)')
    print(f"Motion source: {video_profile['native_resolution']}. 1080p export resizes it. No native soundtrack or lip-sync.")
    try:
        while thread.is_alive():
            time.sleep(5)
    except KeyboardInterrupt:
        server.should_exit = True
        ngrok.disconnect(tunnel.public_url, pyngrok_config=ngrok_config)


if __name__ == '__main__':
    main()
