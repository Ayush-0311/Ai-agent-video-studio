"""Submit the user's 60-second demo to the running SmartEdit production API."""
import json
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'backend/studio-data/verification/motivational-demo'
OUT.mkdir(parents=True, exist_ok=True)
PROMPT = '''Create a cinematic motivational video, vertical 9:16, in Hindi with a deep male voiceover. Generate all images automatically. Use consistent character appearance: the same 24-year-old Indian man, short wavy black hair, light stubble, lean build, charcoal crew-neck T-shirt. Emotional instrumental background music. Realistic photography, cinematic lighting, tasteful camera movements, synchronized Hindi subtitles. Do not draw lettering inside generated images; screen text is added by the editor.
0–5 sec: Visual: A lonely young man sitting on the edge of a bed in a small dark room, soft blue light from a window, intimate medium shot, thoughtful expression. Voiceover: “ज़िंदगी हमेशा आसान नहीं होती।” Text: “NEVER GIVE UP.”
5–10 sec: Visual: The same young man studying alone at his wooden desk late at night, warm desk lamp, open notebooks, tired eyes but determined expression, cinematic side profile. Voiceover: “कभी मेहनत के बाद भी सफलता नहीं मिलती।” Text: “KEEP GOING.”
10–15 sec: Visual: The same young man disappointed after a setback, seated at his desk, eyes closed and taking a deep breath, soft light on his face, close-up. Voiceover: “लेकिन हारना और हार मान लेना अलग बातें हैं।” Text: “FAIL. LEARN. REPEAT.”
15–25 sec: Visual: The same young man running along an empty path at sunrise, charcoal athletic shirt, golden backlight, morning mist, cinematic wide shot conveying steady effort. Voiceover: “असली जीत तब शुरू होती है, जब तुम मुश्किलों के बावजूद आगे बढ़ते हो।” Text: “DISCIPLINE IS POWER.”
25–35 sec: Visual: The same young man learning new skills at his desk, open notebook and laptop, focused face, daylight entering the room, detailed realistic hands, over-the-shoulder composition. Voiceover: “हर छोटा कदम तुम्हें तुम्हारी मंज़िल के करीब ले जाता है।” Text: “ONE STEP AT A TIME.”
35–45 sec: Visual: The same young man working confidently in a bright room with natural window light, relaxed confident expression, clean desk, cinematic medium close-up, warm color palette. Voiceover: “आज की मेहनत ही कल तुम्हारी पहचान बनेगी।” Text: “YOUR TIME WILL COME.”
45–55 sec: Visual: The same young man standing on a hilltop looking toward a beautiful sunrise, vast landscape and golden clouds, inspiring cinematic composition, three-quarter rear view. Voiceover: “इसलिए खुद पर भरोसा रखो और तब तक मत रुको, जब तक अपने सपनों के लिए पूरी कोशिश न कर लो।” Text: “BELIEVE IN YOURSELF.”
55–60 sec: Visual: Powerful close-up of the same young man's determined face, warm sunrise reflection in his eyes, shallow depth of field, fade to black at the end. Voiceover: “हार मत मानना… तुम्हारी कहानी अभी बाकी है।” Text: “YOUR STORY IS NOT OVER.”'''

payload = dict(title='Your Story Is Not Over — Hindi Motivational Short',
    prompt=PROMPT, language='hi', aspect_ratio='9:16', resolution='1080p',
    duration=60, duration_mode='target', narration_timing='exact',
    generation_mode='images', scene_mode='ready', narration=True,
    captions=True, research=False, auto_music='cinematic', music_volume=.10,
    character_reference=True, script_voice_gender='male', color='warm',
    style='Cinematic realistic photography, consistent Indian male protagonist, emotional lighting, natural anatomy, film still')

if __name__ == '__main__':
    # An existing submission is inspected rather than accidentally duplicated.
    receipt = OUT / 'submission.json'
    if receipt.exists():
        result = json.loads(receipt.read_text('utf-8'))
        print(json.dumps({'existing_job': result['id']}))
    else:
        (OUT / 'request.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2), 'utf-8')
        response = requests.post('http://127.0.0.1:8000/api/studio/generate', json=payload, timeout=30)
        response.raise_for_status()
        result = response.json()
        receipt.write_text(json.dumps(result, ensure_ascii=False, indent=2), 'utf-8')
        print(json.dumps({'id': result['id'], 'status': result['status']}))
