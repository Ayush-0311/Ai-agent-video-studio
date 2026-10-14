"""No-key MuseTalk client; narration remains authoritative export audio."""
import base64
import hashlib
import json
import tempfile
import time
import uuid
from pathlib import Path


def readiness(studio):
    cfg = studio.settings()
    try:
        if not cfg.image_url:
            raise ValueError('No bridge')
        response = studio.requests.get(cfg.image_url.rstrip('/')+'/health', headers=studio.headers(cfg), timeout=15)
        response.raise_for_status()
        data = response.json()
        ready = data.get('presenter_available') is True
        if not ready and data.get('presenter_setup_error'):
            if 'matplotlib_inline.backend_inline' in str(data['presenter_setup_error']):
                return {'available':False, 'tested':False,
                        'message':'Colab is connected, but its notebook plotting setting blocked the talking-avatar setup. '
                                  'Run the updated SmartEdit notebook (MuseTalk Agg fix), then reconnect and Test 5 seconds. '
                                  'Image story and Illustrated presenter still work.'}
            return {'available':False, 'tested':False,
                    'message':'MuseTalk setup failed in Colab. Check its installation log and rerun the updated notebook. Other video modes remain available.'}
        return {'available':ready, 'tested':data.get('presenter_tested') is True, 'message':
            'MuseTalk setup ready. Run a 5-second test; your avatar is created automatically.' if ready else
            'Enable realistic presenter in the updated Colab notebook, run the cell, then reconnect.'}
    except Exception as exc:
        return {'available':False,'tested':False,'message':
            'Connect the updated Colab notebook with Enable realistic presenter selected.' if not cfg.image_url else
            studio.connection_failure(exc,'Presenter connection')['message']}


def validate(project, studio, require_service=True):
    source = None
    # Retain source clips only for existing saved projects. New requests create a face.
    if project.presenter_asset_id:
        meta, source = studio.asset(project.presenter_asset_id)
        if meta['kind'] != 'video' or not 2 <= meta['duration'] <= 30:
            raise ValueError('Use a presenter video between 2 and 30 seconds. Its original audio is replaced.')
    if not project.narration:
        raise ValueError('Realistic presenter needs narration. Turn on Add narration.')
    if require_service:
        state = readiness(studio)
        if not state['available']:
            raise ValueError(state['message'])
    return source


def source_video(jid, project, cache, studio):
    """Create one reusable face, then normalize it for the existing Colab protocol.

    Portrait identity is independent of scene text, output ratio and duration, so
    testing, previews and final renders use the same face. No user upload needed.
    """
    if project.presenter_asset_id:
        return studio.asset(project.presenter_asset_id)[1]
    cfg = studio.settings()
    appearance = ('adult male educator, short dark hair, clean shaven' if
                  project.presenter_character == 'alex' else
                  'adult female educator, long dark hair tucked behind the shoulders')
    backdrop = 'muted teal' if project.presenter_theme == 'teal' else 'muted indigo'
    prompt = ('Professional studio headshot of one fictional ' + appearance +
              ', centered frontal view, looking directly into the camera, entire head and shoulders visible, '
              'face fills the center of the frame, eyes open, relaxed closed mouth, '
              'friendly calm expression, natural facial proportions, even soft lighting on the lips, '
              'simple smart casual clothing, plain ' + backdrop + ' background, '
              'no text, no watermark, no collage, no other people, no hands near the face')
    style = 'photorealistic portrait photography, sharp unobstructed face, detailed natural skin'
    key = hashlib.sha256(json.dumps(['auto-portrait-v1', prompt, style, cfg.image_quality]).encode()).hexdigest()
    cache.mkdir(parents=True, exist_ok=True)
    portrait, source = cache/('avatar-'+key+'.png'), cache/('avatar-'+key+'.mp4')
    studio.checkpoint(jid)
    if source.exists():
        # Do not keep reusing a damaged cache after a disk or interrupted-write problem.
        try:
            studio.probe(source)
            studio.event(jid,'Avatar creator','running','Reusing your generated avatar; no clip upload is needed.')
            return source
        except Exception:
            source.unlink(missing_ok=True)
    studio.event(jid,'Avatar creator','running','Creating your presenter face before lip-sync. No clip upload is needed.')
    with tempfile.TemporaryDirectory(prefix='avatar-',dir=cache) as directory:
        work = Path(directory)
        if not portrait.exists():
            pending = work/'portrait.png'
            studio.image_asset(prompt,style,'1:1',pending)
            studio.checkpoint(jid)
            studio.run([studio.ENV['FFMPEG_PATH'],'-v','error','-xerror','-i',str(pending),'-frames:v','1','-f','null','-'])
            pending.replace(portrait)
        pending = work/'source.mp4'
        # MuseTalk loops these frames to the narration length and animates the mouth.
        # This does not synthesize head movements or a full-body performance.
        studio.run([studio.ENV['FFMPEG_PATH'],'-y','-v','error','-loop','1','-i',str(portrait),
            '-t','2','-an','-vf','scale=512:512:force_original_aspect_ratio=decrease:force_divisible_by=2,'
            'pad=512:512:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=25',
            '-c:v','libx264','-crf','18','-pix_fmt','yuv420p',str(pending)])
        studio.checkpoint(jid)
        studio.probe(pending)
        pending.replace(source)
    return source


