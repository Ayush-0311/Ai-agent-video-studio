"""Re-export real cached samples through the current backend, without new GPU inference."""
import json
from pathlib import Path
import shutil
import sys
import time
import uuid
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
sys.stdout.reconfigure(encoding='utf-8')
import main
import studio
OUT=ROOT/'backend/studio-data/verification/live-quality-2026-10-17'
for mode in sys.argv[1:]:
    data=json.loads((OUT/(mode+'-job.json')).read_text('utf-8'))
    project=studio.Project.model_validate(data['result']['project'])
    project.id=uuid.uuid4().hex
    project.title += ' — speech-aligned captions'
    started=time.monotonic()
    job=studio.queue('render',project,studio.render)
    jid=job['id']
    seen=0
    while studio.JOBS[jid]['status'] in ('queued','running'):
        for event in studio.JOBS[jid]['events'][seen:]:print(json.dumps(event,ensure_ascii=False),flush=True)
        seen=len(studio.JOBS[jid]['events'])
        time.sleep(1)
    job=studio.JOBS[jid]
    (OUT/(mode+'-aligned-job.json')).write_text(json.dumps(job,ensure_ascii=False,indent=2),encoding='utf-8')
    if job['status']!='completed':raise RuntimeError(job.get('error',job['status']))
    folder=studio.DATA/'renders'/jid
    for src,suffix in [('final.mp4','.mp4'),('captions.srt','.srt'),('metadata.json','-metadata.json')]:
        shutil.copyfile(folder/src,OUT/(mode+'-aligned'+suffix))
    print(json.dumps({'mode':mode,'seconds':round(time.monotonic()-started,2),'duration':job['result']['duration'],'status':job['status']},ensure_ascii=False),flush=True)
