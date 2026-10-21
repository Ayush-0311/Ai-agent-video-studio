"""Independent speech recognition for a completed live dubbing test."""
import json
import sys
import difflib
import statistics
import unicodedata
from pathlib import Path
from faster_whisper import WhisperModel

root=Path(__file__).resolve().parents[1]
folder=root/'backend/studio-data/verification/dubbing-live-2026-10-18/fixed'
model=WhisperModel('small',device='cpu',compute_type='int8',cpu_threads=4,
                   download_root=str(root/'backend/studio-data/models/whisper-quality'),
                   local_files_only='--prepare-only' not in sys.argv)
if '--prepare-only' in sys.argv:
    print('Independent small speech model ready')
    sys.exit(0)
prior='--existing-audio' in sys.argv
ui=json.loads((folder/'ui-result.json').read_text('utf-8')) if not prior else {'passed':True,'job':None}
assert ui.get('passed'), 'Latest UI run has not finished'
segments,_=model.transcribe(str(folder/'hindi-dub-ui.mp4'),language='hi',beam_size=5,
                            condition_on_previous_text=False,word_timestamps=True)
result={'job':ui['job'],'model':'small','segments':[{'start':s.start,'end':s.end,'text':s.text,
    'words':[{'text':w.word.strip(),'start':w.start,'end':w.end} for w in (s.words or [])]} for s in segments]}
if not prior:
    job=json.loads((folder/'ui-job.json').read_text('utf-8'))
    assert ui['job']==job['id']
    expected=[w for s in job['result']['project']['scenes'] for w in s['caption_words']]
    heard=[w for s in result['segments'] for w in s['words']]
    def normalized(text):
        return ''.join(c for c in unicodedata.normalize('NFKC',text) if unicodedata.category(c)[0] in 'LMN')
    matcher=difflib.SequenceMatcher(a=[normalized(w['text']) for w in expected],
                                  b=[normalized(w['text']) for w in heard],autojunk=False)
    offsets=[abs(expected[a+i]['start']-heard[b+i]['start'])
             for a,b,count in matcher.get_matching_blocks() for i in range(count)]
    result['caption_comparison']={'matched_words':len(offsets),'caption_words':len(expected),
        'median_absolute_start_difference':statistics.median(offsets) if offsets else None,
        'p90_absolute_start_difference':sorted(offsets)[int(.9*(len(offsets)-1))] if offsets else None,
        'note':'Independent ASR estimates, not a phonetic ground truth or pronunciation score.'}
(folder/('prior-speech-review.json' if prior else 'independent-speech-review.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
sys.stdout.reconfigure(encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))
