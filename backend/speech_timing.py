"""Speech timestamps shared by narration, captions and editable scene clips."""
import hashlib
import json
import math
import re
import subprocess
from pathlib import Path
import unicodedata


def text_key(text):
    return ' '.join(unicodedata.normalize('NFC', text).split())


def valid_words(words, duration):
    if not isinstance(words, list) or not words:
        return False
    previous = 0.0
    try:
        for word in words:
            start, end = float(word['start']), float(word['end'])
            if not (math.isfinite(start) and math.isfinite(end) and
                    previous <= start < end <= duration + .1 and str(word['text']).strip()):
                return False
            previous = start
    except (KeyError, TypeError, ValueError):
        return False
    return True


def sidecar(path):
    return Path(path).with_suffix('.words.json')


def alignment_words(text, alignment, duration):
    """Map token alignment back to the supplied words, keeping spelling and punctuation."""
    expected = text_key(text).split()
    compact = lambda value: ''.join(value.split())
    if compact(''.join(w['word'] for w in alignment)) != compact(text_key(text)):
        raise ValueError('Speech alignment changed the supplied text.')
    spans, cursor = [], 0
    for item in alignment:
        size = len(compact(item['word']))
        if size:
            spans.append((cursor, cursor+size, item))
        cursor += size
    mapped, cursor = [], 0
    for word in expected:
        end = cursor + len(word)
        matched = [item for a,b,item in spans if b > cursor and a < end and
                   any(unicodedata.category(c)[0] in ('L','N') for c in item['word'])]
        if not matched:
            raise ValueError('Speech alignment has no timing for a word.')
        raw_start, raw_end = float(matched[0]['start']), float(matched[-1]['end'])
        mapped.append([word, raw_start, raw_end])
        cursor = end
    words = []
    for index, (word, raw_start, raw_end) in enumerate(mapped):
        start, end = max(0, raw_start), min(duration, raw_end)
        if raw_end == raw_start and math.isfinite(raw_start) and 0 <= raw_start <= duration:
            # Whisper can quantize an internal Hindi word to one instant. Give
            # that word a tiny span around its boundary, bounded by its valid
            # neighbors; do not invent timing for missing edge words.
            if (index == 0 or index == len(mapped)-1
                    or mapped[index-1][2] <= mapped[index-1][1]
                    or mapped[index+1][2] <= mapped[index+1][1]):
                raise ValueError('Speech alignment returned invalid word boundaries.')
            pad = min(.08, duration/2)
            start = max(mapped[index-1][1], raw_start-pad, 0)
            end = min(mapped[index+1][2], raw_end+pad, duration)
        words.append({'text':word,'start':start,'end':end})
    if not valid_words(words,duration):
        raise ValueError('Speech alignment returned invalid word boundaries.')
    return words


def align_narration(path, text, language, model, ffmpeg):
    """Align known short narration to audio; never replace it with ASR guesses."""
    from faster_whisper.audio import decode_audio, pad_or_trim
    from faster_whisper.tokenizer import Tokenizer
    audio = decode_audio(str(path), sampling_rate=16000)
    duration = len(audio)/16000
    if not 0 < duration <= 30:
        raise ValueError('Automatic narration alignment supports up to 30 seconds per scene. Split the scene or disable captions.')
    features = model.feature_extractor(audio)
    tokenizer = Tokenizer(model.hf_tokenizer, model.model.is_multilingual, task='transcribe', language=language)
    alignment = model.find_alignment(tokenizer,[tokenizer.encode(text_key(text))],
        model.encode(pad_or_trim(features)),min(features.shape[-1],3000))[0]
    words = alignment_words(text,alignment,duration)
    intervals = quiet_intervals(ffmpeg,path)
    words = refine_quiet_edges(words,intervals)
    # Do not display edge words over measured leading/trailing silence.
    for word in words:
        for start,end in intervals:
            if start <= word['start'] < end < word['end']:
                word['start'] = end
            if word['start'] < start < word['end'] <= end:
                word['end'] = start
    if not valid_words(words,duration):
        raise ValueError('Speech alignment overlaps silence; review the narration.')
    data = {'text':text_key(text),'words':words,'duration':duration,
            'audio_sha256':hashlib.sha256(Path(path).read_bytes()).hexdigest(),
            'method':'whisper_known_text_alignment'}
    target = sidecar(path)
    temp = target.with_suffix('.tmp')
    temp.write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
    temp.replace(target)
    return words


def load(path, text):
    try:
        data = json.loads(sidecar(path).read_text('utf-8'))
        if (data['text'] == text_key(text) and
                data['audio_sha256'] == hashlib.sha256(Path(path).read_bytes()).hexdigest() and
                valid_words(data['words'], data['duration'])):
            return data['words']
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return []


def transform(words, start, end, speed=1):
    """Clip source-relative speech to a trim and transform to clip-relative time."""
    return [{'text': w['text'], 'start': max(0, (w['start']-start)/speed),
             'end': min((end-start)/speed, (w['end']-start)/speed)}
            for w in words if w['end'] > start and w['start'] < end]


def phrases(words):
    group = []
    for word in words:
        if group and (re.search(r'[.!?।][\"\”\’]*$', group[-1]['text']) or len(group) >= 7 or word['start']-group[-1]['end'] > .45 or
                      word['end']-group[0]['start'] > 3):
            yield group[0]['start'], group[-1]['end'], ' '.join(w['text'] for w in group)
            group = []
        group.append(word)
    if group:
        yield group[0]['start'], group[-1]['end'], ' '.join(w['text'] for w in group)


def quiet_intervals(ffmpeg, path):
    """Detect only near-silence; this is not speech detection in music/noise."""
    result = subprocess.run([str(ffmpeg), '-hide_banner', '-nostats', '-i', str(path),
        '-vn', '-af', 'silencedetect=noise=-50dB:d=0.1', '-f', 'null', '-'],
        capture_output=True, timeout=180)
    if result.returncode:
        raise RuntimeError('Could not check caption audio boundaries: '+result.stderr.decode(errors='replace')[-1000:])
    intervals, start = [], None
    for kind, value in re.findall(r'silence_(start|end): ([0-9.]+)', result.stderr.decode(errors='replace')):
        if kind == 'start':
            start = float(value)
        elif start is not None:
            intervals.append((start, float(value)))
            start = None
    return intervals


def refine_quiet_edges(words, intervals):
    """Bounded edge refinement, not a global time shift or forced alignment.

    Only move a leading word out of measured silence or extend the final word
    to a nearby trailing silence. Never move interior words or cross a word.
    """
    result = [dict(w) for w in words]
    if not result:
        return result
    first, last = result[0], result[-1]
    for start, end in intervals:
        if start <= first['start'] < end and 0 < end-first['start'] <= .3 and end < first['end']:
            first['start'] = end
        if 0 < start-last['end'] <= .2 and end-start >= .1:
            last['end'] = start
    return result
