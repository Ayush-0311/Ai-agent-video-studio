"""Named online neural narration; no GPU or silent lower-quality fallback."""
import importlib.util
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unicodedata
import speech_timing

VOICES = {
    'hi-madhur': ('hi','hi-IN-MadhurNeural','Madhur · Hindi'),
    'hi-swara': ('hi','hi-IN-SwaraNeural','Swara · Hindi'),
    'en-prabhat': ('en','en-IN-PrabhatNeural','Prabhat · Indian English'),
    'en-neerja': ('en','en-IN-NeerjaNeural','Neerja · Indian English'),
    'en-christopher': ('en','en-US-ChristopherNeural','Christopher · US English'),
    'en-jenny': ('en','en-US-JennyNeural','Jenny · US English'),
}
AUTO = {
    'hi': ('hi-IN-MadhurNeural','hi-IN-SwaraNeural'),
    'en': ('en-IN-PrabhatNeural','en-IN-NeerjaNeural'),
    'es': ('es-ES-AlvaroNeural','es-ES-ElviraNeural'),
    'fr': ('fr-FR-HenriNeural','fr-FR-DeniseNeural'),
    'de': ('de-DE-KillianNeural','de-DE-KatjaNeural'),
}
# Gentle prosody adjustments, not a claim of a supported emotional acting model.
DELIVERY = {'natural': (0,0), 'calm': (-5,-2), 'energetic': (5,2)}


def available():
    return importlib.util.find_spec('edge_tts') is not None


def resolve(cfg, language):
    voice = AUTO[language][cfg.voice_gender == 'female']
    matched = cfg.voice_profile == 'auto'
    if cfg.voice_profile in VOICES:
        lang, selected, _ = VOICES[cfg.voice_profile]
        if lang == language:
            voice, matched = selected, True
    offset, pitch = DELIVERY[cfg.voice_delivery]
    return {'voice':voice, 'rate':max(-20,min(20,cfg.speech_rate+offset)), 'pitch':pitch,
            'profile_matched':matched, 'delivery':cfg.voice_delivery, 'normalize':cfg.voice_normalize}


def cache_identity(cfg, language):
    if cfg.voice_engine == 'bridge':
        # Legacy bridge consumes gender and raw pace, not direct-neural delivery/profile.
        return ['bridge-narration-v2-omnivoice',cfg.image_url,language,cfg.voice_gender,cfg.speech_rate]
    return ['neural-narration-v2-word-timing',cfg.voice_engine,resolve(cfg,language),
            cfg.image_url if cfg.voice_engine=='bridge' else 'direct-online',cfg.voice_gender]


def synthesize(text, language, output, cfg, ffmpeg, run, probe):
    """Bounded child process, validated MP3, then atomic publish to the cache."""
    if not available():
        raise RuntimeError('Neural voice runtime is missing. Run SmartEdit SETUP to install edge-tts.')
    options = resolve(cfg, language)
    output = Path(output)
    output.parent.mkdir(parents=True,exist_ok=True)
    text = unicodedata.normalize('NFC',text).strip()
    if not text:
        raise ValueError('Write narration text before generating speech.')
    with tempfile.TemporaryDirectory(prefix='narration-',dir=output.parent) as work:
        work = Path(work)
        source, speech, final = work/'text.txt', work/'speech.mp3', work/'final.mp3'
        source.write_text(text,encoding='utf-8')
        try:
            result = subprocess.run([sys.executable,str(Path(__file__).with_name('narration_worker.py')),'--voice',options['voice'],
                '--file',str(source),f"--rate={options['rate']:+d}%",f"--pitch={options['pitch']:+d}Hz",
                '--write-media',str(speech),'--write-timings',str(work/'words.json')],capture_output=True,timeout=150)
        except subprocess.TimeoutExpired:
            raise RuntimeError('Neural voice service timed out. Check Internet access and retry the voice preview.') from None
        if result.returncode or not speech.exists() or speech.stat().st_size<100:
            raise RuntimeError('Neural voice service could not generate speech. Check Internet access and retry. No basic-voice fallback was used.')
        try:
            words = json.loads((work/'words.json').read_text('utf-8'))
            raw_duration = float(probe(speech)['format']['duration'])
            if not speech_timing.valid_words(words, raw_duration):
                raise ValueError('Invalid word timings')
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise RuntimeError('Speech timing was incomplete. Retry narration; inaccurate captions were not cached.') from exc
        if options['normalize']:
            run([ffmpeg,'-y','-v','error','-i',str(speech),'-vn','-af',
                 'highpass=f=65,loudnorm=I=-16:TP=-1.5:LRA=11',
                 '-ar','48000','-c:a','libmp3lame','-b:a','192k',str(final)],timeout=120)
        else:
            speech.replace(final)
        info = probe(final)
        if not any(s.get('codec_type')=='audio' for s in info.get('streams',[])) or float(info.get('format',{}).get('duration',0))<=0:
            raise RuntimeError('Neural voice returned invalid audio; no cached speech was replaced.')
        timing = work/'final.words.json'
        timing.write_text(json.dumps({'text':speech_timing.text_key(text), 'words':words,
            'duration':float(info['format']['duration']),
            'audio_sha256':hashlib.sha256(final.read_bytes()).hexdigest()},ensure_ascii=False),encoding='utf-8')
        final.replace(output)
        timing.replace(speech_timing.sidecar(output))
    return True
