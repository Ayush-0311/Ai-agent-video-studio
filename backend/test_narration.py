"""Neural selection + real local encoding, with only the online TTS boundary substituted."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import main
import studio
import narration
import speech_timing
from fastapi.testclient import TestClient


class NarrationTests(unittest.TestCase):
    def test_voice_language_gender_delivery_and_pace(self):
        cfg=studio.Settings(voice_profile='hi-swara',voice_delivery='calm',speech_rate=-18)
        hi=narration.resolve(cfg,'hi')
        self.assertEqual((hi['voice'],hi['rate'],hi['pitch']),('hi-IN-SwaraNeural',-20,-2))
        en=narration.resolve(cfg,'en')
        self.assertFalse(en['profile_matched'])
        self.assertEqual(en['voice'],'en-IN-PrabhatNeural')
        cfg=studio.Settings(voice_gender='female',voice_profile='auto',voice_delivery='energetic',speech_rate=19)
        self.assertEqual(narration.resolve(cfg,'en')['rate'],20)
        self.assertEqual(narration.resolve(cfg,'en')['voice'],'en-IN-NeerjaNeural')
        self.assertEqual(narration.resolve(cfg,'hi')['voice'],'hi-IN-SwaraNeural')
        for language in ('es','fr','de'):
            self.assertTrue(narration.resolve(cfg,language)['voice'].startswith(language+'-'))

    def test_cache_includes_all_voice_controls(self):
        cfg=studio.Settings(voice_engine='neural')
        key=json.dumps(narration.cache_identity(cfg,'hi'),sort_keys=True)
        for change in [{'voice_gender':'female'},{'voice_profile':'hi-swara'},{'voice_delivery':'calm'},
                       {'speech_rate':4},{'voice_normalize':False},{'voice_engine':'bridge'}]:
            other=cfg.model_copy(update=change)
            self.assertNotEqual(key,json.dumps(narration.cache_identity(other,'hi'),sort_keys=True))

    def test_bridge_cache_uses_actual_pace_not_ignored_delivery(self):
        cfg=studio.Settings(voice_engine='bridge',voice_delivery='energetic',speech_rate=19)
        self.assertNotEqual(narration.cache_identity(cfg,'hi'),narration.cache_identity(cfg.model_copy(update={'speech_rate':20}),'hi'))
        self.assertEqual(narration.cache_identity(cfg,'hi'),narration.cache_identity(cfg.model_copy(update={'voice_delivery':'calm','voice_profile':'hi-swara'}),'hi'))

    def test_voice_save_preserves_services_and_blocks_queued_renders(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(studio,'DATA',Path(folder)),patch.object(studio,'JOBS',{}):
            cfg=studio.Settings(ollama_url='https://planner.test',image_url='https://images.test',bridge_token='test-token',model='test-model')
            studio.write_json(Path(folder)/'settings.json',cfg.model_dump())
            client=TestClient(main.app)
            request=studio.VoiceSettings(voice_profile='hi-swara').model_dump()
            response=client.put('/api/studio/voice-settings',json=request)
            self.assertEqual(response.status_code,200,response.text)
            saved=studio.settings()
            self.assertEqual(saved.voice_profile,'hi-swara')
            self.assertEqual((saved.ollama_url,saved.image_url,saved.bridge_token),(cfg.ollama_url,cfg.image_url,cfg.bridge_token))
            studio.JOBS['test']={'status':'queued'}
            self.assertEqual(client.put('/api/studio/voice-settings',json=request).status_code,409)
            self.assertEqual(client.put('/api/studio/voice-settings',json={**request,'speech_rate':99}).status_code,422)

    def test_real_audio_normalization_and_atomic_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            folder=Path(folder);fixture=folder/'fixture.mp3';out=folder/'output.mp3'
            studio.run([main.FFMPEG_PATH,'-y','-v','error','-f','lavfi','-i',
                        'sine=frequency=220:duration=1','-af','volume=0.15',str(fixture)])
            actual_run=subprocess.run
            captured=[]
            def fake_tts(args,**kwargs):
                if not any(str(arg).endswith('narration_worker.py') for arg in args):
                    return actual_run(args,**kwargs)
                captured.append(args)
                self.assertIn('नमस्ते',Path(args[args.index('--file')+1]).read_text('utf-8'))
                Path(args[args.index('--write-media')+1]).write_bytes(fixture.read_bytes())
                Path(args[args.index('--write-timings')+1]).write_text(json.dumps([{'text':'नमस्ते।','start':.1,'end':.9}]),encoding='utf-8')
                return subprocess.CompletedProcess(args,0)
            cfg=studio.Settings(voice_profile='hi-swara',voice_delivery='calm')
            with patch.object(narration.subprocess,'run',side_effect=fake_tts):
                self.assertTrue(narration.synthesize('नमस्ते।', 'hi',out,cfg,main.FFMPEG_PATH,studio.run,studio.probe))
            self.assertIn('hi-IN-SwaraNeural',captured[0])
            self.assertIn('--rate=-10%',captured[0]);self.assertIn('--pitch=-2Hz',captured[0])
            info=studio.probe(out)
            self.assertEqual(info['streams'][0]['sample_rate'],'48000')
            self.assertAlmostEqual(float(info['format']['duration']),1,delta=.15)
            self.assertEqual(len(speech_timing.load(out, 'नमस्ते।')), 1)
            original=out.read_bytes()
            with patch.object(narration.subprocess,'run',return_value=subprocess.CompletedProcess([],1)):
                with self.assertRaisesRegex(RuntimeError,'No basic-voice fallback'):
                    narration.synthesize('Hello','en',out,cfg,main.FFMPEG_PATH,studio.run,studio.probe)
            self.assertEqual(out.read_bytes(),original)
            self.assertEqual(list(folder.glob('narration-*')),[])

    def test_direct_neural_never_calls_colab(self):
        cfg=studio.Settings(voice_engine='neural',image_url='https://offline.test')
        with patch.object(studio,'settings',return_value=cfg), patch.object(narration,'synthesize',return_value=True) as synth, \
                patch.object(studio.requests,'post',side_effect=AssertionError('Must not contact Colab')):
            self.assertTrue(studio.voice_asset('नमस्ते','hi',Path('unused.mp3')))
            self.assertEqual(synth.call_args.args[3],cfg)


if __name__=='__main__':
    unittest.main()
