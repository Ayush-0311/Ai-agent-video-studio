"""Real cached Whisper -> uploaded video -> subtitle burn-in timing audit."""
import json, os, sys, uuid, subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'backend'))
os.environ['HF_HUB_OFFLINE']='1'
import main, studio
from fastapi.testclient import TestClient
out=root/'backend/studio-data/verification/import-caption-timing'
out.mkdir(parents=True,exist_ok=True)
studio.DATA=out/'workspace'
studio.DATA.mkdir(parents=True,exist_ok=True)
ff=main.FFMPEG_PATH
speech=root/'backend/studio-data/verification/colab-voice-2026-10-12/en.mp3'
duration=float(studio.probe(speech)['format']['duration'])+4
source=out/'english-with-pauses.mp4'
studio.run([ff,'-y','-v','error','-f','lavfi','-i','color=c=0x182838:s=640x360:r=30','-i',str(speech),'-af','adelay=2000:all=1,apad','-t',str(duration),'-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac',str(source)])
client=TestClient(main.app)
with source.open('rb') as f:
 response=client.post('/api/studio/assets',files={'file':(source.name,f)})
response.raise_for_status();media=response.json()
p=studio.Project(title='English speech with silent margins',language='en',narration=False,captions=True,resolution='720p',scenes=[studio.Scene(asset_id=media['id'],media_kind='video',end=media['duration'])])
def job():
 j=uuid.uuid4().hex
 studio.JOBS[j]={'id':j,'kind':'render','project_id':p.id,'status':'running','progress':0,'events':[]}
 return j
print('Running real Whisper on uploaded speech...',flush=True)
result=studio.transcribe(job(),studio.TranscribeRequest(project=p,scene_id=p.scenes[0].id))
p=studio.Project.model_validate(result)
print('Recognized:',[(s.text, [w.model_dump() for w in s.caption_words]) for s in p.scenes],flush=True)
j=job();rendered=studio.render(j,p)
import shutil
shutil.copyfile(studio.DATA/'renders'/j/'final.mp4',out/'caption-timing-refined.mp4')
shutil.copyfile(studio.DATA/'renders'/j/'captions.srt',out/'captions.srt')
(out/'result.json').write_text(json.dumps(rendered,indent=2),encoding='utf-8')
print('Saved real caption render:',out/'caption-timing-refined.mp4',flush=True)

# Inspect actual encoded pixels: blank margins, visible subtitle during speech.
video=out/'caption-timing-refined.mp4'
checks=[]
for seconds, expected in [(2.1,False),(2.3,True),(4.35,False),(4.6,True),(6.3,False)]:
    pixels=subprocess.check_output([ff,'-v','error','-ss',str(seconds),'-i',str(video),
        '-vf','crop=iw:160:0:ih-160,format=gray','-frames:v','1','-f','rawvideo','pipe:1'])
    visible=bool(pixels) and max(pixels)>200
    assert visible == expected, f'Unexpected caption visibility at {seconds}: {visible}'
    checks.append({'time':seconds,'caption_visible':visible})
assert all(w['start']>=1.9 and w['end']<=duration-1.9 for t in rendered['timeline'] for w in t['words'])
(out/'frame-checks.json').write_text(json.dumps(checks,indent=2),encoding='utf-8')
print('Encoded frame checks passed:',checks,flush=True)
