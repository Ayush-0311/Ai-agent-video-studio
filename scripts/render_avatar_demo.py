"""Offline visual QA demo: prepared vector diagrams + Windows demo narration.

This exercises real composition/export, not Colab image generation or Edge TTS.
Run avatar-demo-voice.ps1 first. Output is separate from user projects.
"""
from pathlib import Path
import sys
import uuid
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'backend'))
import main
import studio
from avatar_presenter import ellipse, color


def main_demo():
    out = ROOT/'backend/studio-data/verification/avatar-demo'
    out.mkdir(parents=True,exist_ok=True)
    studio.DATA = out/'workspace'
    ff = main.FFMPEG_PATH
    art = '''[Script Info]
ScriptType: v4.00+
PlayResX: 960
PlayResY: 540
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Segoe UI,27,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''
    def shape(path, fill):
        return f'Dialogue: 0,0:00:00.00,0:00:02.00,Default,,0,0,0,,{{\\pos(0,0)\\p1\\1c{color(fill)}}}m 0 0 l 0 0 {path}{{\\p0}}\n'
    def label(text,x,y):
        return f'Dialogue: 1,0:00:00.00,0:00:02.00,Default,,0,0,0,,{{\\pos({x},{y})}}{text}\n'
    art += shape(ellipse(155,120,66,66),'F6C95D')
    art += shape('m 230 100 l 310 174 300 180 222 110','E8BD6E')
    art += shape('m 302 164 l 317 189 286 180','E8BD6E')
    art += shape('m 60 460 l 900 460 900 473 60 473','213D4A')
    art += shape('m 285 226 l 550 226 600 391 238 391','417CA1')
    art += shape('m 300 238 l 536 238 579 378 258 378','153E61')
    for x in (350,400,450,500):
        art += shape(f'm {x} 237 l {x+20} 378 {x+24} 378 {x+4} 237','4FA9CD')
    for y in (275,320):
        art += shape(f'm 273 {y} l 562 {y} 563 {y+4} 272 {y+4}','4FA9CD')
    art += shape('m 310 394 l 325 394 325 460 310 460','648793')
    art += shape('m 510 394 l 525 394 525 460 510 460','648793')
    art += shape('m 690 300 l 790 222 897 300','68C9B9')
    art += shape('m 711 300 l 878 300 878 456 711 456','CEE4E2')
    art += shape('m 780 365 l 826 365 826 456 780 456','304F64')
    art += shape('m 733 325 l 765 325 765 362 733 362','5DA9BC')
    art += shape('m 609 327 l 668 327 668 316 692 340 668 364 668 351 609 351','68C9B9')
    art += label('SUNLIGHT',82,205)+label('SOLAR CELLS',321,483)+label('HOME',755,483)
    (out/'diagram.ass').write_text(art,encoding='utf-8-sig')
    studio.run([ff,'-y','-v','error','-f','lavfi','-i','color=c=0x122638:s=960x540',
                '-vf','ass=diagram.ass','-frames:v','1','diagram.png'],cwd=out)
    ident=uuid.uuid4().hex
    meta={'id':ident,'kind':'image','extension':'.png','name':'Solar energy diagram','has_audio':False}
    studio.write_json(studio.path_for('assets',ident),meta)
    studio.path_for('assets',ident,'.png').write_bytes((out/'diagram.png').read_bytes())
    texts=['Solar panels turn sunlight into electricity. Their cells capture energy from the sun.',
           'An inverter makes this power usable at home. Batteries can store extra energy for later.']
    p=studio.Project(title='How solar power works',generation_mode='avatar',resolution='720p',duration=15,
                     presenter_layout='side',presenter_character='alex',captions=True,scenes=[
        studio.Scene(asset_id=ident,end=5,text=texts[0],slide_title='From sunlight to electricity',
                     slide_points=['Solar cells capture light','Direct current (DC) is produced']),
        studio.Scene(asset_id=ident,end=5,text=texts[1],slide_title='Power for everyday life',
                     slide_points=['An inverter supplies usable AC power','Optional batteries store extra energy'])])
    def voice(text,language,output):
        source=out/f'speech-{texts.index(text)+1}.wav'
        studio.run([ff,'-y','-v','error','-i',str(source),str(output)])
        return True
    jid=uuid.uuid4().hex
    studio.JOBS[jid]={'id':jid,'kind':'render','status':'running','progress':0,'project_id':p.id,'events':[]}
    with patch.object(studio,'voice_asset',side_effect=voice):
        studio.worker(jid,studio.render,p)
    job=studio.JOBS[jid]
    if job['status']!='completed':
        raise RuntimeError(job.get('error'))
    rendered=studio.DATA/'renders'/jid/'final.mp4'
    (out/'avatar-explainer-demo.mp4').write_bytes(rendered.read_bytes())
    studio.run([ff,'-y','-v','error','-ss','2','-i',str(rendered),'-frames:v','1',str(out/'preview.png')])
    print(f"Demo exported: {job['result']['duration']:.2f}s; {out/'avatar-explainer-demo.mp4'}")


if __name__ == '__main__':
    main_demo()
