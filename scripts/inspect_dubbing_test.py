"""Inspect real live dubbing artifacts, preserving a machine-readable report."""
import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root/'backend'))
import main
import studio

folder = root/'backend/studio-data/verification/dubbing-live-2026-10-18/fixed'
job = json.loads((folder/'ui-job.json').read_text('utf-8'))
ui = json.loads((folder/'ui-result.json').read_text('utf-8'))
assert ui.get('passed') and ui.get('job') == job['id'], 'The latest UI run has not finished successfully'
assert job['status'] == 'completed', job.get('error', job['status'])
project = job['result']['project']
video = folder/'hindi-dub-ui.mp4'
info = studio.probe(video)
duration = float(info['format']['duration'])
assert abs(duration-30) < .15, duration
assert studio.audible(video), 'Silent output'
studio.run([main.FFMPEG_PATH,'-v','error','-i',str(video),'-f','null','-'])
segments = project['production_notes']['dubbing']['segments']
for segment in segments:
    assert segment['audio_end'] <= segment['slot_end']+.02, segment
for scene in project['scenes']:
    words = scene['caption_words']
    assert words and len(words)>1
    assert all(scene['start'] <= w['start'] < w['end'] <= scene['end']+.01 for w in words)
    assert all(a['end'] <= b['start']+.02 for a,b in zip(words,words[1:]))
for second in (4,14,24):
    studio.run([main.FFMPEG_PATH,'-y','-v','error','-ss',str(second),'-i',str(video),
                '-frames:v','1',str(folder/f'frame-{second}.png')])
report = {'job':job['id'],'duration':duration,'audible':True,'decode_passed':True,'caption_bounds_passed':True,
          'segments':segments,'streams':[{k:s.get(k) for k in ('codec_type','codec_name','width','height','r_frame_rate')}
                                        for s in info['streams']]}
(folder/'inspection.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
if '--speech-check' in sys.argv:
    # Independent recognition of the rendered sound; keep separate from forced
    # alignment. Recognition itself can be wrong, so this is review evidence.
    segments, _ = studio.ENV['get_whisper_model']().transcribe(str(video),language='hi',task='translate',beam_size=5)
    recognized = [{'start':s.start,'end':s.end,'english':s.text} for s in segments]
    (folder/'speech-review.json').write_text(json.dumps(recognized,ensure_ascii=False,indent=2),encoding='utf-8')
sys.stdout.reconfigure(encoding='utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2))
