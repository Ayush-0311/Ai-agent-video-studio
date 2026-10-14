"""Generate short Hindi + Indian-English samples through the real online voice engine."""
from pathlib import Path
import json
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
import main
import studio
import narration

out=ROOT/'backend/studio-data/verification/neural-voices'
out.mkdir(parents=True,exist_ok=True)
results=[]
for profile,language,text in [
    ('hi-swara','hi','नमस्ते! आइए, सौर ऊर्जा को आसान भाषा में समझते हैं। सूरज की रोशनी से हम बिजली बना सकते हैं।'),
    ('en-neerja','en','Let’s explore this idea together. Solar panels turn sunlight into electricity for our homes.')]:
    cfg=studio.Settings(voice_profile=profile,voice_gender='female',voice_engine='neural')
    target=out/(profile+'.mp3')
    narration.synthesize(text,language,target,cfg,main.FFMPEG_PATH,studio.run,studio.probe)
    info=studio.probe(target)
    results.append({'profile':profile,'voice':narration.resolve(cfg,language)['voice'],
                    'duration':float(info['format']['duration']),'bytes':target.stat().st_size})
    print(json.dumps(results[-1]),flush=True)
(out/'result.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
