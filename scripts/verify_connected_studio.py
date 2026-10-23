"""Resumable sequential production checks; never change saved service settings."""
import json
from pathlib import Path
import sys
import time
import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'backend/studio-data/verification/connected-review-2026-10-23'
if '--fixed' in sys.argv:
    OUT = OUT/'fixed'
if '--round-two' in sys.argv:
    OUT = OUT/'round-two'
if '--reasoning' in sys.argv:
    OUT = OUT/'reasoning'
if '--timing-fix' in sys.argv:
    OUT = OUT/'timing-fix'
BASE = 'http://127.0.0.1:8000'
OUT.mkdir(parents=True, exist_ok=True)
sys.stdout.reconfigure(encoding='utf-8')

def save(name, value):
    (OUT/name).write_text(json.dumps(value, ensure_ascii=False, indent=2), 'utf-8')

def api(route, payload=None, timeout=60):
    response = requests.get(BASE+'/api/studio'+route, timeout=timeout) if payload is None else requests.post(
        BASE+'/api/studio'+route, json=payload, timeout=timeout)
    response.raise_for_status()
    return response.json()

def fetch(url, name):
    response = requests.get(BASE+url, timeout=180)
    response.raise_for_status()
    (OUT/name).write_bytes(response.content)

def main():
    save('health.json', api('/health'))
    save('presenter.json', api('/presenter-status'))
    owned = {json.loads(p.read_text('utf-8'))['id'] for p in OUT.glob('*-receipt.json')}
    if any(j['status'] in ('running','queued') and j['id'] not in owned for j in api('/jobs')):
        raise RuntimeError('Another user job is running; no review job submitted.')
    for language, text in [('hi','पेड़ों की जड़ें मिट्टी को पकड़कर नदी के किनारों का कटाव कम करती हैं।'),
                           ('en','Tree roots hold soil together and help reduce erosion along riverbanks.')]:
        if '--skip-voice' in sys.argv:
            break
        name = 'voice-'+language
        if (OUT/(name+'.json')).exists():
            continue
        started = time.monotonic()
        print('Generating '+name, flush=True)
        result = api('/voice-preview', {'language':language, 'text':text}, timeout=1250)
        fetch(result['url'],name+'.mp3')
        save(name+'.json', {'seconds':round(time.monotonic()-started,2),'text':text,'provider':result.get('voice')})
        print(name+' complete', flush=True)
    common = dict(duration_mode='target', narration_timing='exact', resolution='720p',
                  aspect_ratio='16:9', scene_mode='auto', narration=True,captions=True,
                  style='Documentary photography, natural colors, concrete real-world examples',
                  character_reference=False, motion_preset='preview', research=True)
    stages = [
        ('images-hi','/generate',dict(common,title='Live review: riverbanks Hindi',duration=20,
            language='hi',generation_mode='images',prompt='Explain how tree roots reduce riverbank erosion. Give a concrete example and mention that trees alone cannot prevent all flooding. Simple Hindi for beginners.')),
        ('motion-en','/generate',dict(common,title='Live review: river motion English',duration=10,
            language='en',generation_mode='motion',prompt='Explain how flowing water wears away an unprotected riverbank. Show a flowing river beside exposed soil. One simple factual idea.')),
        ('presenter-hi','/presenter-test',dict(common,title='Live review: Hindi talking avatar',duration=10,
            language='hi',generation_mode='avatar',presenter_kind='realistic',presenter_character='alex')),
    ]
    for name, route, payload in stages:
        if '--only' in sys.argv and name != sys.argv[sys.argv.index('--only')+1]:
            continue
        receipt = OUT/(name+'-receipt.json')
        if receipt.exists():
            record = json.loads(receipt.read_text('utf-8'))
        else:
            record = api(route,payload)
            record['review_started_at'] = time.time()
            save(name+'-receipt.json',record)
        seen = 0
        while True:
            job = api('/jobs/'+record['id'])
            save(name+'-job.json',job)
            for event in job.get('events',[])[seen:]:
                print(json.dumps({'stage':name,'event':event},ensure_ascii=False),flush=True)
            seen = len(job.get('events',[]))
            if job['status'] in ('completed','failed','cancelled'):
                break
            if time.time()-record['review_started_at'] > 7200:
                api('/jobs/'+record['id']+'/cancel',{})
                raise RuntimeError('Two-hour review stage limit reached; cancellation requested.')
            time.sleep(5)
        summary = {'status':job['status'],'job':record['id'],
                   'seconds':round(job.get('finished_at',time.time())-record['review_started_at'],2),'error':job.get('error')}
        if job['status']=='completed':
            result = job['result']
            fetch(result['video_url'],name+'.mp4')
            for key, suffix in [('subtitles_url','.srt'),('metadata_url','-metadata.json')]:
                if result.get(key): fetch(result[key],name+suffix)
            summary['duration'] = result.get('duration')
        save(name+'-result.json',summary)
        print(json.dumps({'stage':name,**summary}),flush=True)

if __name__=='__main__':
    main()
