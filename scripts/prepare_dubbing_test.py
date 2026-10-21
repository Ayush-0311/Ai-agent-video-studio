"""Create a 30-second English source with real speech and known sentence offsets."""
import json
from pathlib import Path
import sys
import time
import requests
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
import main, studio
OUT=ROOT/'backend/studio-data/verification/dubbing-live-2026-10-18'
OUT.mkdir(parents=True,exist_ok=True)
base='http://127.0.0.1:8000'
texts=[
    'Trees help protect riverbanks. Their roots hold the soil together and reduce erosion when rain makes the river rise.',
    'Healthy trees also provide shade. Cooler water can support fish and other wildlife, while leaves offer shelter for insects.',
    'Protecting rivers takes more than planting trees. Keeping waste out of the water also helps protect the surrounding ecosystem.']
health=requests.get(base+'/api/studio/health',timeout=40);health.raise_for_status()
print(json.dumps({k:health.json().get(k) for k in ['ollama','voice','errors']}),flush=True)
if any(j['status'] in ('running','queued') for j in requests.get(base+'/api/studio/jobs',timeout=15).json()):
    raise RuntimeError('An existing job is active; no source requests sent.')
records=[]
for i,text in enumerate(texts):
    path=OUT/f'english-{i}.mp3'
    started=time.monotonic()
    cached=path.exists()
    if not cached:
        r=requests.post(base+'/api/studio/voice-preview',json={'text':text,'language':'en'},timeout=1250)
        r.raise_for_status()
        audio=requests.get(base+r.json()['url'],timeout=60);audio.raise_for_status();path.write_bytes(audio.content)
    duration=float(studio.probe(path)['format']['duration'])
    if not studio.audible(path) or duration>9:raise RuntimeError('Source speech does not fit the 10-second slot.')
    row={'text':text,'start':i*10+1,'duration':duration,'generation_seconds':round(time.monotonic()-started,2),'cached':cached}
    records.append(row);print(json.dumps(row),flush=True)
    (OUT/'source-speech.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
image=ROOT/'backend/studio-data/verification/live-quality-2026-10-17/image-first-frame.png'
inputs=['-loop','1','-i',str(image),'-f','lavfi','-i','anullsrc=r=48000:cl=stereo:d=30']
filters=[]
for i,row in enumerate(records):
    inputs+=['-i',str(OUT/f'english-{i}.mp3')]
    filters.append(f'[{i+2}:a]aresample=48000,aformat=channel_layouts=stereo,adelay={row["start"]*1000}:all=1[a{i}]')
filters.append('[1:a][a0][a1][a2]amix=inputs=4:duration=first:normalize=0[a]')
studio.run([main.FFMPEG_PATH,'-y','-v','error',*inputs,'-filter_complex',';'.join(filters),
    '-map','0:v','-map','[a]','-vf','scale=1280:720','-t','30','-r','30',
    '-c:v','libx264','-preset','fast','-crf','20','-pix_fmt','yuv420p','-c:a','aac','-movflags','+faststart',str(OUT/'english-source-30s.mp4')])
print(json.dumps({'source':str(OUT/'english-source-30s.mp4'),'duration':studio.probe(OUT/'english-source-30s.mp4')['format']['duration']}),flush=True)
