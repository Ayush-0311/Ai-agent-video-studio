"""Real CPU MMS smoke test; writes samples and evidence under verification/."""
import json
import os
from pathlib import Path
import sys
import time

root = Path(__file__).resolve().parents[1]
out = root/'backend/studio-data/verification/colab-voice-2026-10-12'
out.mkdir(parents=True, exist_ok=True)
os.environ['HF_HOME'] = str(root.parent/'.voice-model-cache')
os.environ['HF_HUB_DISABLE_XET'] = '1'
sys.path.insert(0, str(root/'colab'))
from voice_support import VoiceService, validate_audio

service = VoiceService(root/'colab/voice_support.py', out/'voice.log', mode='auto')
# Exercise the actual auto fallback after a recorded Edge outage, without mocking synthesis.
service.edge_retry_at = time.monotonic()+3600
results = []
for language, text in [('hi', 'नमस्ते। आपकी वीडियो की आवाज़ तैयार है।'),
                       ('en', 'Your video narration is ready. This is a real speech test.')]:
    started = time.monotonic()
    data, model, provider = service.synthesize(text, language, 'unused-during-cooldown', -5, startup=True)
    path = out/(language+'.mp3')
    path.write_bytes(data)
    validate_audio(path)
    results.append({'language': language, 'model': model, 'provider': provider,
                    'bytes': len(data), 'seconds': round(time.monotonic()-started, 2),
                    'decode_and_non_silence': True})
    print(json.dumps(results[-1]), flush=True)
(out/'result.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
