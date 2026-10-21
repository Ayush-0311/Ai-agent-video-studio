"""Decode and independently transcribe live samples, keeping evidence on disk."""
import json
from pathlib import Path
import subprocess
import sys
import time
sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'backend'))
import main
import studio
import speech_timing
OUT = ROOT/'backend/studio-data/verification/live-quality-2026-10-17'
model = None
for name in sys.argv[1:]:
    path = OUT/name
    info = studio.probe(path)
    started = time.monotonic()
    check = subprocess.run([main.FFMPEG_PATH,'-v','error','-xerror','-i',str(path),'-f','null','-'],capture_output=True,timeout=180)
    result = {'file':name,'duration':float(info['format']['duration']),'decode_ok':check.returncode==0,
              'streams':[{k:s.get(k) for k in ['codec_type','codec_name','width','height','r_frame_rate','sample_rate']} for s in info['streams']],
              'audible':studio.audible(path),'quiet_intervals':speech_timing.quiet_intervals(main.FFMPEG_PATH,path)}
    if model is None:
        model = main.get_whisper_model()
    lang = 'hi' if name == 'hi.mp3' or name.startswith('images') else 'en'
    segments, detected = model.transcribe(str(path),language=lang,beam_size=5,word_timestamps=True,condition_on_previous_text=False)
    result['transcription'] = [{'start':s.start,'end':s.end,'text':s.text,'words':[{'text':w.word,'start':w.start,'end':w.end,'probability':w.probability} for w in s.words or []]} for s in segments]
    if path.suffix == '.mp4':
        for sec in [1,3, max(1,result['duration']-1)]:
            subprocess.run([main.FFMPEG_PATH,'-v','error','-y','-ss',str(sec),'-i',str(path),'-frames:v','1',str(OUT/(path.stem+'-frame-'+str(round(sec,2))+'.png'))],check=True)
    result['inspection_seconds']=round(time.monotonic()-started,2)
    (OUT/(path.stem+'-inspection.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False),flush=True)
