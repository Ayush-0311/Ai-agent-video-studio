"""Inspect a completed production export without altering its video."""
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from runtime_tools import _find_ffmpeg

def review(job_id):
    folder = ROOT / 'backend/studio-data/renders' / job_id
    target = folder / 'final.mp4'
    report_dir = ROOT / 'backend/studio-data/verification/motivational-demo' / job_id
    report_dir.mkdir(parents=True, exist_ok=True)
    ff = _find_ffmpeg()
    fp = str(Path(ff).with_name('ffprobe.exe')) if Path(ff).is_absolute() else 'ffprobe'
    info = json.loads(subprocess.check_output([fp, '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(target)]))
    subprocess.run([ff, '-v', 'error', '-xerror', '-i', str(target), '-f', 'null', '-'], check=True, capture_output=True, timeout=240)
    video = next(s for s in info['streams'] if s['codec_type'] == 'video')
    meta = json.loads((folder / 'metadata.json').read_text('utf-8'))
    timeline = meta['timeline']
    samples = []
    for i, scene in enumerate(timeline):
        output = report_dir / f'scene-{i+1:02d}.jpg'
        stamp = scene['start'] + min(2, (scene['end'] - scene['start']) / 2)
        subprocess.run([ff, '-v', 'error', '-y', '-ss', str(stamp), '-i', str(target), '-frames:v', '1', '-vf', 'scale=270:480', str(output)], check=True, capture_output=True, timeout=30)
        samples.append(output)
    from PIL import Image, ImageDraw
    sheet = Image.new('RGB', (270*4, 510*2), '#101014')
    draw = ImageDraw.Draw(sheet)
    for i, path in enumerate(samples):
        with Image.open(path) as frame:
            sheet.paste(frame, ((i%4)*270, (i//4)*510))
        draw.text(((i%4)*270+8, (i//4)*510+485), f'Scene {i+1}', fill='white')
    sheet.save(report_dir / 'contact-sheet.jpg')
    result = {'video': str(target), 'duration': float(info['format']['duration']),
              'resolution': [video['width'], video['height']], 'decode_passed': True,
              'audio_present': any(s['codec_type'] == 'audio' for s in info['streams']),
              'scenes': len(timeline), 'caption_timing': meta.get('caption_timing'),
              'visual_generation': meta.get('visual_generation'),
              'timeline': timeline}
    (report_dir / 'review.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), 'utf-8')
    print(json.dumps({k:v for k,v in result.items() if k != 'timeline'}, ensure_ascii=False))

if __name__ == '__main__':
    review(sys.argv[1])
