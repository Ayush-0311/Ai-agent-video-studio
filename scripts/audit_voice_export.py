"""Real neural voice -> HTTP preview -> avatar MP4 -> download, isolated from user projects."""
from pathlib import Path
import json
import sys
import time
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
import studio
out=ROOT/'backend/studio-data/verification/voice-export-audit'/uuid.uuid4().hex
out.mkdir(parents=True)
studio.DATA=out/'workspace'
import main
from fastapi.testclient import TestClient

client=TestClient(main.app)
def checked(response):
    response.raise_for_status()
    return response.json()

prefs=studio.VoiceSettings(voice_profile='hi-swara',voice_gender='female',voice_delivery='natural').model_dump()
checked(client.put('/api/studio/voice-settings',json=prefs))
assert checked(client.get('/api/studio/settings'))['voice_profile']=='hi-swara'
text='नमस्ते। सूरज की रोशनी से बिजली बनती है।'
preview=checked(client.post('/api/studio/voice-preview',json={'language':'hi','text':text}))
assert preview['voice']['voice']=='hi-IN-SwaraNeural'
audio=client.get(preview['url']);audio.raise_for_status()
(out/'voice-preview.mp3').write_bytes(audio.content)
print('Live voice preview and audio download passed.',flush=True)
diagram=ROOT/'backend/studio-data/verification/avatar-demo/diagram.png'
with diagram.open('rb') as media:
    asset=checked(client.post('/api/studio/assets',files={'file':('diagram.png',media,'image/png')}))
p=studio.Project(title='Voice integration audit',generation_mode='avatar',presenter_layout='pip-right',
                 resolution='720p',language='hi',captions=True,duration=10,
                 scenes=[studio.Scene(asset_id=asset['id'],text=text,end=5,slide_title='सौर ऊर्जा',slide_points=['सूरज से बिजली'])])
job=checked(client.post('/api/studio/render',json=p.model_dump()))
deadline=time.monotonic()+210
while True:
    current=checked(client.get('/api/studio/jobs/'+job['id']))
    if current['status'] not in ('running','queued'):
        break
    if time.monotonic()>deadline:
        client.post('/api/studio/jobs/'+job['id']+'/cancel')
        raise RuntimeError('Audit timed out; cancellation requested for isolated job.')
    time.sleep(.5)
if current['status']!='completed':
    raise RuntimeError(current.get('error','Render failed'))
video=client.get(current['result']['video_url']);video.raise_for_status()
target=out/'verified-voice-avatar.mp4';target.write_bytes(video.content)
info=studio.probe(target)
assert {'audio','video'} <= {s['codec_type'] for s in info['streams']}
caption=client.get(current['result']['subtitles_url']);caption.raise_for_status()
assert 'सूरज' in caption.content.decode('utf-8-sig')
assert (studio.DATA/'renders'/job['id']/'presenter_000.ass').exists()
report={'voice':preview['voice']['voice'],'duration':float(info['format']['duration']),
        'preview_download':True,'avatar_overlay':True,'mp4_download':True,'hindi_subtitles':True,
        'video':str(target),'cloud_images':'Not tested; prepared image uploaded locally'}
(out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=True),flush=True)
