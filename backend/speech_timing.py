"""Speech timestamps shared by narration, captions and editable scene clips."""
import hashlib
import json
import math
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
        if group and (len(group) >= 7 or word['start']-group[-1]['end'] > .45 or
                      word['end']-group[0]['start'] > 3):
            yield group[0]['start'], group[-1]['end'], ' '.join(w['text'] for w in group)
            group = []
        group.append(word)
    if group:
        yield group[0]['start'], group[-1]['end'], ' '.join(w['text'] for w in group)
