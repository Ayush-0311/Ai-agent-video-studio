"""Isolated, time-bounded online speech and word-boundary download."""
import argparse
import asyncio
import json
from pathlib import Path

import edge_tts


async def generate(args):
    words = []
    speaker = edge_tts.Communicate(Path(args.file).read_text('utf-8'), args.voice,
                                  rate=args.rate, pitch=args.pitch, boundary='WordBoundary')
    with open(args.write_media, 'wb') as audio:
        async for item in speaker.stream():
            if item['type'] == 'audio':
                audio.write(item['data'])
            elif item['type'] == 'WordBoundary':
                words.append({'text': item['text'], 'start': item['offset']/10_000_000,
                              'end': (item['offset']+item['duration'])/10_000_000})
    if not words:
        raise RuntimeError('The voice service returned no word timings.')
    Path(args.write_timings).write_text(json.dumps(words, ensure_ascii=False), encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for name in ('file', 'voice', 'rate', 'pitch', 'write-media', 'write-timings'):
        parser.add_argument('--'+name, required=True)
    asyncio.run(generate(parser.parse_args()))
