"""Bounded-disk Wan download: compact official encoder shards one at a time.

BF16 is a disk representation; the T4 route still runs its existing INT8 text
encoder / FP32 motion computation. No BF16 GPU support is assumed here.
"""
import fnmatch
import gc
import json
from pathlib import Path, PurePosixPath
import shutil
import sys

VERSION = 'encoder-bf16-v1'
ROOT = Path('/content/smartedit-models')
RESERVE = 8 * 1024**3


def child(root, name):
    parts = PurePosixPath(name)
    if parts.is_absolute() or '..' in parts.parts or '\\' in name or ':' in name:
        raise ValueError('Unsafe model filename')
    path = (root / name).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError('Model filename escapes its cache')
    return path


def require_space(path, needed, reserve=RESERVE):
    free = shutil.disk_usage(path).free
    if free < needed + reserve:
        raise RuntimeError(f'Insufficient Colab disk: {free/1024**3:.1f} GiB free, '
            f'{(needed+reserve)/1024**3:.1f} GiB required including working reserve. '
            'Existing completed models are preserved; no unrelated files were deleted.')


def write_json(path, value):
    temporary = path.with_suffix(path.suffix + '.partial')
    temporary.write_text(json.dumps(value, indent=2), encoding='utf-8')
    temporary.replace(path)


def compact_shard(source, output):
    import torch
    from safetensors import safe_open
    from safetensors.torch import save_file
    tensors = {}
    temporary = output.with_suffix('.partial')
    try:
        with safe_open(str(source), framework='pt', device='cpu') as reader:
            for key in reader.keys():
                tensor = reader.get_tensor(key)
                tensors[key] = (tensor.to(torch.bfloat16) if tensor.is_floating_point() else tensor).contiguous()
            tensor = None
        total = sum(t.numel()*t.element_size() for t in tensors.values())
        output.parent.mkdir(parents=True, exist_ok=True)
        save_file(tensors, str(temporary), metadata={'format':'pt'})
        with safe_open(str(temporary), framework='pt', device='cpu') as check:
            if set(check.keys()) != set(tensors):
                raise RuntimeError('Compact encoder verification failed')
        temporary.replace(output)
        return total
    finally:
        tensors.clear()
        gc.collect()
        try:
            import ctypes
            if sys.platform == 'linux':
                ctypes.CDLL(None).malloc_trim(0)
        except (AttributeError, OSError):
            pass
        # This is our own unfinished shard, never an existing model/cache file.
        temporary.unlink(missing_ok=True)


def download(model_id, patterns, progress=print, root=ROOT, reserve=RESERVE):
    from huggingface_hub import HfApi, hf_hub_download
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    info = HfApi().model_info(model_id, files_metadata=True)
    revision = info.sha
    folder = child(root, model_id.replace('/', '--')+'/'+revision+'-'+VERSION)
    folder.mkdir(parents=True, exist_ok=True)
    manifest_path = folder/'smartedit-compact.json'
    try:
        manifest = json.loads(manifest_path.read_text('utf-8'))
        if manifest.get('revision') != revision or manifest.get('version') != VERSION:
            raise ValueError('Different model revision')
    except (OSError, ValueError):
        manifest = {'revision':revision, 'version':VERSION, 'files':{}}
    selected = sorted((f for f in info.siblings if any(fnmatch.fnmatchcase(f.rfilename,p) for p in patterns)),
                      key=lambda f:(not f.rfilename.startswith('text_encoder/'), f.rfilename))
    if not selected or not any(f.rfilename.endswith('.safetensors') and f.rfilename.startswith('text_encoder/') for f in selected):
        raise RuntimeError('Wan encoder shards are missing from the model manifest')
    for item in selected:
        name = item.rfilename
        output = child(folder, name)
        done = manifest['files'].get(name, {})
        if done.get('bytes') and output.is_file() and output.stat().st_size == done['bytes']:
            if name.startswith('text_encoder/') and name.endswith('.safetensors'):
                child(folder/'.source', name).unlink(missing_ok=True)
            continue
        if not isinstance(item.size, int) or item.size <= 0:
            raise RuntimeError('Cannot budget model file: '+name)
        encoder = name.startswith('text_encoder/') and name.endswith('.safetensors')
        # One source shard plus its destination, not the complete FP32 model.
        require_space(folder, int(item.size * (1.6 if encoder else 1)), reserve)
        progress(f'Preparing Wan file {name} ({item.size/1024**3:.2f} GiB); one file at a time')
        if encoder:
            incoming = folder/'.source'
            incoming.mkdir(exist_ok=True)
            source = Path(hf_hub_download(model_id, name, revision=revision, local_dir=str(incoming)))
            if source.resolve() != child(incoming, name):
                raise RuntimeError('Downloader returned a path outside the owned staging directory')
            tensor_bytes = compact_shard(source, output)
            manifest['files'][name] = {'bytes':output.stat().st_size, 'tensor_bytes':tensor_bytes}
            write_json(manifest_path, manifest)
            source.unlink()  # Only our verified, superseded source shard.
        else:
            hf_hub_download(model_id, name, revision=revision, local_dir=str(folder))
            manifest['files'][name] = {'bytes':output.stat().st_size}
            write_json(manifest_path, manifest)
    config_path = folder/'text_encoder/config.json'
    config = json.loads(config_path.read_text('utf-8'))
    config['torch_dtype'] = 'bfloat16'
    write_json(config_path, config)
    index_path = folder/'text_encoder/model.safetensors.index.json'
    if index_path.exists():
        index = json.loads(index_path.read_text('utf-8'))
        index.setdefault('metadata', {})['total_size'] = sum(f.get('tensor_bytes',0) for f in manifest['files'].values())
        write_json(index_path, index)
    for path in (config_path, index_path):
        if path.is_file():
            manifest['files'][path.relative_to(folder).as_posix()]['bytes'] = path.stat().st_size
    manifest['complete'] = True
    write_json(manifest_path, manifest)
    progress('Wan ready: compact encoder stored; original FP32 staging shards removed.')
    return str(folder)