def generate(jid, source, voice, seconds, speed, output, studio):
    checkpoint = lambda: studio.checkpoint(jid)
    checkpoint()
    ff = studio.ENV['FFMPEG_PATH']
    with tempfile.TemporaryDirectory(prefix='presenter-',dir=output.parent) as directory:
        work = Path(directory)
        video, audio = work/'presenter.mp4', work/'voice.wav'
        studio.run([ff,'-y','-v','error','-i',str(source),'-t','30','-an','-vf',
            'scale=512:512:force_original_aspect_ratio=decrease:force_divisible_by=2,fps=25,setsar=1',
            '-c:v','libx264','-crf','20','-pix_fmt','yuv420p',str(video)])
        studio.run([ff,'-y','-v','error','-i',str(voice),'-af',f'atempo={speed},apad',
            '-t',str(seconds),'-ar','16000','-ac','1',str(audio)])
        cfg = studio.settings()
        base = cfg.image_url.rstrip('/')+'/presenter/jobs'
        ident = uuid.uuid4().hex
        payload = {'id':ident,'video':base64.b64encode(video.read_bytes()).decode(),
                   'audio':base64.b64encode(audio.read_bytes()).decode()}
        if len(payload['video']) > 28_000_000:
            raise ValueError('Presenter clip is too large. Use a shorter clip.')
        try:
            checkpoint()
            for attempt in range(3):
                try:
                    response = studio.requests.post(base,headers=studio.headers(cfg),json=payload,timeout=60)
                    response.raise_for_status()
                    break
                except (studio.requests.Timeout,studio.requests.ConnectionError):
                    checkpoint()
                    if attempt == 2:
                        raise
            deadline, previous = time.monotonic()+3600, ''
            while time.monotonic() < deadline:
                checkpoint()
                response = studio.requests.get(base+'/'+ident,headers=studio.headers(cfg),timeout=30)
                response.raise_for_status()
                job = response.json()
                message = job.get('message','Generating lip-sync on Colab')
                if message != previous:
                    studio.event(jid,'Realistic presenter','running',message)
                    previous = message
                if job['status'] == 'completed':
                    break
                if job['status'] in ('failed','cancelled'):
                    raise RuntimeError(job.get('error') or 'Presenter generation cancelled.')
                time.sleep(2)
            else:
                raise RuntimeError('Presenter generation exceeded one hour. Try the 5-second test first.')
            checkpoint()
            response = studio.requests.get(base+'/'+ident+'/file',headers=studio.headers(cfg),timeout=120)
            response.raise_for_status()
            if not response.headers.get('content-type','').startswith('video/'):
                raise RuntimeError('Presenter service returned no video. No illustrated fallback was used.')
            temp = work/'result.mp4'
            temp.write_bytes(response.content)
            info = studio.probe(temp)
            if not any(s.get('codec_type')=='video' for s in info.get('streams',[])) or abs(float(info['format']['duration'])-seconds) > .25:
                raise RuntimeError('Presenter output duration does not match narration. Retry the presenter test.')
            studio.run([ff,'-v','error','-xerror','-i',str(temp),'-f','null','-'])
            checkpoint()
            temp.replace(output)
        except Exception:
            try:
                studio.requests.post(base+'/'+ident+'/cancel',headers=studio.headers(cfg),timeout=10)
            except studio.requests.RequestException:
                pass
            raise


def cached_clip(jid, project, voice, seconds, speed, cache, studio):
    source = source_video(jid,project,cache,studio)
    digest = hashlib.sha256(json.dumps(['musetalk-v15-v1',seconds,speed]).encode())
    for file in (source,voice):
        with file.open('rb') as stream:
            for block in iter(lambda:stream.read(1024*1024),b''):
                digest.update(block)
    output = cache/('presenter-'+digest.hexdigest()+'.mp4')
    if not output.exists():
        generate(jid,source,voice,seconds,speed,output,studio)
    else:
        studio.event(jid,'Realistic presenter','running','Reusing lip-sync for the unchanged presenter and narration.')
    return output


def overlay_graph(width,height,layout,input_index,duration):
    from avatar_presenter import geometry
    _,(x,y,box_width),_ = geometry(width,height,layout)
    w = max(2,int(box_width)//2*2)
    h = max(2,int(box_width*(430/320 if layout=='side' else 1))//2*2)
    return (f';[{input_index}:v]setpts=PTS-STARTPTS,fps=30,'
            f'scale={w}:{h}:force_original_aspect_ratio=decrease:force_divisible_by=2,'
            f'pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=0x101724,setsar=1,'
            f'tpad=stop_mode=clone:stop_duration=0.25,trim=duration={duration}[realface];'
            f'[presented][realface]overlay={int(x)}:{int(y)}:eof_action=pass:shortest=0[withface]')
