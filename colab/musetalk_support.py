"""Optional isolated MuseTalk 1.5 runtime for the SmartEdit Colab bridge.
No provider API key. This module uses only the standard library until setup.
"""
import base64
from collections import deque
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import uuid

REVISION = '0a89dec45a0192b824e3cf4daf96c239440c5ed8'
INSTALLER_VERSION = '2026-10-11.2'
ROOT = Path('/content/smartedit-musetalk')
CHECKPOINTS = ('musetalkV15/unet.pth','musetalkV15/musetalk.json',
    'sd-vae/config.json','sd-vae/diffusion_pytorch_model.bin',
    'whisper/config.json','whisper/pytorch_model.bin','whisper/preprocessor_config.json',
    'dwpose/dw-ll_ucoco_384.pth','face-parse-bisent/79999_iter.pth',
    'face-parse-bisent/resnet18-5c106cde.pth')


def python_path():
    return ROOT/'venv/bin/python'


def child_environment():
    """Keep notebook-specific imports and plotting backends out of GPU workers."""
    env = os.environ.copy()
    for name in ('PYTHONPATH', 'PYTHONHOME'):
        env.pop(name, None)
    env.update(PYTHONNOUSERSITE='1', PYTHONUNBUFFERED='1', MPLBACKEND='Agg')
    return env


def run(args, cwd=None, stage='MuseTalk setup'):
    """Surface child stderr in notebooks and retain diagnostics across reruns."""
    ROOT.mkdir(parents=True, exist_ok=True)
    log_path = ROOT/'setup.log'
    tail = deque(maxlen=60)
    env = child_environment()
    print(f'\n[MuseTalk] {stage}', flush=True)
    with log_path.open('a', encoding='utf-8') as log:
        log.write(f'\n[{time.strftime("%Y-%m-%d %H:%M:%S")}] {stage}\n')
        log.flush()
        process = subprocess.Popen([str(x) for x in args], cwd=cwd, env=env,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   text=True, encoding='utf-8', errors='replace', bufsize=1)
        try:
            for line in process.stdout:
                print(line, end='', flush=True)
                log.write(line)
                log.flush()
                tail.append(line[-2000:])
            code = process.wait()
        finally:
            process.stdout.close()
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
    if code:
        detail = ''.join(tail)[-8000:]
        raise RuntimeError(f'{stage} failed (exit {code}). Full log: {log_path}\n{detail}')


def verify_runtime():
    run([python_path(), '-c',
         "import torch; print('Torch:', torch.__version__, 'CUDA:', torch.version.cuda, flush=True); "
         "assert torch.cuda.is_available(), 'CUDA unavailable in MuseTalk Python; select a GPU runtime'; "
         "print('GPU:', torch.cuda.get_device_name(0), flush=True); "
         "x = torch.ones(1, device='cuda'); torch.cuda.synchronize()"],
        stage='Checking isolated CUDA runtime')


def verify_imports():
    # Upstream preprocessing loads DWPose on import, so this runs after downloads.
    run([python_path(), '-c', "import scripts.inference; print('MuseTalk imports passed', flush=True)"],
        ROOT/'repo', stage='Loading MuseTalk and face detection checkpoints')


def check():
    try:
        verified = json.loads((ROOT/'verified.json').read_text())
        return (verified.get('revision') == REVISION and
                verified.get('installer_version') == INSTALLER_VERSION and python_path().is_file() and
                all((ROOT/'repo/models'/name).is_file() and (ROOT/'repo/models'/name).stat().st_size>10 for name in CHECKPOINTS))
    except (OSError,ValueError):
        return False


