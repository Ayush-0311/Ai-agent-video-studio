"""Deterministic timed-script parsing. Dialogue and overlays never go through a writer."""
import re

TIME = r'(?:\d{1,2}:)?\d{1,3}(?:\.\d+)?'
HEADER = re.compile(r'(?m)^\s*(?:\*\*)?\[?\s*(' + TIME +
    r')\s*(?:sec(?:onds?)?|s)?\s*(?:[-–—]|to)\s*(' + TIME +
    r')\s*(?:sec(?:onds?)?|s)?\s*\]?\s*(?:\*\*)?\s*:\s*(?:\*\*)?', re.I)
LABEL = re.compile(r'(?:\*\*)?\b(voiceover|voice over|narration|text|on.screen text|visual|visuals|image|video)\s*(?:\*\*)?\s*:\s*(?:\*\*)?', re.I)


def seconds(value):
    parts = value.split(':')
    if len(parts)==2 and float(parts[1])>=60:
        raise ValueError('Clock timestamps must use seconds below 60, for example 1:05.')
    return float(parts[0])*60 + float(parts[1]) if len(parts)==2 else float(value)


def field(value):
    value = value.strip().strip('*').strip()
    pairs = {'“':'”', '"':'"', '‘':'’'}
    if value[:1] in pairs:
        end = value.find(pairs[value[0]],1)
        if end < 0:
            raise ValueError('Close the quotation marks around Voiceover or Text.')
        return value[1:end].strip()
    return value.strip()


def detected(text):
    return bool(HEADER.search(text))


def labels_outside_quotes(body):
    """A spoken phrase such as 'Text: ...' is content, not a field separator."""
    quoted, closing = set(), None
    for index, char in enumerate(body):
        if closing:
            quoted.add(index)
            if char == closing and (index == 0 or body[index-1] != '\\'):
                closing = None
        elif char in ('"', '“', '‘'):
            closing = {'"':'"', '“':'”', '‘':'’'}[char]
            quoted.add(index)
    if closing:
        raise ValueError('Close the quotation marks around Voiceover or Text.')
    return [m for m in LABEL.finditer(body) if m.start() not in quoted]


def parse(text):
    markers = list(HEADER.finditer(text))
    if not 1 <= len(markers) <= 30:
        raise ValueError('Ready script needs 1–30 scenes headed like 0–5 sec: with Visual, Voiceover and Text fields.')
    rows, cursor = [], 0
    for i, match in enumerate(markers):
        start,end = seconds(match[1]),seconds(match[2])
        if abs(start-cursor) > .001 or end <= start or end-start < .1:
            raise ValueError(f'Scene {i+1}: timestamps must start at 0 and continue without gaps or overlaps.')
        if any(abs(t*30-round(t*30))>.001 for t in (start,end)):
            raise ValueError(f'Scene {i+1}: use timestamps aligned to 1/30 second.')
        body = text[match.end():markers[i+1].start() if i+1<len(markers) else len(text)]
        labels = labels_outside_quotes(body)
        values = {'visual':body[:labels[0].start()].strip() if labels else body.strip(),
                  'voiceover':'', 'text':''}
        seen = set()
        for j,label in enumerate(labels):
            name = label[1].lower()
            key = 'voiceover' if name in ('voiceover','voice over','narration') else 'text' if name in ('text','on-screen text','on screen text') else 'visual'
            if key in seen:
                raise ValueError(f'Scene {i+1}: use one {key} field per scene.')
            seen.add(key)
            values[key] = field(body[label.end():labels[j+1].start() if j+1<len(labels) else len(body)])
        visual = values['visual'].strip()
        if not visual:
            raise ValueError(f'Scene {i+1}: add a visual description.')
        voice = values['voiceover']
        if voice.lower() in ('none','silent','no narration','no voiceover','—','-'):
            voice = ''
        if len(voice)>5000 or len(visual)>4000 or len(values['text'])>300:
            raise ValueError(f'Scene {i+1}: narration, visual description or screen text is too long.')
        rows.append({'start':start,'end':end,'text':voice,'visual_prompt':visual,
                     'overlay_text':values['text'], 'fade_out':bool(re.search(r'fade\s+to\s+black',visual,re.I))})
        cursor=end
    if not 10 <= cursor <= 180 or cursor != round(cursor):
        raise ValueError('Ready-script timeline must end at a whole second between 10 and 180 seconds.')
    return rows
