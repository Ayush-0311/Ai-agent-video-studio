"""Resumable live English/Hindi planning timing check using saved connections."""
import argparse
import json
from pathlib import Path
import sys
import time

import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'backend/studio-data/verification/planner-speed-2026-10-24'
BASE = 'http://127.0.0.1:8000/api/studio'


def save(name, data):
    (OUT/name).write_text(json.dumps(data,ensure_ascii=False,indent=2),'utf-8')


def api(route, payload=None):
    response=(requests.get(BASE+route,timeout=40) if payload is None else
              requests.post(BASE+route,json=payload,timeout=40))
    response.raise_for_status()
    return response.json()


def run_job(name, route, payload):
    receipt=OUT/(name+'-receipt.json')
    if receipt.exists():
        record=json.loads(receipt.read_text('utf-8'))
    else:
        record=api(route,payload)
        save(receipt.name,record)
    seen=0
    started=time.monotonic()
    while True:
        job=api('/jobs/'+record['id'])
        save(name+'-job.json',job)
        for event in job.get('events',[])[seen:]:
            print(json.dumps({'check':name,**event},ensure_ascii=False),flush=True)
        seen=len(job.get('events',[]))
        if job['status'] in ('completed','failed','cancelled'):
            print(json.dumps({'check':name,'status':job['status'],
                'seconds':job.get('elapsed_seconds'),'error':job.get('error')},ensure_ascii=False),flush=True)
            if job['status']!='completed':
                raise RuntimeError('Live verification did not complete. See '+str(OUT/(name+'-job.json')))
            return job['result']
        if time.monotonic()-started>1200:
            api('/jobs/'+record['id']+'/cancel',{})
            raise RuntimeError('Twenty-minute stage limit reached; cancellation requested.')
        time.sleep(3)


def main():
    global OUT
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--render-hi',action='store_true',help='Also render the Hindi image story with voice and captions.')
    parser.add_argument('--language',choices=('both','en','hi'),default='both')
    parser.add_argument('--output-dir',type=Path,default=OUT,help='Use a different folder for a new benchmark; existing receipts resume the previous run.')
    args=parser.parse_args()
    OUT=args.output_dir.resolve()
    sys.stdout.reconfigure(encoding='utf-8')
    OUT.mkdir(parents=True,exist_ok=True)
    owned={json.loads(p.read_text('utf-8'))['id'] for p in OUT.glob('*-receipt.json')}
    if any(j['status'] in ('running','queued') and j['id'] not in owned for j in api('/jobs')):
        raise RuntimeError('Another production is running; no verification submitted.')
    health=api('/health')
    save('health.json',health)
    if not health.get('planner_ready'):
        reason=health.get('planner_error') or '; '.join(health.get('errors',[])) or 'Reconnect Colab.'
        raise RuntimeError('Planner is not ready: '+reason)
    for language in (('en','hi') if args.language=='both' else (args.language,)):
        payload=dict(title='Speed check: solar energy '+language,prompt=
            'Explain how solar panels convert sunlight into electricity for a home. '
            'Give one simple everyday example and mention that they produce less energy without direct sunlight. '
            'Use plain language for beginners.',language=language,duration=20,
            generation_mode='images',scene_mode='auto',duration_mode='target',narration_timing='exact',
            narration=True,captions=True,resolution='720p',research=True,
            style='Documentary photography, natural colors and concrete examples')
        project=run_job('plan-'+language,'/plan',payload)
        if language=='hi' and args.render_hi:
            run_job('render-hi','/render',project)
    print('Saved verification: '+str(OUT),flush=True)


if __name__=='__main__':
    main()
