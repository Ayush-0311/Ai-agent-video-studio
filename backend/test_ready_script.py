"""Ready-script parsing and original local audio; no external providers."""
from pathlib import Path
import tempfile
import unittest
import wave

import instrumental
import ready_script

SAMPLE = (Path(__file__).resolve().parents[1]/'tests/fixtures/motivational-ready-script.txt').read_text('utf-8')


class ReadyScriptTests(unittest.TestCase):
    def test_supplied_eight_scene_script_preserves_fields(self):
        rows = ready_script.parse(SAMPLE)
        self.assertEqual([r['end']-r['start'] for r in rows], [5,5,5,10,10,10,10,5])
        self.assertEqual(rows[0]['text'], 'ज़िंदगी हमेशा आसान नहीं होती।')
        self.assertEqual(rows[-1]['overlay_text'], 'YOUR STORY IS NOT OVER.')
        self.assertTrue(rows[-1]['fade_out'])
        self.assertNotIn('Use realistic', rows[-1]['text']+rows[-1]['overlay_text'])
        self.assertTrue(ready_script.detected(SAMPLE))

    def test_quote_labels_are_spoken_words(self):
        rows = ready_script.parse('0–10 sec: Visual: A sign. Voiceover: “Read Text: KEEP GOING.” Text: “Voiceover: a label”')
        self.assertEqual(rows[0]['text'],'Read Text: KEEP GOING.')
        self.assertEqual(rows[0]['overlay_text'],'Voiceover: a label')

    def test_other_durations_and_clock_notation(self):
        for duration in (10,40,65,120,180):
            rows=ready_script.parse(f'0–{duration} sec: Visual: Sunrise. Voiceover: “Keep going.”')
            self.assertEqual(rows[-1]['end'],duration)
        rows=ready_script.parse('[0:00–0:30]: Visual: Night. Voiceover: none\n[0:30–1:05]: Visual: Dawn. Text: “DAWN”')
        self.assertEqual(rows[-1]['end'],65)
        self.assertEqual(rows[0]['text'],'')

    def test_invalid_timestamps_and_ambiguous_fields_fail(self):
        for text in (
            '1–10 sec: A man.', '0–5 sec: A man.\n6–10 sec: A man.',
            '0–6 sec: A man.\n5–10 sec: A man.', '0–181 sec: A man.',
            '0–1:65 sec: A man.', '0–5.01 sec: A man.\n5.01–10 sec: A man.',
            '0–10 sec: Voiceover: “Hello”', '0–10 sec: A man. Text: “A” Text: “B”',
            '0–10 sec: A man. Voiceover: “Unclosed',
        ):
            with self.subTest(text=text), self.assertRaises(ValueError):
                ready_script.parse(text)

    def test_instrumental_is_stereo_audible_and_exact_length(self):
        import numpy as np
        with tempfile.TemporaryDirectory() as folder:
            for mood in ('cinematic','calm','uplifting'):
                path=Path(folder)/f'{mood}.wav'
                instrumental.create(path,4.25,mood)
                with wave.open(str(path)) as audio:
                    self.assertEqual(audio.getnframes(),102000)
                    self.assertEqual(audio.getnchannels(),2)
                    samples=np.frombuffer(audio.readframes(audio.getnframes()),dtype='<i2')
                self.assertGreater(float(np.std(samples)),100)
                self.assertLess(int(np.max(np.abs(samples))),32767)
                self.assertLess(float(np.std(samples[-1000:])),float(np.std(samples[48000:96000])))
