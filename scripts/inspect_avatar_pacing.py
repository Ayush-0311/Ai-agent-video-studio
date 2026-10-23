"""Inspect the supplied export and locate its production report without changing it."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root/'backend'))
from runtime_tools import _find_ffmpeg
import speech_timing

source = Path(sys.argv[1])
output = root/'backend/studio-data/verification/avatar-pacing'
output.mkdir(parents=True, exist_ok=True)
ff = Path(_find_ffmpeg())
info = json.loads(subprocess.check_output([str(ff.with_name('ffprobe.exe')), '-v','error',
    '-show_format','-show_streams','-of','json',str(source)]))
digest = hashlib.sha256(source.read_bytes()).hexdigest()
match = None
for candidate in (root/'backend/studio-data/renders').glob('*/final.mp4'):
    if candidate.stat().st_size == source.stat().st_size and hashlib.sha256(candidate.read_bytes()).hexdigest() == digest:
        match = candidate.parent
        break
report = {'duration':float(info['format']['duration']),
          'quiet_intervals':speech_timing.quiet_intervals(str(ff),source),
          'matching_render':str(match) if match else None}
if match:
    metadata = json.loads((match/'metadata.json').read_text('utf-8'))
    report['project'] = metadata['project']
    report['timeline'] = metadata['timeline']
for second in (2,16,31,46):
    subprocess.run([str(ff),'-y','-v','error','-ss',str(second),'-i',str(source),
        '-frames:v','1','-vf','scale=960:-1',str(output/f'frame-{second}.jpg')],check=True)
(output/'inspection.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=True))
