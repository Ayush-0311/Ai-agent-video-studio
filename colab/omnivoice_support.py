"""Isolated upstream OmniVoice runtime. No VoiceStudio application dependency."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path('/content/smartedit-omnivoice')
VERSION = '0.2.1'
MODEL = 'k2-fsa/OmniVoice'
ANCHORS = {
    'hi': 'नमस्ते। आज हम एक नई कहानी सुनेंगे। आइए इस विषय को आसान भाषा में समझते हैं।',
    'en': 'Hello. Today we will explore a new story. Let us understand this topic together.',
    'es': 'Hola. Hoy vamos a explorar una nueva historia y aprender juntos.',
    'fr': 'Bonjour. Nous allons découvrir une nouvelle histoire et apprendre ensemble.',
    'de': 'Hallo. Heute entdecken wir eine neue Geschichte und lernen gemeinsam.'}


def python_path():
    return ROOT/'venv/bin/python'


def environment():
    env = os.environ.copy()
    for key in ('PYTHONPATH', 'PYTHONHOME'):
        env.pop(key, None)
    env.update(PYTHONNOUSERSITE='1', USE_TF='0', USE_FLAX='0', MPLBACKEND='Agg',
               HF_HUB_DISABLE_XET='1', HF_ENABLE_PARALLEL_LOADING='false')
    return env


def run(args, timeout=1800):
    ROOT.mkdir(parents=True, exist_ok=True)
    log_path = ROOT/'runtime.log'
    with log_path.open('a', encoding='utf-8') as log:
        log.write('\nOmniVoice operation starting\n')
        log.flush()
        try:
            result = subprocess.run([str(x) for x in args], stdout=log, stderr=subprocess.STDOUT,
                                    env=environment(), timeout=timeout)
        except subprocess.TimeoutExpired:
            raise RuntimeError(f'OmniVoice timed out; worker stopped. Diagnostic: {log_path}') from None
    if result.returncode:
        with log_path.open('rb') as log:
            log.seek(max(0, log_path.stat().st_size-6000))
            detail = log.read().decode('utf-8', errors='replace')
        print(detail, flush=True)
        raise RuntimeError(f'OmniVoice failed. Diagnostic: {log_path}\n{detail[-2000:]}')


def install(worker_source):
    if sys.platform != 'linux':
        raise RuntimeError('Automatic OmniVoice installation requires the Colab Linux GPU runtime.')
    ROOT.mkdir(parents=True, exist_ok=True)
    (ROOT/'worker.py').write_text(worker_source, encoding='utf-8')
    marker = ROOT/'installed.json'
    expected = {'omnivoice': VERSION, 'torch': '2.8.0', 'transformers': '5.3.0'}
    try:
        reuse = json.loads(marker.read_text()) == expected and python_path().is_file()
    except (OSError, ValueError):
        reuse = False
    marker.unlink(missing_ok=True)
    if not reuse:
        print('Installing OmniVoice in separate Python 3.11. Log: '+str(ROOT/'runtime.log'), flush=True)
        run([sys.executable, '-m', 'pip', 'install', 'uv==0.8.22'])
        if not python_path().exists():
            run([sys.executable, '-m', 'uv', 'venv', '--python', '3.11', ROOT/'venv'])
        py = python_path()
        run([sys.executable, '-m', 'uv', 'pip', 'install', '--python', py,
             'torch==2.8.0', 'torchaudio==2.8.0', '--index-url', 'https://download.pytorch.org/whl/cu128'])
        constraints = ROOT/'constraints.txt'
        constraints.write_text('torch==2.8.0\ntorchaudio==2.8.0\ntransformers==5.3.0\n')
        run([sys.executable, '-m', 'uv', 'pip', 'install', '--python', py, '-c', constraints,
             'omnivoice=='+VERSION, 'transformers==5.3.0'])
    run([python_path(), '-c', "import torch; from omnivoice import OmniVoice; "
         "assert torch.cuda.is_available(), 'OmniVoice requires a GPU runtime'; "
         "x=torch.ones(1, device='cuda'); torch.cuda.synchronize(); print('OmniVoice CUDA/imports passed')"])
    marker.write_text(json.dumps(expected))


class OmniVoiceService:
    mode = 'omnivoice'

    def __init__(self, validate_audio):
        self.validate_audio = validate_audio
        self.providers = {}

    def synthesize(self, text, language, selected, rate, startup=False):
        if language not in ('hi', 'en', 'es', 'fr', 'de') or not text.strip() or len(text)>5000:
            raise ValueError('Invalid narration language or text length.')
        gender = 'female' if selected in ('female', 'hi-IN-SwaraNeural', 'en-US-JennyNeural',
                    'es-ES-ElviraNeural', 'fr-FR-DeniseNeural', 'de-DE-KatjaNeural') else 'male'
        self.providers.pop(language, None)
        with tempfile.TemporaryDirectory(prefix='speech-', dir=ROOT) as directory:
            work = Path(directory)
            request = work/'request.json'
            request.write_text(json.dumps({'text':text, 'language':language, 'gender':gender,
                                           'rate':rate}), encoding='utf-8')
            print(f'OmniVoice: generating {language} / {gender}. First use downloads model weights.', flush=True)
            run([python_path(), ROOT/'worker.py', request, work/'speech.wav'], timeout=1800 if startup else 900)
            self.validate_audio(work/'speech.wav')
            run(['ffmpeg', '-y', '-v', 'error', '-i', work/'speech.wav', '-codec:a',
                 'libmp3lame', '-b:a', '192k', work/'speech.mp3'], timeout=30)
            self.validate_audio(work/'speech.mp3')
            self.providers[language] = 'omnivoice'
            return (work/'speech.mp3').read_bytes(), MODEL+'/'+gender, 'omnivoice'


def worker(request_path, output_path):
    import numpy as np
    import soundfile as sf
    import torch
    from huggingface_hub import snapshot_download
    from omnivoice import OmniVoice, VoiceClonePrompt
    request = json.loads(Path(request_path).read_text(encoding='utf-8'))
    torch.set_num_threads(2)
    torch.manual_seed(42)
    # Complete the serial download before allocating GPU weights.
    model_marker = ROOT/'model-path.json'
    try:
        local = json.loads(model_marker.read_text())['path']
        if not (Path(local)/'config.json').is_file():
            raise FileNotFoundError('Model cache no longer exists')
    except (OSError, ValueError, KeyError):
        local = snapshot_download(MODEL, max_workers=1)
        model_marker.write_text(json.dumps({'path':local}))
    model = OmniVoice.from_pretrained(local, device_map='cuda:0', dtype=torch.float16,
                                     attn_implementation='sdpa', load_asr=False)
    # Reuse a self-generated reference instead of redesigning the narrator per scene.
    profiles = ROOT/('profiles-'+VERSION)
    profiles.mkdir(parents=True, exist_ok=True)
    profile = profiles/(request['language']+'-'+request['gender']+'.pt')
    with torch.inference_mode():
        if profile.exists():
            prompt = VoiceClonePrompt.load(str(profile))
        else:
            anchor = ANCHORS[request['language']]
            reference = model.generate(text=anchor, language=request['language'],
                                       instruct=request['gender'], num_step=32)[0]
            reference = np.asarray(reference, dtype=np.float32).reshape(-1)
            if not np.isfinite(reference).all() or reference.size < model.sampling_rate or np.max(np.abs(reference)) < .001:
                raise RuntimeError('OmniVoice narrator reference is empty or silent.')
            with tempfile.TemporaryDirectory(prefix='reference-', dir=ROOT) as folder:
                path = Path(folder)/'reference.wav'
                sf.write(str(path), reference, model.sampling_rate)
                prompt = model.create_voice_clone_prompt(ref_audio=str(path), ref_text=anchor)
            pending = profile.with_suffix('.partial')
            prompt.save(str(pending))
            pending.replace(profile)
        audio = model.generate(text=request['text'], language=request['language'],
                               voice_clone_prompt=prompt, speed=1+request['rate']/100,
                               num_step=32)[0]
    audio = np.asarray(audio, dtype=np.float32).reshape(-1)
    if audio.size < model.sampling_rate/10 or not np.isfinite(audio).all():
        raise RuntimeError('OmniVoice returned empty or invalid samples.')
    sf.write(str(output_path), audio, model.sampling_rate, subtype='PCM_16')


if __name__ == '__main__':
    worker(sys.argv[1], sys.argv[2])