def install():
    if check():
        (ROOT/'verified.json').unlink(missing_ok=True)
        verify_runtime()
        verify_imports()
        write_verified()
        print('Reusing isolated MuseTalk installation.',flush=True)
        return
    if sys.platform != 'linux':
        raise RuntimeError('This automatic installer is for Google Colab Linux GPU runtimes.')
    if shutil.disk_usage('/content').free < 12*1024**3:
        raise RuntimeError('MuseTalk setup needs at least 12 GiB free disk. Use a fresh Colab runtime.')
    ROOT.mkdir(parents=True,exist_ok=True)
    (ROOT/'verified.json').unlink(missing_ok=True)
    print('Installing optional MuseTalk in its own Python 3.10 environment. First setup downloads several GB.',flush=True)
    run([sys.executable,'-m','pip','install','uv==0.8.22'])
    if not python_path().exists():
        run([sys.executable,'-m','uv','venv','--python','3.10',str(ROOT/'venv')])
    py = python_path()
    run([sys.executable,'-m','uv','pip','install','--python',py,'pip==24.3.1','setuptools==69.5.1','wheel'])
    repo = ROOT/'repo'
    if not (repo/'.git').exists():
        run(['git','clone','--filter=blob:none','--no-checkout','https://github.com/TMElyralab/MuseTalk.git',repo])
    run(['git','checkout',REVISION],repo)
    run([py,'-m','pip','install','torch==2.0.1','torchvision==0.15.2','torchaudio==2.0.2','--index-url','https://download.pytorch.org/whl/cu118'])
    verify_runtime()
    # Inference-only environment; avoid Gradio/TensorFlow dependencies that conflict
    # with the modern SDXL/FLUX environment in the parent notebook.
    run([py,'-m','pip','install','numpy==1.23.5','diffusers==0.30.2','accelerate==0.28.0',
        'opencv-python==4.9.0.80','soundfile==0.12.1','transformers==4.39.2','huggingface-hub==0.30.2',
        'librosa==0.11.0','einops==0.8.1','omegaconf==2.3.0','ffmpeg-python==0.2.0',
        'imageio[ffmpeg]','gdown==5.2.0','requests','numba==0.60.0','mmengine==0.10.7'])
    constraints = ROOT/'constraints.txt'
    constraints.write_text('numpy==1.23.5\ntorch==2.0.1\ntorchvision==0.15.2\ntorchaudio==2.0.2\nopencv-python==4.9.0.80\n')
    run([py,'-m','pip','install','-c',constraints,'mmcv==2.0.1','--only-binary=mmcv','-f',
         'https://download.openmmlab.com/mmcv/dist/cu118/torch2.0/index.html'])
    run([py,'-m','pip','install','-c',constraints,'mmdet==3.1.0','mmpose==1.1.0'])
    run([py,'-m','pip','check'])
    run([py, '-c', 'import numpy, cv2, diffusers, transformers, librosa; import mmcv.ops; import mmpose.apis'],
        repo, stage='Checking Python dependencies and compiled MMCV operators')
    downloader = r'''
from pathlib import Path
from huggingface_hub import snapshot_download
import gdown, urllib.request
root = Path('models')
for repo, folder, names in [
 ('TMElyralab/MuseTalk','',['musetalkV15/unet.pth','musetalkV15/musetalk.json']),
 ('stabilityai/sd-vae-ft-mse','sd-vae',['config.json','diffusion_pytorch_model.bin']),
 ('openai/whisper-tiny','whisper',['config.json','pytorch_model.bin','preprocessor_config.json']),
 ('yzd-v/DWPose','dwpose',['dw-ll_ucoco_384.pth'])]:
 snapshot_download(repo,local_dir=str(root/folder),allow_patterns=names,max_workers=1)
face=root/'face-parse-bisent'; face.mkdir(parents=True,exist_ok=True)
if not (face/'79999_iter.pth').exists():
 target=face/'79999_iter.partial'
 if not gdown.download(id='154JgKpzCPW82qINcVieuPH3fZ2e0P812',output=str(target),quiet=False):
  raise RuntimeError('Face parsing checkpoint download failed; rerun setup.')
 target.replace(face/'79999_iter.pth')
if not (face/'resnet18-5c106cde.pth').exists():
 target=face/'resnet18.partial'
 urllib.request.urlretrieve('https://download.pytorch.org/models/resnet18-5c106cde.pth',target)
 target.replace(face/'resnet18-5c106cde.pth')
'''
    run([py,'-c',downloader],repo,stage='Downloading or reusing MuseTalk checkpoints')
    verify_imports()
    if not all((repo/'models'/p).is_file() and (repo/'models'/p).stat().st_size>10 for p in CHECKPOINTS):
        raise RuntimeError('A MuseTalk checkpoint did not download. Rerun setup.')
    write_verified()
    print('MuseTalk dependencies ready; run the 5-second presenter test in SmartEdit to verify inference.',flush=True)


