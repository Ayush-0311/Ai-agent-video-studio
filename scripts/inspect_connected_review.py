"""Decode generated review videos and save frame evidence and timing measurements."""
import json
from pathlib import Path
import re
import subprocess
import sys
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'backend'))
import main
import studio

folder = Path(sys.argv[1])
for file in folder.glob('*.mp4'):
    info = studio.probe(file)
    duration = float(info['format']['duration'])
    subprocess.run([main.FFMPEG_PATH,'-v','error','-xerror','-i',str(file),'-f','null','-'],
                   check=True,capture_output=True,timeout=180)
    frames = []
    for i in range(4):
        target = folder/(file.stem+f'-frame-{i}.jpg')
        subprocess.run([main.FFMPEG_PATH,'-v','error','-y','-ss',str((i+.5)*duration/4),
                        '-i',str(file),'-frames:v','1','-vf','scale=480:-1',str(target)],
                       check=True,capture_output=True,timeout=30)
        with Image.open(target) as image:
            frames.append(image.copy())
    sheet = Image.new('RGB',(960,frames[0].height*2),'black')
    for i,frame in enumerate(frames):
        sheet.paste(frame,((i%2)*480,(i//2)*frame.height))
    sheet.save(folder/(file.stem+'-contact.jpg'))
    subtitles = file.with_suffix('.srt')
    cues = []
    if subtitles.exists():
        for row in subtitles.read_text('utf-8').splitlines():
            if '-->' not in row: continue
            ends = []
            for value in row.split(' --> '):
                h,m,s,ms = map(int,re.split('[:,]',value))
                ends.append(h*3600+m*60+s+ms/1000)
            cues.append(ends)
    report = {'file':file.name,'duration':duration,'decode_passed':True,
              'audible':studio.audible(file),'caption_cues':len(cues),
              'caption_bounds_valid':all(0 <= a < b <= duration+.05 for a,b in cues),
              'streams':[{k:s.get(k) for k in ('codec_type','codec_name','width','height','r_frame_rate')}
                         for s in info['streams']]}
    (folder/(file.stem+'-inspection.json')).write_text(json.dumps(report,indent=2),'utf-8')
    print(json.dumps(report),flush=True)
