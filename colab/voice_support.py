"""Validated Edge speech with a CPU MMS fallback, shared by notebook and worker."""
import array
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import threading
import time
import wave

MMS_LANGUAGES = {'en': 'eng', 'hi': 'hin', 'es': 'spa', 'fr': 'fra', 'de': 'deu'}


def chunks(text, limit=220):
    text = re.sub(r'\s+', ' ', text).strip()
    if not text:
        raise ValueError('Narration text is empty.')
    result = []
    while text:
        cut = len(text)
        if cut > limit:
            candidates = [m.end() for m in re.finditer(r'[.!?।;]\s|\s', text[:limit+1])]
            cut = candidates[-1] if candidates else limit
        result.append(text[:cut].strip())
        text = text[cut:].strip()
    return result


def validate_audio(path):
    """Decode the whole clip and reject corrupt, empty or effectively silent audio."""
    result = subprocess.run(['ffmpeg', '-v', 'error', '-xerror', '-i', str(path),
                             '-ac', '1', '-ar', '16000', '-f', 's16le', '-'],
                            capture_output=True, timeout=15)
    if result.returncode or len(result.stdout) < 3200:
        raise RuntimeError('Speech audio is missing, too short or cannot be decoded.')
    samples = array.array('h', result.stdout)
    if sys.byteorder != 'little':
        samples.byteswap()
    if max(abs(x) for x in samples) < 32:
        raise RuntimeError('Speech provider returned silent audio.')


class VoiceService:
    def __init__(self, worker, log_path='/content/smartedit-voice.log', mode='auto'):
        if mode not in ('auto', 'edge', 'mms'):
            raise ValueError('SMARTEDIT_VOICE_ENGINE must be auto, edge or mms.')
        self.worker = str(worker)
        self.log_path = Path(log_path)
        self.mode = mode
        self.lock = threading.Lock()
        self.edge_retry_at = 0
        self.providers = {}

    def log(self, message):
        # Never log input narration, tokens or full child tracebacks containing text.
        print('[Voice] '+message, flush=True)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open('a', encoding='utf-8') as output:
            output.write(time.strftime('%Y-%m-%d %H:%M:%S')+' '+message+'\n')

    def run(self, command, timeout):
        result = subprocess.run(command, capture_output=True, timeout=timeout,
                                text=True, encoding='utf-8', errors='replace')
        if result.returncode:
            # Keep exception type and diagnostic, with bounded output.
            detail = (result.stderr or result.stdout or 'No diagnostic returned').strip().splitlines()[-1]
            raise RuntimeError(detail[-1200:])

    def synthesize(self, text, language, selected, rate, startup=False):
        if language not in MMS_LANGUAGES or not text.strip() or len(text) > 5000:
            raise ValueError('Use non-empty narration (up to 5000 characters) and a supported language.')
        with self.lock, tempfile.TemporaryDirectory(prefix='smartedit-voice-') as directory:
            work = Path(directory)
            output = work/'speech.mp3'
            source = work/'text.txt'
            source.write_text(text, encoding='utf-8')
            failures = []
            if self.mode != 'mms' and (self.mode == 'edge' or time.monotonic() >= self.edge_retry_at):
                for attempt in range(2):
                    try:
                        output.unlink(missing_ok=True)
                        self.run([sys.executable, '-m', 'edge_tts', '--voice', selected,
                                  '--file', str(source), f'--rate={rate:+d}%',
                                  '--write-media', str(output)], 35)
                        validate_audio(output)
                        self.providers[language] = 'edge-tts'
                        return output.read_bytes(), selected, 'edge-tts'
                    except (RuntimeError, OSError, subprocess.TimeoutExpired) as exc:
                        detail = str(exc).replace(text, '[narration]')
                        # TimeoutExpired includes argv, which contains only the text file path.
                        failures.append('Edge: '+detail[-1200:])
                        self.log(f'Edge attempt {attempt+1} failed: '+detail[-1200:])
                self.edge_retry_at = time.monotonic()+600
            if self.mode != 'edge':
                model = 'facebook/mms-tts-'+MMS_LANGUAGES[language]
                self.log(f'Using {model} on CPU (CC-BY-NC-4.0; fixed voice, gender selection unavailable).')
                request = work/'request.json'
                request.write_text(json.dumps({'text': text, 'language': language, 'rate': rate}), encoding='utf-8')
                try:
                    self.run([sys.executable, self.worker, str(request), str(work/'speech.wav')],
                             900 if startup else 150)
                    self.run(['ffmpeg', '-y', '-v', 'error', '-i', str(work/'speech.wav'),
                              '-af', f'atempo={1+rate/100:.2f}', '-codec:a', 'libmp3lame',
                              '-b:a', '128k', str(output)], 30)
                    validate_audio(output)
                    self.providers[language] = 'mms'
                    return output.read_bytes(), model, 'mms'
                except (RuntimeError, OSError, subprocess.TimeoutExpired) as exc:
                    detail = str(exc).replace(text, '[narration]')
                    failures.append('MMS: '+detail[-1200:])
                    self.log('MMS failed: '+detail[-1200:])
            self.providers.pop(language, None)
            raise RuntimeError('Voice generation failed. '+ ' | '.join(failures)
                               +f' Full diagnostic: {self.log_path}')


def mms_worker(request_path, output_path):
    # A short-lived CPU process releases model RAM after every request.
    os.environ.update(CUDA_VISIBLE_DEVICES='', USE_TF='0', USE_FLAX='0', HF_HUB_DISABLE_XET='1')
    import numpy as np
    import torch
    from transformers import AutoTokenizer, VitsModel
    from huggingface_hub import snapshot_download
    torch.set_num_threads(2)
    request = json.loads(Path(request_path).read_text(encoding='utf-8'))
    model_id = 'facebook/mms-tts-'+MMS_LANGUAGES[request['language']]
    patterns = ['*.json', 'model.safetensors']
    try:
        local = snapshot_download(model_id, local_files_only=True, allow_patterns=patterns)
        if not all((Path(local)/name).is_file() for name in
                   ('model.safetensors', 'config.json', 'tokenizer_config.json', 'vocab.json')):
            raise FileNotFoundError('Incomplete voice model cache')
    except (OSError, ValueError):
        local = snapshot_download(model_id, max_workers=1, allow_patterns=patterns)
    tokenizer = AutoTokenizer.from_pretrained(local, local_files_only=True)
    model = VitsModel.from_pretrained(local, local_files_only=True, use_safetensors=True).cpu().eval()
    torch.manual_seed(42)
    with wave.open(str(output_path), 'wb') as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(model.config.sampling_rate)
        for text in chunks(request['text']):
            inputs = tokenizer(text, return_tensors='pt')
            if inputs['input_ids'].numel() < 2:
                raise RuntimeError('Text is unsupported by this voice tokenizer; use the selected language script.')
            with torch.inference_mode():
                data = model(**inputs).waveform.squeeze().float().numpy()
            if not np.isfinite(data).all() or data.size == 0:
                raise RuntimeError('MMS returned invalid audio samples.')
            audio.writeframes((np.clip(data, -1, 1)*32767).astype('<i2').tobytes())
            audio.writeframes(bytes(int(model.config.sampling_rate*.12)*2))


if __name__ == '__main__':
    mms_worker(sys.argv[1], sys.argv[2])