def write_verified():
    (ROOT/'verified.json').write_text(json.dumps({'revision': REVISION,
        'installer_version': INSTALLER_VERSION, 'inference_tested': False}))


def decode_media(value,limit):
    if not isinstance(value,str) or len(value)>limit*4//3+4:
        raise ValueError('Presenter media exceeds the upload limit.')
    try:
        result=base64.b64decode(value,validate=True)
    except Exception as exc:
        raise ValueError('Invalid presenter media encoding.') from exc
    if not result or len(result)>limit:
        raise ValueError('Empty or oversized presenter media.')
    return result


def infer(payload,progress):
    if not check():
        raise RuntimeError('MuseTalk is not installed. Enable realistic presenter in the notebook and rerun.')
    repo=ROOT/'repo'
    runs=repo/'smartedit_runs';runs.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='job_',dir=runs) as directory:
        work=Path(directory)
        (work/'source.mp4').write_bytes(decode_media(payload['video'],21_000_000))
        (work/'audio.wav').write_bytes(decode_media(payload['audio'],6_000_000))
        # Upstream uses shell-based FFmpeg: only generated relative ASCII paths
        # are handed to it. User filenames and commands never enter those strings.
        relative=work.relative_to(repo).as_posix()
        def probe(file):
            return json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(file)]))
        source=probe(work/'source.mp4'); audio=probe(work/'audio.wav')
        video=next((s for s in source['streams'] if s['codec_type']=='video'),None)
        duration=float(audio['format']['duration'])
        if not video or max(video['width'],video['height'])>512 or not 2<=float(source['format']['duration'])<=30.1:
            raise ValueError('Use a normalized presenter clip between 2 and 30 seconds.')
        if not .1<=duration<=180 or not any(s['codec_type']=='audio' for s in audio['streams']):
            raise ValueError('Invalid presenter narration duration.')
        config={'presenter':{'video_path':relative+'/source.mp4','audio_path':relative+'/audio.wav','result_name':'result.mp4'}}
        (work/'task.json').write_text(json.dumps(config))
        args=[str(python_path()),'-m','scripts.inference','--inference_config',relative+'/task.json',
              '--result_dir',relative+'/output','--unet_model_path','models/musetalkV15/unet.pth',
              '--unet_config','models/musetalkV15/musetalk.json','--version','v15',
              '--use_float16','--batch_size','2','--fps','25']
        progress('Loading MuseTalk and checking the presenter face. Animating the mouth to match narration.')
        with (work/'inference.log').open('w') as log:
            process=subprocess.Popen(args,cwd=repo,stdout=log,stderr=subprocess.STDOUT,
                                     env=child_environment())
            started=time.monotonic()
            try:
                while process.poll() is None:
                    if time.monotonic()-started>3500:
                        raise RuntimeError('MuseTalk timed out. Try a shorter presenter test.')
                    progress(f'Lip-sync generation running: {int(time.monotonic()-started)} seconds elapsed.')
                    time.sleep(2)
                if process.returncode:
                    raise RuntimeError('MuseTalk inference failed. Check Colab GPU memory and use a clear face clip.')
            finally:
                if process.poll() is None:
                    process.terminate()
                    try: process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill();process.wait()
        result=work/'output/v15/result.mp4'
        # Upstream can catch exceptions and exit zero: validate the actual file.
        if not result.is_file():
            raise RuntimeError('MuseTalk produced no video. Use one clearly visible face, with no cuts or occlusion.')
        info=probe(result)
        if abs(float(info['format']['duration'])-duration)>.25 or not any(s['codec_type']=='video' for s in info['streams']):
            raise RuntimeError('MuseTalk output failed the duration/video check.')
        subprocess.run(['ffmpeg','-v','error','-xerror','-i',str(result),'-f','null','-'],check=True,timeout=180)
        progress('Presenter clip encoded and validated.')
        return result.read_bytes()
