import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import speech_timing as timing
import studio


class SpeechTimingTests(unittest.TestCase):
    def test_known_text_alignment_preserves_spelling_without_punctuation_delay(self):
        words=timing.alignment_words('Deep roots. पानी।',[
            {'word':'Deep','start':.2,'end':.5}, {'word':' roots','start':.5,'end':1},
            {'word':'.','start':1,'end':1.5}, {'word':' पानी।','start':1.6,'end':2}],2.2)
        self.assertEqual([w['text'] for w in words],['Deep','roots.','पानी।'])
        self.assertEqual(words[1]['end'],1)
        self.assertEqual(words[2]['start'],1.6)

    def test_known_text_alignment_rejects_changed_text_and_zero_duration(self):
        for alignment in [[{'word':'Wrong','start':0,'end':1}],
                          [{'word':'Hello','start':1,'end':1}]]:
            with self.assertRaises(ValueError):timing.alignment_words('Hello',alignment,2)

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


class CaptionBoundaryTests(unittest.TestCase):
    def test_sentence_boundary_does_not_show_next_sentence_early(self):
        words=[{'text':'Ready.', 'start':2,'end':3},
               {'text':'Next', 'start':3.15,'end':3.5},
               {'text':'sentence.', 'start':3.5,'end':4}]
        self.assertEqual(list(timing.phrases(words)),[(2,3,'Ready.'),(3.15,4,'Next sentence.')])

    def test_measured_silence_refines_only_nearby_outer_edges(self):
        words=[{'text':'Hello','start':2.06,'end':2.64},
               {'text':'world.','start':5.5,'end':5.98}]
        refined=timing.refine_quiet_edges(words,[(0,2.2),(6.1,8)])
        self.assertAlmostEqual(refined[0]['start'],2.2)
        self.assertAlmostEqual(refined[-1]['end'],6.1)
        self.assertEqual(words[0]['start'],2.06)
        self.assertEqual(refined[0]['end'],words[0]['end'])
        self.assertEqual(timing.refine_quiet_edges(words,[(0,3),(7,8)]),words)
        self.assertEqual(timing.refine_quiet_edges(words,[]),words)
