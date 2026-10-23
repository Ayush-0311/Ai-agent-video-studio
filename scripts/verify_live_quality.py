"""Live, sequential benchmark using saved app settings; never modifies settings."""
import json
from pathlib import Path
import sys
import time
import uuid
import requests

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'backend/studio-data/verification/live-quality-2026-10-17'
OUT.mkdir(parents=True, exist_ok=True)
BASE = 'http://127.0.0.1:8000/api/studio'
retry_images = '--images20' in sys.argv
preview_motion = '--motion-preview' in sys.argv
corrected = '--corrected' in sys.argv
results = json.loads((OUT/'results.json').read_text('utf-8')) if (retry_images or preview_motion or corrected) and (OUT/'results.json').exists() else []

def save(name, data):
    (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')

def api(route, payload=None, timeout=30):
    r = requests.get(BASE + route, timeout=timeout) if payload is None else requests.post(BASE + route, json=payload, timeout=timeout)
    r.raise_for_status()
    return r.json()

def record(data):
    results.append(data)
    save('results.json', results)
    print(json.dumps(data, ensure_ascii=False), flush=True)

def download(url, name):
    r = requests.get('http://127.0.0.1:8000' + url, timeout=180)
    r.raise_for_status()
    (OUT / name).write_bytes(r.content)

health = api('/health', timeout=40)
save('health.json', health)
print(json.dumps({'health': {k: health.get(k) for k in ['ollama', 'image', 'voice', 'video_available']}}), flush=True)
if any(j['status'] in ('running', 'queued') for j in api('/jobs')):
    raise RuntimeError('An existing user job is active. Benchmark was not submitted.')
for lang, text in [('hi', 'सुबह की धूप पेड़ों के बीच से आती है। नदी धीरे बह रही है।'), ('en', 'A quiet river flows through the forest. Trees protect the riverbanks and keep the water clean.')]:
    if retry_images or preview_motion or corrected:
        break
    started = time.monotonic()
    try:
        response = api('/voice-preview', {'language': lang, 'text': text}, timeout=1250)
        download(response['url'], lang + '.mp3')
        record({'stage': 'voice-' + lang, 'status': 'completed', 'seconds': round(time.monotonic()-started, 2), 'text': text, 'file': lang + '.mp3', 'voice': response.get('voice')})
    except Exception as exc:
        record({'stage': 'voice-' + lang, 'status': 'failed', 'seconds': round(time.monotonic()-started, 2), 'error': str(exc)})

for mode, lang in ([('images-corrected', 'hi')] if corrected else [('images20', 'hi')] if retry_images else [('motion-preview', 'en')] if preview_motion else [('images', 'hi'), ('motion', 'en')]):
    p = {'id': uuid.uuid4().hex, 'title': 'Live quality review ' + mode + ' ' + lang,
         'prompt': 'Explain how tree roots protect riverbanks. Make exactly one short scene with about 15 spoken words. Show a peaceful forest river in morning sunlight.',
         'language': lang, 'duration': 10, 'duration_mode': 'target', 'narration_timing': 'natural',
         'resolution': '1080p', 'aspect_ratio': '16:9', 'generation_mode': mode,
         'motion_preset': 'balanced', 'style': 'cinematic realism, natural morning light, realistic forest and flowing river',
         'narration': True, 'captions': True, 'research': False, 'scenes': []}
    if retry_images:
        p.update(duration=20,generation_mode='images',prompt='Explain simply in Hindi how tree roots protect riverbanks. Use two short sentences, one per scene, about 24 Hindi words total. Show a peaceful forest river in morning sunlight.')
    endpoint = '/generate'
    if corrected:
        p=json.loads((OUT/'images20-job.json').read_text('utf-8'))['result']['project']
        p.update(id=uuid.uuid4().hex,title='Reviewed Hindi script comparison',language='hi')
        for scene,text in zip(p['scenes'],['पेड़ों की जड़ें मिट्टी को पकड़कर नदी के किनारों का कटाव कम करती हैं।','इससे किनारे मजबूत रहते हैं और बारिश में कम मिट्टी पानी के साथ बहती है।']):
            scene.update(text=text,rendered_asset=None)
        endpoint='/render'
    if preview_motion:
        original=json.loads((OUT/'motion-submitted.json').read_text('utf-8'))
        source=json.loads((ROOT/'backend/studio-data/projects'/(original['project']['id']+'.json')).read_text('utf-8'))
        p=source
        p.update(id=uuid.uuid4().hex,title='Live quality review Preview motion',motion_preset='preview')
        p['scenes']=p['scenes'][:1]
        p['scenes'][0].update(asset_id='',rendered_asset=None)
        endpoint='/render'
    started = time.monotonic()
    try:
        job = api(endpoint, p)
        jid = job['id']
        save(mode + '-submitted.json', {'job': jid, 'project': p, 'started_unix': time.time()})
        print(json.dumps({'submitted': mode, 'job': jid}), flush=True)
        seen = 0
        while time.monotonic()-started < 3600:
            job = api('/jobs/' + jid)
            save(mode + '-job.json', job)
            for event in job.get('events', [])[seen:]:
                print(json.dumps({'mode': mode, 'elapsed': round(time.monotonic()-started, 1), 'event': event}, ensure_ascii=False), flush=True)
            seen = len(job.get('events', []))
            if job['status'] in ('completed', 'failed', 'cancelled'):
                break
            time.sleep(3)
        else:
            api('/jobs/' + jid + '/cancel', {})
            raise RuntimeError('One-hour benchmark limit reached; cancellation requested.')
        result = job.get('result') or {}
        if job['status'] == 'completed':
            download(result['video_url'], mode + '.mp4')
            if result.get('subtitles_url'):
                download(result['subtitles_url'], mode + '.srt')
            if result.get('metadata_url'):
                download(result['metadata_url'], mode + '-metadata.json')
        record({'stage': mode, 'status': job['status'], 'seconds': round(time.monotonic()-started, 2), 'error': job.get('error'), 'duration': result.get('duration'), 'job': jid})
    except Exception as exc:
        record({'stage': mode, 'status': 'failed', 'seconds': round(time.monotonic()-started, 2), 'error': str(exc)})
