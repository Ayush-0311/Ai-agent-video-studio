"""Make a fuller demo cut, reusing approved images and measuring real narration."""
import hashlib
import json
from pathlib import Path
import sys
import uuid
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
import studio
from runtime_tools import _find_ffmpeg

OUT = ROOT / 'backend/studio-data/verification/motivational-demo'
API = 'http://127.0.0.1:8000/api/studio'
LINES = [
    'ज़िंदगी हमेशा आसान नहीं होती। कभी रास्ते अंधेरे होते हैं, और साथ कोई नहीं होता।',
    'कभी मेहनत के बाद भी सफलता नहीं मिलती। फिर भी सीखना और कोशिश करना छोड़ो मत।',
    'लेकिन हारना और हार मान लेना अलग बातें हैं। हर गलती तुम्हें अगला कदम सिखाती है।',
    'असली जीत तब शुरू होती है, जब तुम मुश्किलों के बावजूद आगे बढ़ते हो। हर सुबह उठो, अपने डर का सामना करो, और एक काम पूरे मन से पूरा करो।',
    'हर छोटा कदम तुम्हें तुम्हारी मंज़िल के करीब ले जाता है। आज थोड़ा सीखो, कल थोड़ा बेहतर बनो। छोटी कोशिशें जब रोज़ दोहराई जाती हैं, तभी बड़ा बदलाव आता है।',
    'आज की मेहनत ही कल तुम्हारी पहचान बनेगी। तालियों का इंतज़ार मत करो। जब कोई नहीं देख रहा हो, तब भी ईमानदारी से काम करो। तुम्हारा अनुशासन ही तुम्हारी ताकत है।',
    'इसलिए खुद पर भरोसा रखो और तब तक मत रुको, जब तक अपने सपनों के लिए पूरी कोशिश न कर लो। अपनी तुलना दूसरों से नहीं, अपने कल से करो।',
    'हार मत मानना… तुम्हारी कहानी अभी बाकी है। बस एक कदम और बढ़ाओ। आगे बढ़ते रहो।',
]

def main():
    submitted = OUT / 'fuller-submission.json'
    if submitted.exists():
        print('Existing fuller demo job: ' + json.loads(submitted.read_text('utf-8'))['id'], flush=True)
        return
    original = json.loads((OUT / 'submission.json').read_text('utf-8'))['id']
    response = requests.get(API + '/jobs/' + original, timeout=20)
    response.raise_for_status()
    if response.json()['status'] != 'completed':
        raise RuntimeError('Wait for the first production export before preparing the fuller cut.')
    meta = json.loads((studio.DATA / 'renders' / original / 'metadata.json').read_text('utf-8'))
    project = studio.Project.model_validate(meta['project'])
    cfg = studio.settings()
    response = requests.get(cfg.image_url.rstrip('/') + '/health', headers=studio.headers(cfg), timeout=30)
    response.raise_for_status()
    if response.json().get('reference_encoding') != 'separate-clip-v1':
        raise RuntimeError('Connect the updated memory-safe Colab setup before preparing character-reference images.')
    studio.ENV['FFMPEG_PATH'] = _find_ffmpeg()
    cache = studio.DATA / 'cache'
    image_identity = studio.bridge_cache.identity(cfg, 'image')
    workflow = project.production_notes['agent_workflow']
    character = workflow['characters'][0]
    reference_name = project.production_notes['character_reference']['cache_key'] + '.png'
    state_path = OUT / 'fuller-state.json'
    state = json.loads(state_path.read_text('utf-8')) if state_path.exists() else {'project_id': uuid.uuid4().hex, 'assets': {}}
    project.id = state['project_id']
    project.title = 'Your Story Is Not Over — 60s Hindi Demo'
    project.transition = 'fade_black'
    project.transition_duration = .18
    project.music_volume = .22
    durations = []
    for i, scene in enumerate(project.scenes):
        # This supplied story explicitly shows the same man in all eight shots.
        # Repair the live director's missing links using that known story, rather
        # than attaching a person to unrelated shots in the generic pipeline.
        scene.visual_prompt = scene.visual_prompt + ' ' + character['appearance'] + '.'
        parts = ['sdxl-v2', scene.visual_prompt or scene.text, project.style, project.aspect_ratio, image_identity, cfg.image_quality]
        parts += ['reference-v1', reference_name]
        source = cache / (hashlib.sha256(json.dumps(parts, sort_keys=True).encode()).hexdigest() + '.png')
        if not source.is_file():
            print(f'Generating reference-conditioned scene image {i+1}/8', flush=True)
            try:
                studio.image_asset(scene.visual_prompt, project.style, project.aspect_ratio, source, cache / reference_name)
            except Exception as exc:
                (OUT / 'fuller-last-error.json').write_text(json.dumps({'stage':'image', 'scene':i+1, 'error':str(exc)}, indent=2), 'utf-8')
                raise
        state.setdefault('source_images', {})[scene.id] = str(source)
        if scene.id not in state['assets']:
            with source.open('rb') as file:
                response = requests.post(API + '/assets', files={'file': (f'motivational-scene-{i+1}.png', file, 'image/png')}, timeout=60)
            response.raise_for_status()
            state['assets'][scene.id] = response.json()['id']
            state_path.write_text(json.dumps(state, indent=2), 'utf-8')
        scene.asset_id = state['assets'][scene.id]
        scene.rendered_asset = None
        scene.text = LINES[i]
        scene.caption_words = []
        scene.caption_source_text = ''
        scene.speed = 1
    # Complete images before loading voice, so the GPU swaps model families once.
    for i, scene in enumerate(project.scenes):
        print(f'Measuring fuller narration {i+1}/8', flush=True)
        _, duration = studio.scene_voice(project, scene, cache, f'Demo scene {i+1}')
        durations.append(duration)
        print(f'Scene {i+1}: {duration:.2f}s', flush=True)
    total = sum(durations)
    speed = total / 58.0
    (OUT / 'fuller-voice-measurements.json').write_text(json.dumps({'durations': durations, 'total': total, 'speed_to_fill_58s': speed}, indent=2), 'utf-8')
    if not .9 <= speed <= 1.1:
        raise RuntimeError(f'Fuller narration totals {total:.2f}s. Revise text before export rather than using extreme voice speed.')
    # Real measured voice occupies 58s; distribute 2s of short pauses across 8 scenes.
    speech_frames = [d / speed * 30 for d in durations]
    frames = [round(n + 7.5) for n in speech_frames]
    frames[-1] += 1800 - sum(frames)
    for scene, count in zip(project.scenes, frames):
        scene.start = 0
        scene.end = count / 30 * speed
        scene.speed = speed
    project.character_reference = False  # The imported original images already share their generated reference.
    project.production_notes['demo_edit'] = {'source_job': original, 'narration': 'Expanded original lines to avoid long gaps', 'measured_voice_seconds': total, 'playback_speed': speed}
    project.production_notes.pop('ready_script', None)
    project.prompt = '60-second Hindi motivational demo, fuller narration, original generated scene images. ' + ' '.join(LINES)
    payload = project.model_dump()
    (OUT / 'fuller-request.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2), 'utf-8')
    response = requests.post(API + '/render', json=payload, timeout=30)
    response.raise_for_status()
    job = response.json()
    submitted.write_text(json.dumps(job, ensure_ascii=False, indent=2), 'utf-8')
    print('Fuller demo submitted: ' + job['id'], flush=True)

if __name__ == '__main__':
    main()
