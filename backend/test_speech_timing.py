import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import speech_timing as timing
import studio


class SpeechTimingTests(unittest.TestCase):
    def test_trim_speed_and_scene_offset_do_not_retime_words_into_silence(self):
        words = [{'text':'Hello', 'start':.2, 'end':.6},
                 {'text':'world.', 'start':.7, 'end':1.1},
                 {'text':'Again', 'start':2.0, 'end':2.5}]
        trimmed = timing.transform(words, .5, 2.2, 2)
        self.assertAlmostEqual(trimmed[0]['start'], 0)
        self.assertAlmostEqual(trimmed[-1]['end'], .85)
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            studio.caption_files(folder, [{'text':'Hello world. Again', 'start':10, 'end':20,
                                          'words':trimmed}], 1280, 720, '')
            srt = (folder/'captions.srt').read_text('utf-8')
            self.assertIn('00:00:10,000', srt)
            self.assertIn('00:00:10,850', srt)
            self.assertNotIn('00:00:20,000', srt)

    def test_long_pause_is_not_covered_by_a_caption(self):
        words = [{'text':'First.', 'start':.15, 'end':1},
                 {'text':'Next.', 'start':3, 'end':4}]
        self.assertEqual(list(timing.phrases(words)),[(.15, 1, 'First.'), (3, 4, 'Next.')])

    def test_disabled_captions_ignore_timestamped_words(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            studio.caption_files(folder,[{'text':'','start':0,'end':5,
                'words':[{'text':'Hidden','start':1,'end':2}]}],1280,720,'Brand')
            self.assertEqual((folder/'captions.srt').read_text('utf-8'),'')
            self.assertNotIn('Hidden',(folder/'captions.ass').read_text('utf-8-sig'))

    def test_cache_rejects_changed_audio_text_and_invalid_timestamps(self):
        with tempfile.TemporaryDirectory() as folder:
            audio = Path(folder)/'test.mp3'; audio.write_bytes(b'audio')
            words = [{'text':'नमस्ते', 'start':.1, 'end':.9}]
            data = {'text':'नमस्ते', 'words':words, 'duration':1,
                    'audio_sha256':hashlib.sha256(audio.read_bytes()).hexdigest()}
            timing.sidecar(audio).write_text(json.dumps(data),encoding='utf-8')
            self.assertEqual(timing.load(audio, 'नमस्ते'), words)
            self.assertEqual(timing.load(audio, 'Different script'), [])
            audio.write_bytes(b'replaced')
            self.assertEqual(timing.load(audio, 'नमस्ते'), [])
        for end in (float('nan'), float('inf'), -.1, 2):
            self.assertFalse(timing.valid_words([{'text':'Invalid','start':0,'end':end}],1))

    def test_hindi_phrases_preserve_unicode(self):
        words = [{'text':w,'start':i*.3,'end':i*.3+.25} for i,w in enumerate('यह एक सरल उदाहरण है।'.split())]
        self.assertEqual(list(timing.phrases(words))[0][2], 'यह एक सरल उदाहरण है।')
