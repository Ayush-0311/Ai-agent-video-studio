"""LTX 0.9.8 13B distilled image-to-video, embedded in the standalone notebook.

Single-pass schedule follows Lightricks' distilled demo/config. This is not
the optional multi-scale upsampler. Dependencies are imported only on Colab.
"""
import base64
import io
import time

MODEL = 'Lightricks/LTX-Video-0.9.8-13B-distilled'
# Official first_pass timesteps, in Diffusers' 0..1000 units.
# https://github.com/Lightricks/LTX-Video/blob/main/configs/ltxv-13b-0.9.8-distilled.yaml
TIMESTEPS = [1000.0, 993.7, 987.5, 981.2, 975.0, 909.4, 725.0]


def profile(vram_gb, ram_gb, native_bf16):
    # Conservative application guard for unquantized BF16 + model CPU offload.
    # This is not a measured minimum or a promise that every workload will fit.
    available = native_bf16 and vram_gb >= 38 and ram_gb >= 48
    return {'available': available, 'engine': 'ltx-13b', 'family': 'ltx',
            'image_to_video': True, 'model': MODEL, 'dtype': 'bfloat16',
            'frames': 161, 'fps': 30, 'steps': len(TIMESTEPS), 'guidance': 1.0,
            'sizes': {'16:9': (1216, 704), '9:16': (704, 1216), '1:1': (832, 832)},
            'quality': 'quality', 'native_resolution': '704p-class',
            'unavailable_reason': '' if available else
                'LTX 13B BF16 in this setup requires native BF16, at least 38 GiB GPU memory '
                'and 48 GiB system RAM (A100-class Colab). Choose a larger runtime or explicitly select Wan.'}


def settings(profile, preset):
    if preset not in ('preview', 'balanced', 'quality'):
        raise ValueError('Choose preview, balanced or quality motion.')
    result = dict(profile, quality=preset)
    # Keep the distilled schedule intact. Speed presets change pixels/frames.
    if preset == 'preview':
        result.update(frames=97, sizes={'16:9': (512, 288), '9:16': (288, 512), '1:1': (384, 384)},
                      native_resolution='288p-class preview')
    elif preset == 'balanced':
        result.update(sizes={'16:9': (832, 480), '9:16': (480, 832), '1:1': (640, 640)},
                      native_resolution='480p-class balanced')
    return result


def decode_image(encoded):
    from PIL import Image
    if not encoded or len(encoded) > 8000000:
        raise ValueError('LTX motion requires a scene image (maximum 8 MB base64). Update the desktop app.')
    try:
        with Image.open(io.BytesIO(base64.b64decode(encoded, validate=True))) as source:
            if source.width * source.height > 1536 * 1536 or min(source.size) < 64:
                raise ValueError('Unsupported dimensions')
            source.load()
            return source.convert('RGB')
    except Exception as exc:
        raise ValueError('Invalid LTX scene image. Use a PNG/JPEG up to 1536 x 1536 pixels.') from exc


def generate(state, folder, payload, options, progress):
    """Caller owns the shared GPU lock and releases other model families first."""
    import torch
    from PIL import Image, ImageOps
    from diffusers import LTXConditionPipeline

    image = decode_image(payload.get('source_image', ''))
    width, height = options['sizes'][payload['aspect_ratio']]
    image = ImageOps.fit(image, (width, height), method=Image.Resampling.LANCZOS)
    if state['motion_pipe'] is None:
        progress('Loading LTX 13B distilled from cache; BF16 with model CPU offload')
        pipe = LTXConditionPipeline.from_pretrained(folder, torch_dtype=torch.bfloat16,
            low_cpu_mem_usage=True, local_files_only=True, use_safetensors=True)
        pipe.vae.enable_tiling()
        pipe.enable_model_cpu_offload()
        state['motion_pipe'] = pipe
    pipe = state['motion_pipe']
    progress(f"LTX image-to-video: {width}x{height}, {options['frames']} frames, {len(TIMESTEPS)} distilled steps")
    started = time.monotonic()

    def on_step(pipeline, step, timestep, tensors):
        elapsed = time.monotonic() - started
        remaining = elapsed / (step + 1) * (len(TIMESTEPS) - step - 1)
        progress(f'Generating motion: step {step+1}/{len(TIMESTEPS)} · '
                 f'estimated {remaining/60:.1f} min left in this shot')
        return tensors

    with torch.inference_mode():
        return pipe(image=image, frame_index=0, strength=1.0, prompt=payload['prompt'],
            width=width, height=height, num_frames=options['frames'], frame_rate=options['fps'],
            timesteps=TIMESTEPS, num_inference_steps=len(TIMESTEPS), guidance_scale=1.0,
            decode_timestep=0.05, decode_noise_scale=0.025, image_cond_noise_scale=0.15,
            generator=torch.Generator('cpu').manual_seed(payload['seed']),
            callback_on_step_end=on_step, output_type='np').frames[0]
