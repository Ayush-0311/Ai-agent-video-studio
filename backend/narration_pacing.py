"""Use measured narration pace to avoid unnecessary script/TTS regeneration."""
import hashlib
import json
import math
from pathlib import Path
import statistics
import threading
import time

LOCK = threading.RLock()
MAX_AGE = 30 * 86400


def profile_path(folder, identity):
    key=hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()
    return Path(folder)/(key+'.json')


def samples(path):
    try:
        rows=json.loads(path.read_text('utf-8'))
        if not isinstance(rows,list):
            return []
        now=time.time()
        return [r for r in rows[-8:] if isinstance(r,dict)
                and isinstance(r.get('id'),str)
                and all(isinstance(r.get(k),(int,float)) and not isinstance(r[k],bool)
                        and math.isfinite(r[k]) for k in ('words','seconds','at'))
                and 12 <= r['words'] <= 5000 and 3 <= r['seconds'] <= 1800
                and .75 <= r['words']/r['seconds'] <= 6
                and 0 <= now-r['at'] <= MAX_AGE]
    except (OSError,ValueError):
        return []


def observe(folder, identity, text, seconds):
    words=len(text.split())
    if (not math.isfinite(seconds) or not 3 <= seconds <= 1800 or words < 12
            or words > 5000 or not .75 <= words/seconds <= 6):
        return
    path=profile_path(folder,identity)
    sample={'id':hashlib.sha256(text.encode()).hexdigest(), 'words':words,
            'seconds':seconds, 'at':time.time()}
    with LOCK:
        rows=[r for r in samples(path) if r['id'] != sample['id']]
        rows=(rows+[sample])[-8:]
        try:
            path.parent.mkdir(parents=True,exist_ok=True)
            temp=path.with_suffix('.tmp')
            temp.write_text(json.dumps(rows),'utf-8')
            temp.replace(path)
        except OSError:
            # Optional optimization: a read-only cache must not break a valid video.
            pass


def measured_rate(folder, identity):
    with LOCK:
        rows=samples(profile_path(folder,identity))
    if len({r['id'] for r in rows}) < 2 or sum(r['words'] for r in rows) < 32:
        return None
    return statistics.median(r['words']/r['seconds'] for r in rows)
