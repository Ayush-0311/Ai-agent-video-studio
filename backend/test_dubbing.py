"""Dubbing integration: real media encoding, substituted external translation/TTS."""
import json
from pathlib import Path
import tempfile
import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import patch, Mock
import main
import studio
import dubbing
from fastapi.testclient import TestClient


class DubbingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='dub-tests-')
        cls.root=Path(cls.temp.name)
        cls.old=studio.DATA
        studio.DATA=cls.root
        (cls.root/'assets').mkdir()
        cls.ident=uuid.uuid4().hex
        cls.source=studio.path_for('assets',cls.ident,'.mp4')
        studio.run([main.FFMPEG_PATH,'-y','-v','error','-f','lavfi','-i','color=blue:s=320x180:r=30',
            '-f','lavfi','-i','sine=frequency=440:sample_rate=48000','-t','3','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac',str(cls.source)])
        studio.write_json(studio.path_for('assets',cls.ident),{'id':cls.ident,'name':'English source','extension':'.mp4','kind':'video','has_audio':True,'duration':3})
    @classmethod
    def tearDownClass(cls):
        studio.DATA=cls.old
        cls.temp.cleanup()
    def setUp(self):
        configured=patch.object(studio,'settings',return_value=studio.Settings(image_url='https://bridge.test'))
        configured.start();self.addCleanup(configured.stop)
        ready=Mock();ready.json.return_value={'voice_ready':True}
        health=patch.object(studio.requests,'get',return_value=ready)
        health.start();self.addCleanup(health.stop)
        # TTS fixtures are tones; alignment fixtures represent known speech times.
        alignment=patch.object(studio.speech_timing,'align_narration',side_effect=lambda path,text,*args:
            [{'text':text,'start':0,'end':float(studio.probe(path)['format']['duration'])}])
        alignment.start();self.addCleanup(alignment.stop)
    def request(self,captions=True):
        p=studio.Project(language='en',narration=False,resolution='720p',scenes=[studio.Scene(asset_id=self.ident,media_kind='video',end=3)])
        return studio.DubRequest(project=p,scene_id=p.scenes[0].id,target_language='hi',captions=captions)
    def job(self,request):
        jid=uuid.uuid4().hex
        studio.JOBS[jid]={'id':jid,'project_id':request.project.id,'kind':'dub','status':'running','progress':0,'events':[]}
        return jid
    def translate(self,system,message,**kwargs):
        data=json.loads(message)
        return {'segments':[{'id':s['id'],'text':'नमस्ते दुनिया।' if s['text'].startswith('Hello') else 'यह एक उदाहरण है।'} for s in data['segments']]}
    def voice(self,text,language,path,cfg):
        self.assertEqual(language,'hi')
        studio.run([main.FFMPEG_PATH,'-y','-v','error','-f','lavfi','-i','sine=frequency=880:duration=0.5:sample_rate=48000',str(path)])
        return True
    def whisper(self):
        return SimpleNamespace(transcribe=lambda *a,**k:([SimpleNamespace(start=.3,end=1,text='Hello world.'),SimpleNamespace(start=2,end=2.7,text='This is an example.')],None))
    def test_replaces_original_audio_preserves_duration_and_hindi_captions(self):
        req=self.request();jid=self.job(req)
        with patch.dict(studio.ENV,{'get_whisper_model':self.whisper}),patch.object(studio,'chat',side_effect=self.translate),patch.object(studio,'voice_asset',side_effect=self.voice):
            result=dubbing.dub(jid,req,studio)
        self.assertAlmostEqual(result['duration'],3,delta=.05)
        self.assertEqual(result['project']['language'],'hi')
        self.assertFalse(result['project']['narration'])
        self.assertTrue(self.source.exists())
        studio.JOBS[jid].update(status='completed',result=result)
        studio.write_json(studio.path_for('jobs',jid),studio.JOBS[jid])
        client=TestClient(main.app)
        for kind in ('video','subtitles','metadata'):
            response=client.get(f'/api/studio/jobs/{jid}/file/{kind}')
            self.assertEqual(response.status_code,200,response.text[:100] if kind!='video' else 'Video blocked')
        response=client.get(f'/api/studio/jobs/{jid}/file/video',headers={'Range':'bytes=0-127'})
        self.assertEqual(response.status_code,206)
        self.assertEqual(len(response.content),128)
        self.assertTrue(any(row['id']==jid for row in studio.saved_records('jobs')))
        srt=(self.root/'renders'/jid/'captions.srt').read_text('utf-8')
        self.assertIn('नमस्ते दुनिया।',srt);self.assertNotIn('Hello',srt)
        self.assertIn('00:00:00,300',srt);self.assertIn('00:00:02,000',srt)
        # Actual output must contain the replacement frequency, not original speech.
        import numpy as np
        raw=studio.run([main.FFMPEG_PATH,'-v','error','-ss','0.4','-t','0.2','-i',str(self.root/'renders'/jid/'final.mp4'),'-ac','1','-ar','8000','-f','f32le','-'])
        samples=np.frombuffer(raw,dtype=np.float32)
        spectrum=np.abs(np.fft.rfft(samples))
        freq=np.fft.rfftfreq(len(samples),1/8000)
        self.assertAlmostEqual(freq[spectrum.argmax()],880,delta=15)
        self.assertGreater(spectrum[(abs(freq-880)).argmin()],spectrum[(abs(freq-440)).argmin()]*10)
    def test_caption_toggle_and_saved_job(self):
        req=self.request(False);jid=self.job(req)
        with patch.dict(studio.ENV,{'get_whisper_model':self.whisper}),patch.object(studio,'chat',side_effect=self.translate),patch.object(studio,'voice_asset',side_effect=self.voice):
            result=dubbing.dub(jid,req,studio)
        self.assertEqual((self.root/'renders'/jid/'captions.srt').read_text('utf-8'),'')
        self.assertFalse(result['project']['captions'])
        studio.SavedJob.model_validate(studio.JOBS[jid])
    def test_overlong_speech_stops_without_truncation(self):
        req=self.request();jid=self.job(req)
        def long_voice(text,language,path,cfg):
            studio.run([main.FFMPEG_PATH,'-y','-v','error','-f','lavfi','-i','sine=frequency=880:duration=5',str(path)])
            return True
        with patch.dict(studio.ENV,{'get_whisper_model':self.whisper}),patch.object(studio,'chat',side_effect=self.translate),patch.object(studio,'voice_asset',side_effect=long_voice),patch.object(studio,'render') as render:
            with self.assertRaisesRegex(ValueError,'avoid cutting speech'):
                dubbing.dub(jid,req,studio)
            render.assert_not_called()
    def test_translation_rejects_missing_duplicate_and_empty_rows(self):
        parts=[{'id':'a','text':'Hello'},{'id':'b','text':'World'}]
        for reply in [{'segments':[]},{'segments':[{'id':'a','text':'x'},{'id':'a','text':'y'}]}, {'segments':[{'id':'a','text':''},{'id':'b','text':'y'}]}]:
            with self.assertRaises(ValueError):
                dubbing.translate(parts,'en','hi',lambda *args,**kwargs:reply)
    def test_endpoint_checks_language_and_queues_dub(self):
        client=TestClient(main.app);req=self.request()
        with patch.object(studio,'queue',return_value={'id':'test'}) as queue:
            response=client.post('/api/studio/dub',json=req.model_dump())
            self.assertEqual(response.status_code,200)
            self.assertEqual(queue.call_args.args[0],'dub')
            payload=req.model_dump();payload['target_language']='en'
            self.assertEqual(client.post('/api/studio/dub',json=payload).status_code,400)
            payload['target_language']='invalid'
            self.assertEqual(client.post('/api/studio/dub',json=payload).status_code,422)

    def test_offline_voice_stops_before_transcription(self):
        req=self.request();jid=self.job(req)
        with patch.object(studio.requests,'get',side_effect=studio.requests.ConnectionError()),patch.object(studio,'transcribe') as transcribe:
            with self.assertRaisesRegex(ValueError,'reconnect'):
                dubbing.dub(jid,req,studio)
            transcribe.assert_not_called()
        with patch.object(studio.requests,'get',return_value=Mock(json=lambda:{'voice_ready':False})):
            with self.assertRaisesRegex(ValueError,'not ready'):
                dubbing.dub(jid,req,studio)

    def test_cancellation_does_not_start_external_services(self):
        req=self.request();jid=self.job(req)
        studio.JOBS[jid]['cancel_requested']=True
        with patch.object(studio.requests,'get') as health:
            with self.assertRaisesRegex(RuntimeError,'Cancelled'):
                dubbing.dub(jid,req,studio)
            health.assert_not_called()

    def test_overlong_translation_is_retried_once_and_successfully_fits(self):
        req=self.request();jid=self.job(req);count=0
        def voice(text,language,path,cfg):
            nonlocal count
            count+=1
            seconds=3 if count==1 else .5
            studio.run([main.FFMPEG_PATH,'-y','-v','error','-f','lavfi','-i',f'sine=frequency=880:duration={seconds}',str(path)])
            return True
        with patch.dict(studio.ENV,{'get_whisper_model':self.whisper}),patch.object(studio,'chat',side_effect=self.translate) as chat,patch.object(studio,'voice_asset',side_effect=voice):
            result=dubbing.dub(jid,req,studio)
        self.assertEqual(count,3)
        self.assertEqual(chat.call_count,5)
        self.assertIn('max_words',json.loads(chat.call_args.args[1])['segments'][0])
        self.assertAlmostEqual(result['duration'],3,delta=.05)

    def test_caption_slot_uses_next_word_start_not_earlier_segment_start(self):
        req=self.request();jid=self.job(req)
        model=SimpleNamespace(transcribe=lambda *a,**k:([
            SimpleNamespace(start=.2,end=1,text='Hello.',words=[SimpleNamespace(word='Hello.',start=.3,end=1)]),
            SimpleNamespace(start=2,end=2.8,text='Next.',words=[SimpleNamespace(word='Next.',start=2.2,end=2.8)])],None))
        count=0
        def voice(text,language,path,cfg):
            nonlocal count
            count+=1
            seconds=1.8 if count==1 else .5
            studio.run([main.FFMPEG_PATH,'-y','-v','error','-f','lavfi','-i',f'sine=frequency=880:duration={seconds}',str(path)])
            return True
        with patch.dict(studio.ENV,{'get_whisper_model':lambda:model}),patch.object(studio,'chat',side_effect=self.translate),patch.object(studio,'voice_asset',side_effect=voice):
            result=dubbing.dub(jid,req,studio)
        first,second=result['project']['scenes']
        self.assertAlmostEqual(first['end'],2.2)
        self.assertAlmostEqual(second['start'],2.2)
        self.assertGreater(result['timeline'][0]['words'][-1]['end'],2)
        self.assertLessEqual(result['timeline'][0]['words'][-1]['end'],2.2)

    def test_malformed_translation_id_has_actionable_error(self):
        with self.assertRaisesRegex(ValueError,'mismatched'):
            dubbing.translate([{'id':'a','text':'Hello'}],'en','hi',lambda *a,**k:{'segments':[{'id':[],'text':'x'}]})

    def test_roman_hindi_is_rejected_before_voice_generation(self):
        with self.assertRaisesRegex(ValueError,'Devanagari'):
            dubbing.translate([{'id':'a','text':'Hello'}],'en','hi',lambda *a,**k:{'segments':[{'id':'0','text':'Namaste duniya'}]})

    def test_translation_uses_reasoning_and_original_source(self):
        source = 'Keep waste out of the water.'
        corrected = 'कचरे को पानी से बाहर रखें।'
        draft = 'पानी में कचरा रखें।'
        chat = Mock(side_effect=[{'segments':[{'id':'0','text':draft}]},
                                 {'segments':[{'id':'0','text':corrected}]}])
        result = dubbing.translate([{'id':'a','text':source}],'en','hi',chat)
        self.assertEqual(json.loads(chat.call_args.args[1])['segments'][0]['text'],source)
        self.assertTrue(chat.call_args.kwargs['think'])
        self.assertEqual(json.loads(chat.call_args.args[1])['segments'][0]['draft_translation'],draft)
        self.assertEqual(result['a'],corrected)

    def test_invalid_json_retries_original_request_once(self):
        reply={'segments':[{'id':'0','text':'नमस्ते दुनिया।'}]}
        chat=Mock(side_effect=[ValueError('incomplete JSON'),reply,reply])
        result=dubbing.translate([{'id':'original-scene-id','text':'Hello world.'}],'en','hi',chat)
        self.assertEqual(result,{'original-scene-id':'नमस्ते दुनिया।'})
        self.assertEqual(chat.call_args_list[0].args[1],chat.call_args_list[1].args[1])
        self.assertIn('previous response was incomplete',chat.call_args_list[1].args[0])
        self.assertTrue(chat.call_args_list[1].kwargs['think'])
        self.assertEqual(chat.call_args.kwargs['response_schema']['properties']['segments']['maxItems'],1)

    def test_invalid_json_retry_is_bounded(self):
        chat=Mock(side_effect=ValueError('incomplete JSON'))
        with self.assertRaisesRegex(ValueError,'invalid JSON twice'):
            dubbing.translate([{'id':'a','text':'Hello'}],'en','hi',chat)
        self.assertEqual(chat.call_count,2)

    def test_word_alignment_uses_source_offset_and_preserves_pause(self):
        req=self.request();jid=self.job(req)
        words=[{'text':'नमस्ते','start':.05,'end':.15},{'text':'दुनिया।','start':.35,'end':.45}]
        with patch.dict(studio.ENV,{'get_whisper_model':self.whisper}),patch.object(studio,'chat',side_effect=self.translate),patch.object(studio,'voice_asset',side_effect=self.voice),patch.object(studio.speech_timing,'align_narration',return_value=words):
            result=dubbing.dub(jid,req,studio)
        cue=result['project']['scenes'][0]['caption_words']
        self.assertAlmostEqual(cue[0]['start'],.35)
        self.assertAlmostEqual(cue[1]['start'],.65)
        self.assertLess(cue[0]['end'],cue[1]['start'])
        report=result['project']['production_notes']['dubbing']
        self.assertIn('alignment',report['caption_timing'])
        self.assertTrue(all(s['audio_end']<=s['slot_end'] for s in report['segments']))

