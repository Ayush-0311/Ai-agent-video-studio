"""Deterministic integration tests: real FFmpeg, fake external AI only."""
import json
import base64
from pathlib import Path
import tempfile
import unittest
import uuid
from unittest.mock import patch, Mock

from fastapi.testclient import TestClient
import main
import studio

ANALYZE_VIDEO_BRIEF = studio.video_brief.analyze


class StudioTests(unittest.TestCase):
    def test_health_distinguishes_model_presence_from_planner_inference(self):
        cfg=studio.Settings(ollama_url='https://planner.invalid',model='qwen3.5:9b',
                            image_url='https://bridge.invalid',bridge_token='private-token')
        tags=Mock(status_code=200); tags.json.return_value={'models':[{'name':'qwen3.5:9b'}]}
        bridge=Mock(status_code=200); bridge.json.return_value={
            'image_ready':True,'voice_ready':True,'edit_planner_ready':False,
            'planner_error':'Ollama runner terminated.', 'video_available':True}
        recovery=Mock(status_code=503,text='')
        recovery.json.return_value={'detail':'runner still unavailable; Bearer private-token at https://bridge.invalid/api/chat'}
        with patch.object(studio,'settings',return_value=cfg), patch.object(studio,'headers',return_value={}), \
             patch.object(studio.requests,'get',side_effect=[tags,bridge]), \
             patch.object(studio.requests,'post',return_value=recovery):
            response=TestClient(main.app).get('/api/studio/health')
        self.assertEqual(response.status_code,200)
        health=response.json()
        self.assertTrue(health['ollama'],'The installed model should remain separately visible')
        self.assertFalse(health['planner_ready'],'A model in /api/tags is not proof inference works')
        self.assertEqual(health['services']['language_model']['status'],'inference_failed')
        self.assertIn('runner still unavailable',health['planner_error'])
        self.assertNotIn('private-token',health['planner_error'])
        self.assertNotIn('bridge.invalid',health['planner_error'])

    def test_health_recovers_planner_with_a_real_bridge_probe(self):
        cfg=studio.Settings(ollama_url='https://planner.invalid',model='qwen3.5:9b',
                            image_url='https://bridge.invalid',bridge_token='private-token')
        studio.remember_planner(cfg,False,'Earlier 503: model runner terminated.')
        tags=Mock(status_code=200); tags.json.return_value={'models':[{'name':'qwen3.5:9b'}]}
        bridge=Mock(status_code=200); bridge.json.return_value={
            'image_ready':True,'voice_ready':True,'edit_planner_ready':True,'planner_error':''}
        recovery=Mock(status_code=200); recovery.json.return_value={'planner_ready':True}
        with patch.object(studio,'settings',return_value=cfg), patch.object(studio,'headers',return_value={}), \
             patch.object(studio.requests,'get',side_effect=[tags,bridge]), \
             patch.object(studio.requests,'post',return_value=recovery) as post:
            response=TestClient(main.app).get('/api/studio/health')
        health=response.json()
        self.assertTrue(health['planner_ready'])
        self.assertEqual(health['planner_error'],'')
        self.assertEqual(health['services']['language_model']['status'],'ready')
        self.assertTrue(post.call_args.args[0].endswith('/planner/check'))
        self.assertEqual(post.call_args.kwargs['timeout'],130)

    def test_hindi_romanized_writer_output_is_repaired_before_direction(self):
        project = studio.Project(prompt='Explain riverbank erosion', language='hi', research=False,
                                 duration=20, duration_mode='target')
        valid = {'scenes':[{'text':'पेड़ों की जड़ें मिट्टी को पकड़कर कटाव कम करती हैं।',
                           'visual_prompt':'Tree roots hold riverbank soil together'}]}
        delegate = self.agent_reply(valid)
        writer_calls = []
        def reply(system, message, **options):
            if system.startswith('You are a careful video scriptwriter'):
                writer_calls.append(message)
                if len(writer_calls) == 1:
                    return {'scenes':[{'text':'Ped ki jadain mitti pakadti hain.',
                                      'visual_prompt':'Tree roots hold riverbank soil together'}]}
            return delegate(system, message)
        with patch.object(studio, 'chat', side_effect=reply):
            studio.plan(self.job(project), project)
        self.assertEqual(len(writer_calls), 2)
        self.assertIn('Devanagari', json.loads(writer_calls[1])['validation_error'])
        self.assertEqual(project.scenes[0].text, valid['scenes'][0]['text'])

    def test_ready_script_auto_detection_preserves_dialogue_timing_and_overlays(self):
        from test_ready_script import SAMPLE
        rows=studio.ready_script.parse(SAMPLE)
        p=studio.Project(prompt=SAMPLE,generation_mode='hybrid',duration=20)
        with patch.object(studio,'chat',side_effect=self.agent_reply({})) as chat, \
             patch.object(studio.video_brief,'analyze') as analyst, \
             patch.object(studio.explainer_research,'lookup') as lookup:
            result=studio.plan(self.job(p),p)
        self.assertEqual(chat.call_count,2)
        self.assertTrue(all('scriptwriter' not in c.args[0] for c in chat.call_args_list))
        analyst.assert_not_called()
        lookup.assert_not_called()
        self.assertEqual((p.scene_mode,p.duration,p.generation_mode,p.language,p.aspect_ratio,p.script_voice_gender),
                         ('ready',60,'images','hi','9:16','male'))
        self.assertEqual([s.text for s in p.scenes],[r['text'] for r in rows])
        self.assertEqual([s.end for s in p.scenes],[5,5,5,10,10,10,10,5])
        self.assertTrue(p.scenes[-1].fade_out)
        self.assertEqual(result['scenes'][-1]['overlay_text'],'YOUR STORY IS NOT OVER.')
        saved=studio.Project.model_validate(result)
        self.assertEqual(saved.scenes[-1].overlay_text,p.scenes[-1].overlay_text)

    def test_ready_long_voice_reports_scene_before_images_without_rewriting(self):
        p=studio.Project(scene_mode='ready',duration=10,duration_mode='target',
                         scenes=[studio.Scene(text='Keep this dialogue unchanged.',end=10)])
        with patch.object(studio,'scene_voice',return_value=(self.music,15)), \
             patch.object(studio,'chat') as chat, patch.object(studio,'image_asset') as images:
            with self.assertRaisesRegex(ValueError,r'Scene 1: supplied voiceover needs 15.0s'):
                studio.render(self.job(p),p)
        chat.assert_not_called()
        images.assert_not_called()
        self.assertEqual(p.scenes[0].text,'Keep this dialogue unchanged.')

    def test_ready_motion_slot_limit_is_checked_before_director(self):
        p=studio.Project(prompt='0–10 sec: Visual: A man running. Voiceover: “Keep going.”',
                         scene_mode='ready',generation_mode='motion',motion_preset='preview')
        with patch.object(studio,'chat') as chat:
            with self.assertRaisesRegex(ValueError,'locked slot'):
                studio.plan(self.job(p),p)
        chat.assert_not_called()
        self.assertEqual(p.scenes,[])

    def test_ready_sixty_second_export_music_overlay_and_silent_slots(self):
        from test_ready_script import SAMPLE
        rows=studio.ready_script.parse(SAMPLE)
        p=studio.Project(duration=60,duration_mode='target',scene_mode='ready',resolution='720p',
                         aspect_ratio='9:16',narration=False,captions=False,auto_music='cinematic',
                         scenes=[studio.Scene(asset_id=self.image_meta['id'],text=r['text'],
                             overlay_text=r['overlay_text'],fade_out=r['fade_out'],end=r['end']-r['start'])
                             for r in rows])
        jid=self.job(p)
        with patch.object(studio,'voice_asset',side_effect=AssertionError('Silent choice was ignored')):
            result=studio.render(jid,p)
        stream=next(s for s in studio.probe(self.root/'renders'/jid/'final.mp4')['streams'] if s['codec_type']=='video')
        self.assertEqual(int(stream['nb_frames']),1800)
        self.assertEqual((stream['width'],stream['height']),(720,1280))
        self.assertEqual(result['duration'],60)
        self.assertTrue(studio.audible(self.root/'renders'/jid/'final.mp4'))
        ass=(self.root/'renders'/jid/'captions.ass').read_text('utf-8-sig')
        self.assertIn('Dialogue: 2,0:00:55.00,0:01:00.00,Overlay',ass)
        self.assertIn('YOUR STORY IS NOT OVER.',ass.replace('\\N',' '))
        self.assertNotIn('ज़िंदगी',ass)
        self.assertEqual(result['project']['production_notes']['music']['provider'],'Local instrumental composer')
        import numpy as np
        def pixels(at):
            return np.frombuffer(studio.run([self.ff,'-v','error','-ss',str(at),'-i',
                str(self.root/'renders'/jid/'final.mp4'),'-frames:v','1','-pix_fmt','rgb24',
                '-f','rawvideo','-']),dtype=np.uint8).reshape(1280,720,3)
        self.assertGreater(int(np.sum(np.all(pixels(2)[140:400]>220,axis=2))),100,
                           'Screen text was not burned into the final video')
        self.assertLess(float(pixels(59.96).mean()),10,'Final image did not fade to black')

    def test_ready_silent_visual_scene_does_not_require_dialogue(self):
        p=studio.Project(duration=10,duration_mode='target',scene_mode='ready',
                         scenes=[studio.Scene(text='',visual_prompt='Sunrise',end=10)])
        cache=self.root/'ready-cache';cache.mkdir(exist_ok=True)
        prepared,tempos=studio.prepare_narration(self.job(p),p,cache,[10])
        self.assertEqual(prepared[0],(None,0))

    def test_character_reference_only_conditions_matching_image_scenes(self):
        import shutil
        p=studio.Project(narration=False,captions=False,character_reference=True,resolution='720p',
                         scenes=[studio.Scene(visual_prompt='A young man studying at his desk.',end=1),
                                 studio.Scene(visual_prompt='Empty mountain landscape at dawn.',end=1)])
        p.production_notes={'agent_workflow':{'characters':[{'key':'hero','appearance':'Young man with short dark hair, blue jacket.'}],
            'scene_characters':{p.scenes[0].id:['hero'],p.scenes[1].id:[]}}}
        calls=[]
        def image(prompt,style,ratio,output,reference=None):
            calls.append((prompt,reference))
            shutil.copyfile(self.image,output)
        health=Mock();health.json.return_value={'reference_images':True}
        with patch.object(studio.requests,'get',return_value=health),patch.object(studio,'image_asset',side_effect=image):
            studio.render(self.job(p),p)
            studio.render(self.job(p),p)
        self.assertEqual(len(calls),3,'Unchanged renders should reuse portrait and scene image caches')
        self.assertIsNone(calls[0][1])
        self.assertIsNotNone(calls[1][1])
        self.assertIsNone(calls[2][1])
        health.json.return_value={'reference_images':False}
        with patch.object(studio.requests,'get',return_value=health),patch.object(studio,'image_asset') as images:
            with self.assertRaisesRegex(ValueError,'updated Colab notebook'):
                studio.render(self.job(p),p)
        images.assert_not_called()

    def test_image_request_transmits_optional_reference(self):
        import base64
        cfg=studio.settings().model_copy(update={'image_url':'http://fixture.invalid'})
        response=Mock();response.headers={'content-type':'image/png'};response.content=self.image.read_bytes()
        output=self.root/'reference-output.png'
        with patch.object(studio,'settings',return_value=cfg),patch.object(studio.requests,'post',return_value=response) as post:
            studio.image_asset('A man','cinematic','9:16',output,self.image)
            self.assertEqual(base64.b64decode(post.call_args.kwargs['json']['reference_image']),self.image.read_bytes())
            studio.image_asset('A landscape','cinematic','9:16',output)
            self.assertNotIn('reference_image',post.call_args.kwargs['json'])

    def test_natural_narration_ends_with_speech_and_preserves_editable_timestamps(self):
        import hashlib
        import speech_timing
        text = 'Hello world.'
        words = [{'text':'Hello','start':.1,'end':.6},{'text':'world.','start':.7,'end':1.4}]
        p = studio.Project(duration=20, duration_mode='target', narration_timing='natural',
            resolution='720p', scenes=[studio.Scene(asset_id=self.image_meta['id'],text=text,end=20)])
        def voice(text, language, path):
            studio.run([self.ff,'-y','-v','error','-f','lavfi','-i','sine=frequency=320:duration=1.5',str(path)])
            speech_timing.sidecar(path).write_text(json.dumps({'text':text,'words':words,'duration':1.6,
                'audio_sha256':hashlib.sha256(path.read_bytes()).hexdigest()}),encoding='utf-8')
            return True
        jid = self.job(p)
        with patch.object(studio,'voice_asset',side_effect=voice), patch.object(studio,'chat',side_effect=AssertionError('No rewrite needed')):
            result = studio.render(jid,p)
        self.assertAlmostEqual(result['duration'],1.6,delta=1/30)
        srt=(self.root/'renders'/jid/'captions.srt').read_text('utf-8')
        self.assertIn('00:00:01,400',srt)
        ident=result['scene_assets'][0]['asset_id']
        meta,_=studio.asset(ident)
        self.assertEqual(meta['speech_words'],words)
        edited=studio.Project(resolution='720p',scenes=[studio.Scene(asset_id=ident,media_kind='video',
            text=text,start=.5,end=1.5,speed=2)])
        rendered=studio.render(self.job(edited),edited)
        self.assertEqual(rendered['timeline'][0]['caption_timing'],'speech words')
        self.assertAlmostEqual(rendered['timeline'][0]['words'][-1]['end'],.45)

    def test_repaired_visual_reaches_renderer_and_bypasses_unrelated_cache(self):
        import hashlib, shutil
        p=studio.Project(prompt='Explain apple recognition',resolution='720p',captions=False,
            scenes=[studio.Scene(text='Learn to recognise apples from example photographs.',visual_prompt='Unrelated glowing computer',end=2)])
        old_key=hashlib.sha256(json.dumps(['sdxl-v2',p.scenes[0].visual_prompt,p.style,p.aspect_ratio,
            studio.settings().image_url,studio.settings().image_quality]).encode()).hexdigest()
        cache=self.root/'cache';cache.mkdir(exist_ok=True)
        shutil.copyfile(self.image,cache/(old_key+'.png'))
        fixed='Apple example photographs arranged for comparison beside a new apple photograph.'
        def verdict(matched):
            return {'scenes':[{'scene_id':p.scenes[0].id,'matched':matched,'narration_quote':p.scenes[0].text,
                'reason':'Apple examples explain recognition; an unrelated glowing computer does not.',
                'replacement_prompt':'' if matched else fixed}]}
        def image(prompt,style,ratio,output):
            self.assertEqual(prompt,fixed)
            shutil.copyfile(self.image,output)
        with patch.object(studio,'scene_voice',return_value=(self.music,2)),patch.object(studio,'chat',side_effect=[verdict(False),verdict(True)]) as chat,patch.object(studio,'image_asset',side_effect=image) as images:
            result=studio.render(self.job(p),p)
            studio.render(self.job(p),p)
        self.assertEqual(images.call_count,1)
        self.assertEqual(chat.call_count,2)
        self.assertEqual(result['project']['scenes'][0]['visual_prompt'],fixed)
        self.assertEqual(result['project']['production_notes']['visual_alignment']['status'],'reviewed')

    def test_unresolved_visual_mismatch_stops_before_image_generation(self):
        p=studio.Project(scenes=[studio.Scene(text='Explain apple recognition',visual_prompt='Unrelated computer',end=2)])
        reply={'scenes':[{'scene_id':p.scenes[0].id,'matched':False,'narration_quote':p.scenes[0].text,
            'reason':'This computer does not depict the apple examples.','replacement_prompt':'Another unrelated glowing computer'}]}
        with patch.object(studio,'scene_voice',return_value=(self.music,2)),patch.object(studio,'chat',return_value=reply),patch.object(studio,'image_asset') as image:
            with self.assertRaisesRegex(ValueError,'could not confirm'):
                studio.render(self.job(p),p)
        image.assert_not_called()
        self.assertEqual(p.scenes[0].visual_prompt,'Unrelated computer')

    def test_target_duration_fits_voice_and_exports_twenty_seconds(self):
        p = studio.Project(duration=20, duration_mode='target', resolution='720p', captions=True,
            scenes=[studio.Scene(asset_id=self.image_meta['id'], text='Target timing first scene', end=10),
                    studio.Scene(asset_id=self.image_meta['id'], text='Target timing second scene', end=10)])
        def voice(text, language, path):
            studio.run([self.ff,'-y','-v','error','-f','lavfi','-i','sine=frequency=320:duration=10.4',str(path)])
            return True
        jid = self.job(p)
        with patch.object(studio,'voice_asset',side_effect=voice), patch.object(studio,'chat',side_effect=AssertionError('Small timing drift needs no rewrite')):
            result = studio.render(jid,p)
        self.assertAlmostEqual(result['duration'],20,delta=1/30)
        self.assertEqual(result['audio_status'],'Narration included')
        self.assertTrue(studio.audible(self.root/'renders'/jid/'final.mp4'))
        stream=next(s for s in studio.probe(self.root/'renders'/jid/'final.mp4')['streams'] if s['codec_type']=='video')
        self.assertEqual(int(stream['nb_frames']),600)
        self.assertAlmostEqual(float(stream['duration']),20,places=3)
        report=json.loads((self.root/'renders'/jid/'metadata.json').read_text())
        self.assertTrue(all(1 < tempo <= 1.1 for tempo in report['voice_tempo_adjustments'].values()))
        self.assertIn('00:00:20,000',(self.root/'renders'/jid/'captions.srt').read_text())

    def test_target_rewrites_overlong_voice_once_before_visuals(self):
        p=studio.Project(duration=10,duration_mode='target',scenes=[studio.Scene(text=' '.join(['word']*30),end=10)])
        jid=self.job(p)
        cache=self.root/'timing-cache';cache.mkdir(exist_ok=True)
        with patch.object(studio,'scene_voice',side_effect=[(self.music,18),(self.music,9.5)]), patch.object(studio,'chat',return_value={'scenes':[{'id':p.scenes[0].id,'text':'Machines learn patterns from examples to make predictions.','visual_prompt':'Fruit photographs grouped by shape'}]}) as chat:
            voices,tempos=studio.prepare_narration(jid,p,cache,[10])
        self.assertEqual(chat.call_count,1)
        self.assertEqual(voices[0][1],9.5)
        self.assertEqual(tempos[0],1)
        self.assertTrue(p.scenes[0].text.startswith('Machines learn'))

    def test_target_overlong_after_repair_stops_before_images(self):
        p=studio.Project(duration=10,duration_mode='target',scenes=[studio.Scene(text=' '.join(['word']*30),end=10)])
        with patch.object(studio,'scene_voice',return_value=(self.music,18)), patch.object(studio,'chat',return_value={'scenes':[{'id':p.scenes[0].id,'text':'A short factual example.','visual_prompt':'A concrete example'}]}) as chat, patch.object(studio,'image_asset') as image:
            with self.assertRaisesRegex(ValueError,'could not fill'):
                studio.render(self.job(p),p)
        self.assertEqual(chat.call_count,3)
        image.assert_not_called()

    def test_target_missing_or_silent_voice_stops_before_visuals(self):
        p=studio.Project(duration=10,duration_mode='target',scenes=[studio.Scene(text='',end=10)])
        with patch.object(studio,'image_asset') as image:
            with self.assertRaisesRegex(ValueError,'script is empty'):
                studio.render(self.job(p),p)
        image.assert_not_called()
        p.scenes[0].text='Silent provider response should fail'
        def silence(text,language,path):
            studio.run([self.ff,'-y','-v','error','-f','lavfi','-i','anullsrc=r=48000:cl=stereo','-t','1',str(path)])
            return True
        with patch.object(studio,'voice_asset',side_effect=silence), patch.object(studio,'image_asset') as image:
            with self.assertRaisesRegex(ValueError,'no audible speech'):
                studio.render(self.job(p),p)
        image.assert_not_called()

    def test_target_explicit_script_is_not_rewritten(self):
        p=studio.Project(duration=10,duration_mode='target',scene_mode='sentences',scenes=[studio.Scene(text='Keep my supplied script.',end=10)])
        with patch.object(studio,'scene_voice',return_value=(self.music,18)),patch.object(studio,'chat') as chat:
            with self.assertRaisesRegex(ValueError,'supplied script is too long'):
                studio.render(self.job(p),p)
        chat.assert_not_called()

    def test_target_silent_generation_preserves_choice_and_exact_frames(self):
        p=studio.Project(duration=10,duration_mode='target',narration=False,captions=False,resolution='720p',
            scenes=[studio.Scene(asset_id=self.image_meta['id'],end=10)])
        jid=self.job(p)
        with patch.object(studio,'voice_asset',side_effect=AssertionError('Voice was switched on')):
            result=studio.render(jid,p)
        stream=next(s for s in studio.probe(self.root/'renders'/jid/'final.mp4')['streams'] if s['codec_type']=='video')
        self.assertEqual(int(stream['nb_frames']),300)
        self.assertIn('Silent video',result['audio_status'])

    def test_target_planner_repairs_word_budget_and_keeps_visuals(self):
        p=studio.Project(duration=20,duration_mode='target',generation_mode='images',language='hi',narration=False,captions=True)
        def reply(system,message, **options):
            if system.startswith('You are a concise educational narration editor'):
                body=json.loads(message)
                self.assertTrue(all(s['max_words']==16 for s in body['scenes']))
                return {'scenes':[{'id':s['id'],'text':'कंप्यूटर उदाहरणों से पैटर्न सीखता है।'} for s in body['scenes']]}
            return self.agent_reply({'title':'Learning from examples','scenes':[
                {'text':' '.join(['बहुत']*25),'visual_prompt':'Apples being sorted on a table','slide_title':'Examples','slide_points':['Learn patterns']}
                for _ in range(2)]})(system,message)
        with patch.object(studio,'chat',side_effect=reply) as chat:
            result=studio.plan(self.job(p),p)
        self.assertEqual(chat.call_count,4)
        self.assertTrue(all(len(s['text'].split())<=16 for s in result['scenes']))
        self.assertTrue(all('Apples' in s['visual_prompt'] for s in result['scenes']))

    def setUp(self):
        # These fixtures synthesize sine tones, not speech. Test the local aligner
        # independently; live sample evidence also exercises the real Whisper model.
        aligner = patch.object(studio.speech_timing,'align_narration',return_value=[])
        aligner.start()
        self.addCleanup(aligner.stop)
        model = patch.dict(studio.ENV,{'get_whisper_model':lambda:None})
        model.start()
        self.addCleanup(model.stop)
        # External semantic reviewer is deterministic here; separate tests cover mismatches.
        reviewer = patch.object(studio, 'chat', side_effect=self.agent_reply({}))
        reviewer.start()
        self.addCleanup(reviewer.stop)
        lookup = patch.object(studio.explainer_research, 'lookup', return_value={'status':'unavailable','sources':[]})
        lookup.start()
        self.addCleanup(lookup.stop)
        # Existing writer/renderer fixtures isolate those stages. Brief integration
        # below restores the real analyst and supplies only its external AI replies.
        analyst = patch.object(studio.video_brief, 'analyze',
                               side_effect=lambda project,chat,checkpoint:studio.video_brief.fallback(project))
        analyst.start()
        self.addCleanup(analyst.stop)

    def test_interpreted_brief_drives_research_writer_and_visuals_in_all_modes(self):
        for mode in ('avatar','images','hybrid','motion'):
            for research_enabled in (True,False):
                with self.subTest(mode=mode,research=research_enabled):
                    interpreted={'topic':'Solar energy','objective':'Explain solar electricity with a home example',
                        'audience':'School children','tone':'Simple conversational Hindi','kind':'explanation',
                        'must_include':['Household example'],'avoid':['Technical jargon'],
                        'visual_approach':'Show panels supplying household appliances',
                        'needs_research':True,'search_query':'Solar power photovoltaic cells'}
                    references={'status':'retrieved','sources':[{'title':'Solar power',
                        'url':'https://en.wikipedia.org/wiki/Solar_power','excerpt':'Introductory solar electricity reference.'}]}
                    count=4 if mode in ('motion','hybrid') else 2
                    draft={'scenes':[{'text':'सूरज की रोशनी से घर के लिए बिजली बनती है।',
                        'visual_prompt':'Solar panels powering a home','slide_title':'Solar power',
                        'slide_points':['Electricity from light']} for _ in range(count)]}
                    seen=[]
                    def reply(system,message, **options):
                        body=json.loads(message)
                        if system.startswith("You are SmartEdit's video brief analyst"):
                            seen.append('brief')
                            self.assertEqual(body['selected_settings']['duration_seconds'],20)
                            return interpreted
                        if system.startswith('You are a careful video scriptwriter'):
                            seen.append('writer')
                            self.assertEqual(body['video_brief']['audience'],'School children')
                            self.assertEqual(body['video_brief']['must_include'],['Household example'])
                            self.assertEqual(body['references'],references if research_enabled else {'status':'disabled','sources':[]})
                            return draft
                        if system.startswith("You are SmartEdit's shot director"):
                            self.assertEqual(body['video_brief']['visual_approach'],interpreted['visual_approach'])
                        return self.agent_reply(draft)(system,message)
                    p=studio.Project(prompt='bhai bacchon ko solar power samjhana ghar ka example dena, jargon mat use karna',
                        language='hi',duration=20,generation_mode=mode,research=research_enabled,duration_mode='target')
                    with patch.object(studio.video_brief,'analyze',side_effect=ANALYZE_VIDEO_BRIEF), \
                         patch.object(studio,'chat',side_effect=reply), \
                         patch.object(studio.explainer_research,'lookup',return_value=references) as lookup:
                        result=studio.plan(self.job(p),p)
                    self.assertEqual(seen,['brief','writer'])
                    if research_enabled:
                        lookup.assert_called_once_with('Solar power photovoltaic cells',fallback_query='Solar energy')
                    else:
                        lookup.assert_not_called()
                    self.assertEqual(result['production_notes']['video_brief']['avoid'],['Technical jargon'])
                    self.assertEqual(result['duration'],20)

    def test_creative_brief_skips_factual_lookup_and_manual_script_skips_analyst(self):
        p=studio.Project(prompt='A playful puppy adventure',generation_mode='images',research=True)
        brief={**studio.video_brief.fallback(p),'status':'interpreted','kind':'story','needs_research':False}
        draft={'scenes':[{'text':'The puppy found a little ball.','visual_prompt':'Puppy discovering a ball in grass'}]}
        with patch.object(studio.video_brief,'analyze',return_value=brief), \
             patch.object(studio,'chat',side_effect=self.agent_reply(draft)) as chat, \
             patch.object(studio.explainer_research,'lookup') as lookup:
            studio.plan(self.job(p),p)
        lookup.assert_not_called()
        self.assertEqual(p.production_notes['research']['status'],'not_needed')
        self.assertNotIn('define the topic',chat.call_args_list[0].args[0])
        p.scene_mode='sentences'
        with patch.object(studio.video_brief,'analyze') as analyst, \
             patch.object(studio,'chat',side_effect=self.agent_reply(draft)):
            studio.plan(self.job(p),p)
        analyst.assert_not_called()

    def test_generate_owns_plan_and_render_and_returns_editable_project(self):
        p = studio.Project(prompt='Explain artificial intelligence', generation_mode='avatar', language='hi', duration=30)
        jid = self.job(p)
        studio.JOBS[jid]['kind'] = 'generate'
        def planned(job, project):
            studio.event(job, 'Writer', 'completed', 'Ready', 95)
            self.assertEqual(studio.JOBS[job]['progress'], 19)
            return project.model_copy(update={'scenes':[studio.Scene(text='एआई उदाहरणों से सीखता है।')]}).model_dump()
        def rendered(job, project):
            studio.event(job, 'Renderer', 'running', 'Encoding', 50)
            self.assertEqual(studio.JOBS[job]['progress'], 60)
            self.assertEqual(project.language, 'hi')
            self.assertTrue(studio.path_for('projects', project.id).exists())
            return {'video_url':'/verified.mp4'}
        with patch.object(studio, 'plan', side_effect=planned) as plan, patch.object(studio, 'render', side_effect=rendered) as render:
            studio.worker(jid, studio.generate, p)
        job = studio.JOBS[jid]
        self.assertEqual(job['status'], 'completed')
        self.assertEqual(job['result']['project']['scenes'][0]['text'], 'एआई उदाहरणों से सीखता है।')
        self.assertEqual(plan.call_count, 1)
        self.assertEqual(render.call_count, 1)

    def test_generate_keeps_reviewed_scenes_and_real_mp4(self):
        p = studio.Project(prompt='Reviewed', narration=False, captions=False, resolution='720p',
            scenes=[studio.Scene(asset_id=self.video_meta['id'], media_kind='video', text='My edited caption', end=.5)])
        jid = self.job(p)
        studio.JOBS[jid]['kind'] = 'generate'
        with patch.object(studio, 'plan', side_effect=AssertionError('Must not replan reviewed scenes')):
            studio.worker(jid, studio.generate, p)
        job = studio.JOBS[jid]
        self.assertEqual(job['status'], 'completed', job.get('error'))
        self.assertEqual(job['result']['project']['scenes'][0]['text'], 'My edited caption')
        self.assertEqual(self.client.get(job['result']['video_url']).status_code, 200)

    def test_cancel_between_planning_and_render_never_starts_render(self):
        p = studio.Project(prompt='Explain AI')
        jid = self.job(p)
        def planned(job, project):
            studio.JOBS[job]['cancel_requested'] = True
            return project.model_dump()
        with patch.object(studio, 'plan', side_effect=planned), patch.object(studio, 'render') as render:
            studio.worker(jid, studio.generate, p)
        render.assert_not_called()
        self.assertEqual(studio.JOBS[jid]['status'], 'cancelled')

    def test_research_references_reach_writer_and_saved_report(self):
        p = studio.Project(prompt='Explain artificial intelligence', generation_mode='avatar', language='hi')
        references = {'status':'retrieved','sources':[{'title':'AI','url':'https://en.wikipedia.org/wiki/Artificial_intelligence','excerpt':'AI supports learning and reasoning.'}]}
        with patch.object(studio.explainer_research, 'lookup', return_value=references), patch.object(studio,'chat',side_effect=self.agent_reply({'scenes':[{'text':'कृत्रिम बुद्धिमत्ता मशीनों की क्षमता है।','visual_prompt':'Computer classifying fruit'}]})) as chat:
            result = studio.plan(self.job(p), p)
        self.assertEqual(json.loads(chat.call_args_list[0].args[1])['references'], references)
        self.assertEqual(result['production_notes']['research'], references)
        self.assertIn('concrete everyday example', chat.call_args_list[0].args[0])
        p.research = False
        with patch.object(studio.explainer_research, 'lookup') as lookup, patch.object(studio,'chat',side_effect=self.agent_reply({'scenes':[{'text':'सरल व्याख्या।','visual_prompt':'Supporting illustration'}]})):
            studio.plan(self.job(p), p)
        lookup.assert_not_called()

    def test_generate_endpoint_validates_and_queues_one_workflow(self):
        with patch.object(studio,'queue',return_value={'id':'a'*32}) as queue:
            self.assertEqual(self.client.post('/api/studio/generate',json={'prompt':'Explain AI','generation_mode':'avatar'}).status_code, 200)
            self.assertEqual(queue.call_args.args[0], 'generate')
            self.assertIs(queue.call_args.args[2], studio.generate)
        self.assertEqual(self.client.post('/api/studio/generate',json={'prompt':''}).status_code, 400)

    def test_short_topics_are_accepted_but_empty_prompts_are_not(self):
        for endpoint in ('plan','generate'):
            with patch.object(studio,'queue',return_value={'id':'a'*32}) as queue:
                for prompt in ('AI','Sun','जल'):
                    self.assertEqual(self.client.post('/api/studio/'+endpoint,
                        json={'prompt':prompt}).status_code,200)
                self.assertEqual(queue.call_count,3)
                for prompt in ('','   ','\n'):
                    self.assertEqual(self.client.post('/api/studio/'+endpoint,
                        json={'prompt':prompt}).status_code,400)

    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='smartedit-tests-')
        cls.root = Path(cls.temp.name)
        cls.original_data = studio.DATA
        studio.DATA = cls.root
        cls.client = TestClient(main.app)
        cls.ff = main.FFMPEG_PATH
        cls.video = cls.root/'source.mp4'
        cls.music = cls.root/'music.wav'
        cls.image = cls.root/'image.png'
        studio.run([cls.ff,'-y','-v','error','-f','lavfi','-i','testsrc2=size=320x180:rate=30',
            '-f','lavfi','-i','sine=frequency=440:sample_rate=48000','-t','3','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac',str(cls.video)])
        studio.run([cls.ff,'-y','-v','error','-f','lavfi','-i','sine=frequency=220:duration=2',str(cls.music)])
        studio.run([cls.ff,'-y','-v','error','-f','lavfi','-i','color=c=teal:size=320x180','-frames:v','1',str(cls.image)])
        cls.video_meta = cls.upload(cls.video)
        cls.music_meta = cls.upload(cls.music)
        cls.image_meta = cls.upload(cls.image)

    @classmethod
    def tearDownClass(cls):
        studio.DATA = cls.original_data
        cls.temp.cleanup()

    @classmethod
    def upload(cls, path):
        with path.open('rb') as file:
            response = cls.client.post('/api/studio/assets',files={'file':(path.name,file)})
        if response.status_code != 200:
            raise AssertionError(response.text)
        return response.json()

    def job(self, project):
        ident = uuid.uuid4().hex
        studio.JOBS[ident] = {'id':ident,'kind':'render','project_id':project.id,'status':'running','progress':0,'events':[]}
        return ident

    @staticmethod
    def agent_reply(draft):
        def reply(system, message, **options):
            if system.startswith("You are SmartEdit's narration-to-visual reviewer"):
                return {'scenes':[{'scene_id':s['scene_id'],'matched':True,'narration_quote':s['text'],
                    'reason':'Fixture visual depicts the narrated example.','replacement_prompt':''} for s in json.loads(message)['scenes']]}
            if system.startswith("You are SmartEdit's shot director"):
                scenes = json.loads(message)['scenes']
                return {'characters':[], 'shots':[{'scene_id':s['scene_id'],
                    'visual_prompt':s['visual_prompt']+'; coherent framing and soft natural light.',
                    'characters':[]} for s in scenes]}
            return draft
        return reply

    def test_api_validation_and_persistence(self):
        p = studio.Project(scenes=[studio.Scene(asset_id=self.video_meta['id'],media_kind='video',end=2)])
        response = self.client.put('/api/studio/projects/'+p.id,json=p.model_dump())
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['scenes'][0]['media_kind'],'video')
        self.assertIn(p.id,[x['id'] for x in self.client.get('/api/studio/projects').json()])
        invalid = p.model_dump()
        invalid['scenes'][0]['end'] = 0
        self.assertEqual(self.client.post('/api/studio/render',json=invalid).status_code,422)
        self.assertEqual(self.client.get('/api/studio/assets/not-an-id').status_code,400)
        self.assertEqual(self.client.post('/api/studio/assets',files={'file':('fake.mp4',b'not video')}).status_code,400)

    def test_storyboard_retains_language_and_editable_scenes(self):
        p = studio.Project(prompt='A useful Hindi tutorial',language='hi')
        jid = self.job(p)
        with patch.object(studio,'chat',side_effect=self.agent_reply({'title':'Solar energy','scenes':[{'text':'नमस्ते दोस्तों','visual_prompt':'Sunlit solar panels'}]})):
            result = studio.plan(jid,p)
        self.assertEqual(result['language'],'hi')
        self.assertGreater(result['scenes'][0]['end'],result['scenes'][0]['start'])
        self.assertEqual(len(result['scenes'][0]['id']),32)

    def test_avatar_planner_repairs_invalid_drafts_before_directing(self):
        valid = {'title':'Solar energy','scenes':[{'text':'सूरज से बिजली बनती है।',
            'visual_prompt':'Solar panels in sunlight','slide_title':'सौर ऊर्जा','slide_points':['बिजली']}]}
        invalid_drafts = [{}, {'scenes':[]}, {'scenes':{}}, {'scenes':[None]},
                          {'scenes':[{'text':'Hello'}]},
                          {'scenes':[{**valid['scenes'][0],'slide_points':None}]}]
        for invalid in invalid_drafts:
            with self.subTest(invalid=invalid):
                drafts = iter([invalid, valid])
                def reply(system, message, **options):
                    if system.startswith('You are a careful video scriptwriter'):
                        return next(drafts)
                    return self.agent_reply(valid)(system, message)
                p = studio.Project(prompt='Explain solar energy',generation_mode='avatar',
                                   duration=65,language='hi',duration_mode='target',research=False)
                with patch.object(studio,'chat',side_effect=reply) as chat:
                    result = studio.plan(self.job(p),p)
                self.assertEqual(result['scenes'][0]['text'],valid['scenes'][0]['text'])
                repair = json.loads(chat.call_args_list[1].args[1])
                self.assertEqual(repair['invalid_draft'],invalid)
                self.assertIn('two or three connected spoken sentences',chat.call_args_list[0].args[0])
                self.assertNotIn('about 2 words per second',chat.call_args_list[0].args[0])

    def test_invalid_storyboard_retries_are_bounded(self):
        p = studio.Project(prompt='Explain solar energy',generation_mode='avatar',research=False)
        with patch.object(studio,'chat',return_value={'scenes':[]}) as chat, \
             patch.object(studio,'direct_scenes') as director:
            with self.assertRaisesRegex(ValueError,'after 3 attempts'):
                studio.plan(self.job(p),p)
        self.assertEqual(chat.call_count,3)
        director.assert_not_called()

    def test_all_modes_repair_invalid_scene_lists_and_json(self):
        for mode in ('avatar','images','hybrid','motion'):
            for language in ('hi','en'):
                count = 4 if mode in ('hybrid','motion') else 2
                scene={'text':'सूरज से बिजली बनती है।' if language=='hi' else 'Sunlight produces electricity.',
                       'visual_prompt':'Solar panels supplying a house',
                       'slide_title':'Solar energy','slide_points':['Electricity from sunlight']}
                valid={'title':'Solar energy','scenes':[dict(scene) for _ in range(count)]}
                invalid_drafts=[None, [], {}, {'scenes':[]}, {'scenes':{}},
                    {'scenes':[None]*count}, {'scenes':[{'text':'Hello'}]*count},
                    {'scenes':[{**scene,'text':''}]*count},
                    {'scenes':[{**scene,'visual_prompt':42}]*count},
                    ValueError('Invalid JSON'),ValueError('Output limit reached')]
                if mode == 'avatar':
                    invalid_drafts.append({'scenes':[{**scene,'slide_points':None}]*count})
                if mode in ('hybrid','motion'):
                    invalid_drafts.append({'scenes':[scene]})
                for invalid in invalid_drafts:
                    with self.subTest(mode=mode,language=language,invalid=str(invalid)[:80]):
                        drafts=iter([invalid, valid])
                        def reply(system,message, **options):
                            if system.startswith('You are a careful video scriptwriter'):
                                draft=next(drafts)
                                if isinstance(draft,Exception):
                                    raise draft
                                return draft
                            return self.agent_reply(valid)(system,message)
                        p=studio.Project(prompt='Explain solar energy',generation_mode=mode,language=language,
                                         duration=20,duration_mode='target',research=False)
                        with patch.object(studio,'chat',side_effect=reply) as chat:
                            result=studio.plan(self.job(p),p)
                        writer_calls=[c for c in chat.call_args_list if c.args[0].startswith('You are a careful video scriptwriter')]
                        self.assertEqual(len(writer_calls),2)
                        self.assertEqual(len(result['scenes']),count)
                        self.assertTrue(all(s['text']==scene['text'] for s in result['scenes']))
                        self.assertTrue(json.loads(writer_calls[1].args[1])['validation_error'])

    def test_all_modes_bound_failed_repairs_and_preserve_connection_errors(self):
        for mode in ('avatar','images','hybrid','motion'):
            for failure in ({'scenes':[]}, ValueError('Invalid JSON'),RuntimeError('Planner unavailable')):
                with self.subTest(mode=mode,failure=str(failure)):
                    p=studio.Project(prompt='Explain solar energy',generation_mode=mode,research=False)
                    def reply(*args, **options):
                        if isinstance(failure,Exception):
                            raise failure
                        return failure
                    with patch.object(studio,'chat',side_effect=reply) as chat, \
                         patch.object(studio,'direct_scenes') as director:
                        with self.assertRaises((ValueError,RuntimeError)):
                            studio.plan(self.job(p),p)
                    self.assertEqual(chat.call_count,1 if isinstance(failure,RuntimeError) else 3)
                    director.assert_not_called()

    def test_avatar_expands_short_narration_before_real_exact_export(self):
        import shutil
        p=studio.Project(prompt='Explain solar energy',generation_mode='avatar',language='en',
                         duration=55,duration_mode='target',research=False,resolution='720p',captions=False,
                         scenes=[studio.Scene(text='Short headline.',visual_prompt='Solar panels',end=11)
                                 for _ in range(5)])
        expanded='Sunlight reaches the solar panel. Its cells convert light into electricity, which can power appliances in a home.'
        def reply(system,message, **options):
            if system.startswith('You are an educational video narration editor'):
                request=json.loads(message)
                self.assertLess(request['measured_seconds'],20)
                return {'scenes':[{'id':s.id,'text':expanded,'slide_title':'Solar power',
                    'slide_points':['Light becomes electricity'],'visual_prompt':'Solar panels powering household appliances'}
                    for s in p.scenes]}
            return self.agent_reply({})(system,message)
        def voice(text,language,path):
            seconds=10.5 if text==expanded else 2.5
            studio.run([self.ff,'-y','-v','error','-f','lavfi','-i',
                        f'sine=frequency=320:duration={seconds}',str(path)])
            return True
        jid=self.job(p)
        with patch.object(studio,'chat',side_effect=reply),patch.object(studio,'voice_asset',side_effect=voice), \
             patch.object(studio,'image_asset',side_effect=lambda prompt,style,ratio,out:shutil.copyfile(self.image,out)):
            result=studio.render(jid,p)
        self.assertAlmostEqual(result['duration'],55,places=2)
        report=json.loads((self.root/'renders'/jid/'metadata.json').read_text())
        fit=report['project']['production_notes']['narration_fit']
        self.assertEqual(fit['rewrite_attempts'],1)
        self.assertGreater(fit['speech_seconds'],52)
        self.assertTrue(all(s.text==expanded for s in p.scenes))
        self.assertTrue(all('appliances' in s.visual_prompt for s in p.scenes))
        gaps=studio.speech_timing.quiet_intervals(self.ff,self.root/'renders'/jid/'final.mp4')
        self.assertTrue(all(end-start<1 for start,end in gaps),gaps)

    def test_avatar_does_not_render_silence_when_expansion_fails(self):
        p=studio.Project(generation_mode='avatar',duration=60,duration_mode='target',
                         scenes=[studio.Scene(text='A short line.',end=12) for _ in range(5)])
        def reply(system,message, **options):
            return {'scenes':[{'id':s.id,'text':s.text,'slide_title':'Heading',
                'slide_points':['Point'],'visual_prompt':'Relevant supporting image'} for s in p.scenes]}
        with patch.object(studio,'scene_voice',return_value=(self.music,2.5)), \
             patch.object(studio,'chat',side_effect=reply) as chat,patch.object(studio,'image_asset') as images:
            with self.assertRaisesRegex(ValueError,'could not fill'):
                studio.render(self.job(p),p)
        self.assertEqual(chat.call_count,3)
        images.assert_not_called()

    def test_all_auto_modes_plan_narration_for_forty_seconds(self):
        for mode in ('avatar','images','motion','hybrid'):
            with self.subTest(mode=mode):
                count = 8 if mode in ('motion','hybrid') else 3
                draft={'scenes':[{'text':'सूरज की रोशनी से बिजली बनती है।',
                    'visual_prompt':'Solar panels supplying a home','slide_title':'Solar energy',
                    'slide_points':['Sunlight becomes electricity']} for _ in range(count)]}
                p=studio.Project(prompt='Explain solar energy',generation_mode=mode,duration=40,
                                 duration_mode='target',language='hi',research=False)
                with patch.object(studio,'chat',side_effect=self.agent_reply(draft)) as chat:
                    studio.plan(self.job(p),p)
                request=json.loads(chat.call_args_list[0].args[1])
                self.assertEqual(request['target_seconds'],40)
                self.assertEqual(request['target_words'],100)
                self.assertEqual(request['scene_count'],count)
                self.assertEqual(request['selected_settings']['mode'],mode)
                self.assertEqual(request['selected_settings']['duration_seconds'],40)
                self.assertEqual(request['selected_settings']['language'],'hi')
                expected=['motion']*count if mode=='motion' else ['motion']+['image']*(count-1) if mode=='hybrid' else ['avatar_slide' if mode=='avatar' else 'image']*count
                self.assertEqual(request['visual_kind_by_scene'],expected)
                self.assertNotIn('at most 8 words',chat.call_args_list[0].args[0])
                self.assertEqual(len(p.scenes),count)
                self.assertTrue(all(s.text==draft['scenes'][0]['text'] for s in p.scenes))

    def test_images_hybrid_and_motion_expand_then_export_exactly_forty_seconds(self):
        import shutil
        for mode in ('images','hybrid','motion'):
            with self.subTest(mode=mode):
                count=3 if mode=='images' else 8
                expanded=f'{mode}: Sunlight reaches solar cells and produces electricity to power household appliances.'
                p=studio.Project(prompt='Explain solar energy',generation_mode=mode,duration=40,
                    duration_mode='target',motion_preset='preview',resolution='720p',captions=False,
                    scenes=[studio.Scene(text=f'{mode} short headline.',visual_prompt=f'{mode} solar panel {i}',
                                         end=40/count) for i in range(count)])
                def reply(system,message, **options):
                    if system.startswith('You are an educational video narration editor'):
                        body=json.loads(message)
                        self.assertEqual(body['generation_mode'],mode)
                        self.assertTrue(all(s['target_words']>len(s['text'].split()) for s in body['scenes']))
                        return {'scenes':[{'id':s.id,'text':expanded,
                            'visual_prompt':f'{mode} solar cells powering a household appliance {i}'}
                            for i,s in enumerate(p.scenes)]}
                    return self.agent_reply({})(system,message)
                def voice(text,language,path):
                    seconds=(12.9 if mode=='images' else 4.7) if text==expanded else 1.5
                    studio.run([self.ff,'-y','-v','error','-f','lavfi','-i',
                                f'sine=frequency=320:duration={seconds}',str(path)])
                    return True
                def motion(job,prompt,style,ratio,out,*args):
                    self.assertTrue(all(s.text==expanded for s in p.scenes))
                    shutil.copyfile(self.video,out)
                jid=self.job(p)
                with patch.object(studio,'chat',side_effect=reply),patch.object(studio,'voice_asset',side_effect=voice), \
                     patch.object(studio,'image_asset',side_effect=lambda prompt,style,ratio,out:shutil.copyfile(self.image,out)) as images, \
                     patch.object(studio,'motion_service'),patch.object(studio,'motion_asset',side_effect=motion) as motions:
                    result=studio.render(jid,p)
                self.assertAlmostEqual(result['duration'],40,places=2)
                output=self.root/'renders'/jid/'final.mp4'
                stream=next(s for s in studio.probe(output)['streams'] if s['codec_type']=='video')
                self.assertEqual(int(stream['nb_frames']),1200)
                self.assertEqual(motions.call_count,8 if mode=='motion' else 1 if mode=='hybrid' else 0)
                self.assertEqual(images.call_count,3 if mode=='images' else 7 if mode=='hybrid' else 0)
                self.assertEqual(p.production_notes['narration_fit']['rewrite_attempts'],1)
                self.assertGreater(p.production_notes['narration_fit']['speech_seconds'],37)
                self.assertTrue(all(end-start<.7 for start,end in studio.speech_timing.quiet_intervals(self.ff,output)))

    def test_failed_image_never_reports_completed_video(self):
        p = studio.Project(scenes=[studio.Scene(text='Hello',visual_prompt='A tree')])
        jid = self.job(p)
        with patch.object(studio,'scene_voice',return_value=(self.music,2)), patch.object(studio,'image_asset',side_effect=RuntimeError('Image provider offline')):
            studio.worker(jid,studio.render,p)
        self.assertEqual(studio.JOBS[jid]['status'],'failed')
        self.assertIn('Image provider offline',studio.JOBS[jid]['error'])
        self.assertEqual(self.client.get('/api/studio/jobs/'+jid+'/file/video').status_code,409)

    def test_scene_modes_enforce_selected_script_boundaries(self):
        for mode, prompt in [('sentences','पहला दृश्य। दूसरा दृश्य।'),
                             ('paragraphs','First part.\n\nSecond part.'),
                             ('manual','[Scene 1] First part.\n[Scene 2] Second part.')]:
            with self.subTest(mode=mode):
                p = studio.Project(prompt=prompt, scene_mode=mode, duration=10, language='hi')
                with patch.object(studio,'chat',side_effect=self.agent_reply({'scenes':[
                    {'text':'पहला दृश्य','visual_prompt':'First visual'},
                    {'text':'दूसरा दृश्य','visual_prompt':'Second visual'}]})) as chat:
                    result = studio.plan(self.job(p),p)
                request = json.loads(chat.call_args_list[0].args[1])
                self.assertEqual(request['scene_mode'],mode)
                self.assertEqual(len(request['script_segments']),2)
                self.assertEqual(request['language'],'hi')
                self.assertEqual([s['end'] for s in result['scenes']],[5,5])
                with patch.object(studio,'chat',return_value={'scenes':[{'text':'One','visual_prompt':'One'}]}):
                    with self.assertRaisesRegex(ValueError,'exactly 2'):
                        studio.plan(self.job(p),p)
        with self.assertRaisesRegex(ValueError,'Manual scenes'):
            studio.script_segments(studio.Project(prompt='No tags here',scene_mode='manual'))
        with self.assertRaisesRegex(ValueError,'Scene count'):
            studio.script_segments(studio.Project(prompt='One shot.',scene_mode='sentences',generation_mode='motion',duration=60))

    def test_subtitles_without_narration_survive_planning_and_real_export(self):
        p = studio.Project(prompt='A quiet landscape',narration=False,captions=True,duration=10,
                           aspect_ratio='16:9',resolution='720p')
        with patch.object(studio,'chat',side_effect=self.agent_reply({'scenes':[{'text':'A quiet landscape','visual_prompt':'A mountain lake'}]})) as chat:
            studio.plan(self.job(p),p)
        self.assertFalse(json.loads(chat.call_args_list[0].args[1])['narration_enabled'])
        self.assertTrue(json.loads(chat.call_args_list[0].args[1])['captions_enabled'])
        self.assertEqual(p.scenes[0].text,'A quiet landscape')
        p.scenes[0].asset_id=self.image_meta['id']
        p.scenes[0].end=.5
        with patch.object(studio,'voice_asset',side_effect=AssertionError('Narration disabled')):
            jid=self.job(p)
            studio.worker(jid,studio.render,p)
        self.assertEqual(studio.JOBS[jid]['status'],'completed',studio.JOBS[jid].get('error'))
        self.assertIn('A quiet landscape',(self.root/'renders'/jid/'captions.srt').read_text('utf-8'))
        self.assertEqual(self.client.get('/api/studio/jobs/'+jid+'/file/video').status_code,200)

    def test_real_video_trim_speed_music_captions_and_download(self):
        p = studio.Project(aspect_ratio='9:16',resolution='720p',brand='SmartEdit test',color='warm',denoise=True,
            music_id=self.music_meta['id'],scenes=[
                studio.Scene(asset_id=self.video_meta['id'],media_kind='video',start=.5,end=2.5,speed=2,text='First scene captions'),
                studio.Scene(asset_id=self.video_meta['id'],media_kind='video',start=0,end=1,mute=True,text='Second muted scene')])
        jid = self.job(p)
        studio.worker(jid,studio.render,p)
        job = studio.JOBS[jid]
        self.assertEqual(job['status'],'completed',job.get('error'))
        self.assertAlmostEqual(job['result']['duration'],2,delta=.1)
        info = studio.probe(self.root/'renders'/jid/'final.mp4')
        video = next(s for s in info['streams'] if s['codec_type']=='video')
        self.assertEqual((video['width'],video['height']),(720,1280))
        self.assertTrue(any(s['codec_type']=='audio' for s in info['streams']))
        subtitles = (self.root/'renders'/jid/'captions.srt').read_text('utf-8')
        self.assertIn('First scene captions',subtitles)
        self.assertIn('00:00:01,000',subtitles)
        self.assertEqual(self.client.get('/api/studio/jobs/'+jid+'/file/video').status_code,200)
        self.assertTrue((self.root/'renders'/jid/'metadata.json').exists())

    def test_real_image_voice_duration_and_muted_scene(self):
        p = studio.Project(aspect_ratio='1:1',captions=False,scenes=[
            studio.Scene(asset_id=self.image_meta['id'],text='Test speech',end=9,speed=2),
            studio.Scene(asset_id=self.image_meta['id'],text='',mute=True,end=.5)])
        jid = self.job(p)
        def voice(text,language,path):
            studio.run([self.ff,'-y','-v','error','-i',str(self.music),str(path)])
            return True
        with patch.object(studio,'voice_asset',side_effect=voice):
            studio.worker(jid,studio.render,p)
        job = studio.JOBS[jid]
        self.assertEqual(job['status'],'completed',job.get('error'))
        self.assertAlmostEqual(job['result']['duration'],5,delta=.15)
        video = next(s for s in studio.probe(self.root/'renders'/jid/'final.mp4')['streams'] if s['codec_type']=='video')
        self.assertEqual((video['width'],video['height']),(1080,1080))
        self.assertEqual((self.root/'renders'/jid/'captions.srt').read_text('utf-8'),'')

    def test_cancel_prevents_success(self):
        p = studio.Project(scenes=[studio.Scene(asset_id=self.image_meta['id'],mute=True,end=.5)])
        jid = self.job(p)
        self.client.post('/api/studio/jobs/'+jid+'/cancel')
        studio.worker(jid,studio.render,p)
        self.assertEqual(studio.JOBS[jid]['status'],'cancelled')

    def test_28_capabilities_are_honest(self):
        rows = self.client.get('/api/studio/agents').json()
        self.assertEqual(len(rows),28)
        lip = next(x for x in rows if x['id']=='lip_sync')
        self.assertEqual(lip['capability'],'Optional Colab model')
        self.assertIn('test five seconds',lip['note'])

    def effect_video(self):
        path=self.root/'green-screen.mp4'
        studio.run([self.ff,'-y','-v','error','-f','lavfi','-i',
            'color=c=0x00ff00:size=320x180:rate=30,drawbox=x=120:y=60:w=80:h=60:color=red:t=fill',
            '-t','1','-c:v','libx264','-pix_fmt','yuv420p',str(path)])
        return self.upload(path)

    def effect_frame(self, jid, seconds):
        import numpy as np
        raw=studio.run([self.ff,'-v','error','-ss',str(seconds),'-i',str(self.root/'renders'/jid/'final.mp4'),
            '-frames:v','1','-vf','scale=100:100','-f','rawvideo','-pix_fmt','rgb24','pipe:1'])
        return np.frombuffer(raw,dtype=np.uint8).reshape(100,100,3)

    def test_real_chroma_key_replaces_background_preserves_foreground(self):
        meta=self.effect_video()
        p=studio.Project(resolution='720p',narration=False,captions=False,scenes=[studio.Scene(
            asset_id=meta['id'],media_kind='video',end=1,effects={'key_enabled':True,'background_color':'#0000ff'})])
        jid=self.job(p);result=studio.render(jid,p);frame=self.effect_frame(jid,.5)
        self.assertGreater(int(frame[10,10,2]),200)
        self.assertLess(int(frame[10,10,1]),35)
        self.assertGreater(int(frame[50,50,0]),190)
        self.assertAlmostEqual(result['duration'],1,delta=.05)

    def test_real_background_image_and_moving_overlay(self):
        meta=self.effect_video()
        p=studio.Project(resolution='720p',narration=False,captions=False,scenes=[studio.Scene(
            asset_id=meta['id'],media_kind='video',end=1,effects={'key_enabled':True,'background_id':self.image_meta['id'],
            'region':'image','overlay_id':self.image_meta['id'],'x':0,'end_x':1,'y':0,'end_y':1,'width':.2,'height':.2})])
        jid=self.job(p);studio.render(jid,p);frame=self.effect_frame(jid,.5)
        self.assertTrue(70<int(frame[10,10,1])<180)
        self.assertTrue(70<int(frame[10,10,2])<180)
        # With key disabled, the teal overlay must move from top-left to bottom-right over green.
        p.scenes[0].effects.key_enabled=False
        jid=self.job(p);studio.render(jid,p)
        first,last=self.effect_frame(jid,.05),self.effect_frame(jid,.9)
        self.assertGreater(int(first[12,12,2]),80)
        self.assertLess(int(last[12,12,2]),40)
        self.assertGreater(int(last[82,82,2]),80)

    def test_real_moving_blur_changes_only_selected_region(self):
        p=studio.Project(resolution='720p',narration=False,captions=False,scenes=[studio.Scene(
            asset_id=self.video_meta['id'],media_kind='video',end=.5)])
        clean=self.job(p);studio.render(clean,p)
        p.scenes[0].effects.region='blur';p.scenes[0].effects.width=.5;p.scenes[0].effects.height=.5
        blurred=self.job(p);studio.render(blurred,p)
        a,b=self.effect_frame(clean,.2),self.effect_frame(blurred,.2)
        self.assertGreater(abs(a[25:75,25:75].astype(float)-b[25:75,25:75]).mean(),.8)
        self.assertLess(abs(a[:15,:15].astype(float)-b[:15,:15]).mean(),3)

    def test_fades_preserve_duration_and_reach_black_or_white(self):
        for transition,expected in [('fade_black',0),('fade_white',255)]:
            with self.subTest(transition=transition):
                p=studio.Project(resolution='720p',narration=False,captions=False,transition=transition,
                    transition_duration=.2,scenes=[studio.Scene(asset_id=self.image_meta['id'],end=.6),studio.Scene(asset_id=self.image_meta['id'],end=.6)])
                jid=self.job(p);result=studio.render(jid,p)
                self.assertAlmostEqual(result['duration'],1.2,delta=.05)
                frame=self.effect_frame(jid,.6)
                self.assertLess(abs(frame.astype(float).mean()-expected),15)
                self.assertGreater(self.effect_frame(jid,.95).astype(float).std(),20)

    def test_effect_parameters_and_media_type_are_validated(self):
        for effects in [{'key_color':'red;movie=secret'},{'width':0},{'x':float('nan')},{'region':'image'}, {'overlay_id':'../../secret'}]:
            with self.assertRaises(ValueError):studio.Scene(effects=effects)
        p=studio.Project(resolution='720p',captions=False,narration=False,scenes=[studio.Scene(asset_id=self.image_meta['id'],end=.2,
            effects={'region':'image','overlay_id':self.music_meta['id']})])
        with self.assertRaisesRegex(ValueError,'must be images'):studio.render(self.job(p),p)

    def test_effect_motion_path_survives_natural_language_trim(self):
        from edit_agent import slice_timeline
        p=studio.Project(scenes=[studio.Scene(end=10,effects={'region':'blur','x':0,'end_x':1,'y':0,'end_y':1})])
        cut=slice_timeline(p,2,8)[0]
        self.assertAlmostEqual(cut.effects.x,.2)
        self.assertAlmostEqual(cut.effects.end_x,.8)

    def test_specialist_endpoint_validates_and_dispatches_current_project(self):
        p = studio.Project(scenes=[studio.Scene(text='A quiet forest.')])
        with patch.object(studio,'queue',return_value={'id':'a'*32}) as queue:
            response = self.client.post('/api/studio/agent-run',json={'project':p.model_dump(),'agent':'seo_metadata'})
            self.assertEqual(response.status_code,200)
            self.assertEqual(queue.call_args.args[0],'agent')
            self.assertEqual(queue.call_args.args[1].id,p.id)
            invalid = self.client.post('/api/studio/agent-run',json={'project':p.model_dump(),'agent':'lip_sync'})
            self.assertEqual(invalid.status_code,422)
            empty = self.client.post('/api/studio/agent-run',json={'project':studio.Project().model_dump(),'agent':'seo_metadata'})
            self.assertEqual(empty.status_code,400)
            self.assertEqual(queue.call_count,1)

    def test_short_transcript_scene_is_not_dropped(self):
        result = main.detect_scenes(main.SceneDetectionRequest(transcript_segments=[{'start':0,'end':1,'text':'Hello'}]))
        self.assertEqual(len(result['scenes']),1)

    def test_jump_cut_duration_uses_source_span(self):
        result=main.jump_cut(main.JumpCutRequest(segments=[{'start':0,'end':2},{'start':10,'end':12}],padding_seconds=0))
        self.assertEqual(result['original_duration'],12)
        self.assertEqual(result['new_duration'],4)
        self.assertEqual(result['time_saved_seconds'],8)
        self.assertEqual(result['status'],'command_ready')

    def test_speech_transcription_preserves_source_and_can_remove_gaps(self):
        from types import SimpleNamespace
        p=studio.Project(scenes=[studio.Scene(asset_id=self.video_meta['id'],media_kind='video',start=0,end=3)])
        model=SimpleNamespace(transcribe=lambda *a,**kw:([SimpleNamespace(start=.2,end=1,text='First'),SimpleNamespace(start=2,end=2.7,text='Second')],None))
        with patch.dict(studio.ENV,{'get_whisper_model':lambda:model}):
            keep=studio.transcribe(self.job(p),studio.TranscribeRequest(project=p.model_copy(deep=True),scene_id=p.scenes[0].id))
            cut=studio.transcribe(self.job(p),studio.TranscribeRequest(project=p.model_copy(deep=True),scene_id=p.scenes[0].id,remove_silence=True))
        self.assertEqual(keep['scenes'][0]['start'],0)
        self.assertEqual(keep['scenes'][-1]['end'],3)
        self.assertEqual(keep['scenes'][0]['end'],keep['scenes'][1]['start'])
        self.assertEqual(cut['scenes'][0]['end'],1)
        self.assertEqual(cut['scenes'][1]['start'],2)
        # Preserving footage must not stretch subtitles into the silent margins.
        kept=studio.Project.model_validate(keep)
        jid=self.job(kept)
        result=studio.render(jid,kept)
        srt=(self.root/'renders'/jid/'captions.srt').read_text('utf-8')
        self.assertIn('00:00:00,200 --> 00:00:01,000',srt)
        self.assertIn('00:00:02,000 --> 00:00:02,700',srt)
        # Trimming to silence must produce no caption, not an estimated fallback.
        silent=kept.model_copy(deep=True)
        silent.scenes=silent.scenes[:1]
        silent.scenes[0].start=1.1
        silent.scenes[0].end=1.8
        jid=self.job(silent)
        studio.render(jid,silent)
        self.assertEqual((self.root/'renders'/jid/'captions.srt').read_text('utf-8'),'')
        # Speed/trim changes transform source speech boundaries.
        kept.scenes=kept.scenes[:1]
        kept.scenes[0].start=.1
        kept.scenes[0].speed=2
        jid=self.job(kept)
        studio.render(jid,kept)
        self.assertIn('00:00:00,050 --> 00:00:00,450',
            (self.root/'renders'/jid/'captions.srt').read_text('utf-8'))


    def test_optimizer_rejects_changed_scene_ids_without_saving(self):
        p=studio.Project(scenes=[studio.Scene(text='Keep the original wording')])
        with patch.object(studio,'chat',return_value={'scenes':[{'id':'wrong','text':'Unexpected'}]}):
            with self.assertRaisesRegex(ValueError,'scene IDs'):
                studio.polish(self.job(p),p)
        self.assertFalse(studio.path_for('projects',p.id).exists())

    def test_bridge_voice_uses_preferences_and_validates_audio(self):
        from types import SimpleNamespace
        encoded = self.root/'voice-fixture.mp3'
        studio.run([self.ff,'-y','-v','error','-i',str(self.music),str(encoded)])
        response = SimpleNamespace(status_code=200,headers={'content-type':'audio/mpeg'},content=encoded.read_bytes(),raise_for_status=lambda:None)
        cfg=studio.Settings(voice_engine='bridge',image_url='https://example.test',bridge_token='test-token',voice_gender='female',speech_rate=-10)
        with patch.object(studio,'settings',return_value=cfg),patch.object(studio.requests,'post',return_value=response) as post:
            self.assertTrue(studio.voice_asset('नमस्ते','hi',self.root/'voice-output.mp3'))
            self.assertEqual(post.call_args.kwargs['json'],{'text':'नमस्ते','language':'hi','gender':'female','rate':-10})
            self.assertEqual(post.call_args.kwargs['headers']['Authorization'],'Bearer test-token')

    def test_bridge_bad_audio_never_becomes_cached_speech(self):
        from types import SimpleNamespace
        response=SimpleNamespace(status_code=200,headers={'content-type':'audio/mpeg'},content=b'not audio',raise_for_status=lambda:None)
        output=self.root/'invalid-voice.mp3'
        with patch.object(studio,'settings',return_value=studio.Settings(voice_engine='bridge',image_url='https://example.test')),patch.object(studio.requests,'post',return_value=response):
            with self.assertRaisesRegex(RuntimeError,'decoded'):
                studio.voice_asset('Hello','en',output)
        self.assertFalse(output.exists())

    def test_high_detail_image_request_and_invalid_old_voice_bridge(self):
        from types import SimpleNamespace
        response=SimpleNamespace(status_code=200,headers={'content-type':'image/png'},content=self.image.read_bytes(),raise_for_status=lambda:None)
        cfg=studio.Settings(voice_engine='bridge',image_url='https://example.test',image_quality='high')
        with patch.object(studio,'settings',return_value=cfg),patch.object(studio.requests,'post',return_value=response) as post:
            studio.image_asset('Sunlit mountain','cinematic','9:16',self.root/'generated.png')
            payload=post.call_args.kwargs['json']
            self.assertEqual((payload['width'],payload['height'],payload['steps']),(768,1344,40))
            response.status_code=404
            with self.assertRaisesRegex(RuntimeError,'updated SmartEdit notebook'):
                studio.voice_asset('Hello','en',self.root/'missing.mp3')

    def test_motion_storyboard_requires_short_topic_shots_and_allows_no_narration(self):
        p = studio.Project(prompt='A robot exploring an underwater city', generation_mode='motion',
                           narration=False, captions=False, duration=10)
        shots = [{'text': '', 'visual_prompt': 'A silver robot swims toward submerged towers, camera follows'},
                 {'text': '', 'visual_prompt': 'The same silver robot opens a glowing door, close-up'}]
        with patch.object(studio, 'chat', side_effect=self.agent_reply({'title': 'Underwater city', 'scenes': shots})) as chat:
            result = studio.plan(self.job(p), p)
        self.assertEqual([s['end'] for s in result['scenes']], [5, 5])
        self.assertEqual(result['generation_mode'], 'motion')
        self.assertEqual(result['scenes'][0]['text'], '')
        self.assertIn('camera movement', chat.call_args_list[0].args[0])
        self.assertEqual(chat.call_count,2)
        self.assertIn('agent_workflow',result['production_notes'])
        with patch.object(studio, 'chat', return_value={'scenes': shots[:1]}):
            with self.assertRaisesRegex(ValueError, 'exactly 2'):
                studio.plan(self.job(p), p)
        with self.assertRaises(ValueError):
            studio.Project(generation_mode='motion', duration=90)

    def test_avatar_storyboard_preserves_slide_fields(self):
        p=studio.Project(prompt='Explain solar power',generation_mode='avatar',language='hi',duration=20,
                         presenter_layout='pip-left',presenter_character='maya',presenter_theme='teal')
        with patch.object(studio,'chat',side_effect=self.agent_reply({'title':'सौर ऊर्जा','scenes':[
            {'text':'सूरज से बिजली बनती है।','visual_prompt':'Solar panels in sunlight',
             'slide_title':'सौर ऊर्जा','slide_points':['सूरज की रोशनी','बिजली का उत्पादन']}]})) as chat:
            result=studio.plan(self.job(p),p)
        self.assertIn('presenter-led video following the requested purpose',chat.call_args_list[0].args[0])
        self.assertIn('app renders the presenter',chat.call_args_list[0].args[0])
        self.assertEqual(result['scenes'][0]['slide_title'],'सौर ऊर्जा')
        self.assertEqual(result['scenes'][0]['slide_points'],['सूरज की रोशनी','बिजली का उत्पादन'])
        self.assertEqual(result['presenter_layout'],'pip-left')
        with self.assertRaises(ValueError):
            studio.Project(generation_mode='avatar',presenter_layout='bad-filter')

    def test_avatar_real_export_layouts_and_voice_reactivity(self):
        from avatar_presenter import speech_levels
        import shutil
        from unittest.mock import Mock
        def voice(text, language, output):
            studio.run([self.ff,'-y','-v','error','-i',str(self.music),str(output)])
            return True
        for ratio,layout in [(ratio,layout) for ratio in ('16:9','9:16','1:1')
                             for layout in ('side','pip-right','pip-left')]:
            p=studio.Project(generation_mode='avatar',resolution='720p',aspect_ratio=ratio,
                             presenter_layout=layout,presenter_character='maya',presenter_theme='teal',captions=True,
                             scenes=[studio.Scene(asset_id=self.image_meta['id'],end=1,text='सूरज से बिजली बनती है।',
                                                  slide_title='सौर ऊर्जा',slide_points=['Clean energy','Sunlight becomes power'])])
            with patch.object(studio,'voice_asset',side_effect=voice),patch.object(studio,'motion_asset') as motion:
                jid=self.job(p);studio.worker(jid,studio.render,p)
            self.assertEqual(studio.JOBS[jid]['status'],'completed',studio.JOBS[jid].get('error'))
            motion.assert_not_called()
            result=studio.JOBS[jid]['result']
            self.assertAlmostEqual(result['duration'],2,delta=.15)
            overlay=(self.root/'renders'/jid/'presenter_000.ass').read_text('utf-8-sig')
            self.assertIn('सौर ऊर्जा',overlay)
            self.assertIn('Sunlight becomes power',overlay)
            self.assertGreater(overlay.count('Dialogue: 8'),30)
            self.assertEqual('\\clip(' in overlay, layout != 'side')
            # Make an inspectable frame without image-library dependencies.
            studio.run([self.ff,'-y','-v','error','-ss','0.5','-i',str(self.root/'renders'/jid/'final.mp4'),
                        '-frames:v','1',str(self.root/f'avatar-{layout}.png')])
            verify=self.original_data/'verification';verify.mkdir(exist_ok=True)
            shutil.copyfile(self.root/f'avatar-{layout}.png',verify/f'avatar-{ratio.replace(":","-")}-{layout}.png')
            if layout != 'side':
                # Even a mismatched source ratio must fill the output edges
                # with image colour, not the old dark slide-box padding.
                info=studio.probe(self.root/'renders'/jid/'final.mp4')
                stream=next(s for s in info['streams'] if s['codec_type']=='video')
                pixels=studio.run([self.ff,'-v','error','-ss','0.5','-i',str(self.root/'renders'/jid/'final.mp4'),
                    '-frames:v','1','-pix_fmt','rgb24','-f','rawvideo','-'])
                for x in (8,stream['width']-9):
                    pos=(stream['height']//2*stream['width']+x)*3
                    r,g,b=pixels[pos:pos+3]
                    self.assertGreater(g,80)
                    self.assertGreater(b,80)
                    self.assertLess(r,30)
        levels=speech_levels(self.ff,self.music,3,1,studio.run)
        self.assertGreater(max(levels[:12]),.1)
        self.assertEqual(levels[-1],0)
        no_decode=Mock(side_effect=AssertionError('Muted avatar must not decode audio'))
        self.assertEqual(max(speech_levels(self.ff,self.music,1,1,no_decode,enabled=False)),0)

    def test_avatar_regions_never_overlap_or_clip(self):
        from avatar_presenter import geometry, caption_box
        def overlaps(a,b):
            return a[0] < b[0]+b[2] and b[0] < a[0]+a[2] and a[1] < b[1]+b[3] and b[1] < a[1]+a[3]
        for w,h in [(1280,720),(720,1280),(720,720),(1920,1080),(1080,1920),(1080,1080)]:
            for layout in ('side','pip-left','pip-right'):
                with self.subTest(size=(w,h),layout=layout):
                    visual,(x,y,aw),text=geometry(w,h,layout)
                    # Include the complete vector shape, not just its face/torso.
                    avatar=(x,y,aw,aw*430/320 if layout=='side' else aw)
                    if layout != 'side':
                        self.assertLessEqual(aw,w*.22)
                        self.assertLessEqual(aw,h*.24)
                        self.assertEqual(visual,(0,0,w,h))
                        self.assertAlmostEqual(h-y-aw,round(min(w,h)*.035))
                    # PiP intentionally overlays its full-frame background;
                    # only foreground controls must remain mutually separate.
                    regions=([visual] if layout=='side' else [])+[avatar,text,caption_box(w,h,layout)]
                    for i,a in enumerate(regions):
                        self.assertGreaterEqual(min(a),0)
                        self.assertLessEqual(a[0]+a[2],w+.01)
                        self.assertLessEqual(a[1]+a[3],h+.01)
                        for b in regions[i+1:]:
                            self.assertFalse(overlaps(a,b),(a,b))
                    self.assertTrue(all(v%2==0 for v in visual))

    def test_avatar_captions_fit_reserved_band(self):
        for w,h in [(1280,720),(720,1280),(720,720)]:
            studio.caption_files(self.root,[{'start':0,'end':4,
                'text':'Understanding internationalization demonstrates extraordinary computational capabilities clearly'}],w,h,'',presenter=True)
            ass=(self.root/'captions.ass').read_text('utf-8-sig')
            self.assertIn('\\q2',ass)
            self.assertIn(f',{round(w*.05)},{round(w*.05)},{round(h*.025)},1',ass)
            self.assertNotIn('\\fs',(self.root/'captions.srt').read_text('utf-8'))

    def test_bottom_pip_caption_margins_follow_corner(self):
        from avatar_presenter import caption_box
        for w,h in [(1280,720),(720,1280),(720,720),(1920,1080)]:
            for layout in ('pip-left','pip-right'):
                studio.caption_files(self.root,[{'start':0,'end':3,'text':'A longer subtitle must never overlap the illustrated presenter face.'}],
                    w,h,'',presenter=True,presenter_layout=layout)
                ass=(self.root/'captions.ass').read_text('utf-8-sig')
                x,_,cw,_=caption_box(w,h,layout)
                self.assertIn(f',{x},{w-x-cw},{round(h*.025)},1',ass)
                if layout=='pip-right':
                    self.assertGreater(w-x-cw,x)
                else:
                    self.assertGreater(x,w-x-cw)

    def test_real_motion_export_uses_video_and_cache_without_images(self):
        import shutil
        p = studio.Project(prompt='Robot city', generation_mode='motion', narration=False, captions=False,
                           resolution='720p', duration=10,
                           scenes=[studio.Scene(visual_prompt='Robot walks through a city', end=2)])
        def video(jid, prompt, style, ratio, path, *options):
            shutil.copyfile(self.video, path)
        with patch.object(studio, 'motion_service'), patch.object(studio, 'motion_asset', side_effect=video) as motion, \
                patch.object(studio, 'image_asset', side_effect=AssertionError('Image fallback used')), \
                patch.object(studio, 'voice_asset', side_effect=AssertionError('Narration was disabled')):
            jid = self.job(p)
            studio.worker(jid, studio.render, p)
            self.assertEqual(studio.JOBS[jid]['status'], 'completed', studio.JOBS[jid].get('error'))
            self.assertAlmostEqual(studio.JOBS[jid]['result']['duration'], 2, delta=.1)
            again = self.job(p)
            studio.worker(again, studio.render, p)
            self.assertEqual(studio.JOBS[again]['status'], 'completed', studio.JOBS[again].get('error'))
            self.assertEqual(motion.call_count, 1)
        info = studio.probe(self.root/'renders'/jid/'final.mp4')
        self.assertEqual({s['codec_type'] for s in info['streams']}, {'video', 'audio'})
        self.assertEqual(self.client.get('/api/studio/jobs/'+jid+'/file/video').status_code, 200)
        metadata = json.loads((self.root/'renders'/jid/'metadata.json').read_text('utf-8'))
        self.assertIn('balanced', metadata['visual_generation'])

    def test_avatar_reuses_generated_media_and_does_not_overlay_baked_clips(self):
        import shutil, hashlib, speech_timing
        p=studio.Project(generation_mode='avatar',resolution='720p',captions=False,scenes=[
            studio.Scene(visual_prompt='Solar panels in sunlight',text='Clean energy',end=1,slide_title='Solar power')])
        def image(prompt,style,ratio,output):
            shutil.copyfile(self.image,output)
        def voice(text,language,output):
            studio.run([self.ff,'-y','-v','error','-i',str(self.music),str(output)])
            speech_timing.sidecar(output).write_text(json.dumps({'text':text,'duration':2,
                'words':[{'text':text,'start':.1,'end':1.8}],
                'audio_sha256':hashlib.sha256(output.read_bytes()).hexdigest()}),encoding='utf-8')
            return True
        with patch.object(studio,'image_asset',side_effect=image) as images, patch.object(studio,'voice_asset',side_effect=voice) as voices:
            for layout in ['side','pip-right']:
                p.presenter_layout=layout
                jid=self.job(p);studio.worker(jid,studio.render,p)
                self.assertEqual(studio.JOBS[jid]['status'],'completed',studio.JOBS[jid].get('error'))
            self.assertEqual(images.call_count,1)
            self.assertEqual(voices.call_count,1)
            response=self.client.get('/api/studio/jobs/'+jid+'/file/video')
            self.assertEqual(response.status_code,200)
            rendered=studio.JOBS[jid]['result']['scene_assets'][0]
            p.scenes=[studio.Scene(asset_id=rendered['asset_id'],media_kind='video',end=rendered['duration'])]
            baked=self.job(p);studio.worker(baked,studio.render,p)
            self.assertEqual(studio.JOBS[baked]['status'],'completed',studio.JOBS[baked].get('error'))
            self.assertFalse((self.root/'renders'/baked/'presenter_000.ass').exists())
            self.assertEqual(images.call_count,1)
            self.assertEqual(voices.call_count,1)

    def test_motion_provider_failure_never_falls_back_to_images(self):
        p = studio.Project(generation_mode='motion', scenes=[studio.Scene(visual_prompt='A bird flies over mountains')])
        jid = self.job(p)
        with patch.object(studio, 'motion_service'), \
                patch.object(studio, 'motion_asset', side_effect=RuntimeError('GPU memory exhausted')), \
                patch.object(studio, 'image_asset') as image:
            studio.worker(jid, studio.render, p)
        self.assertEqual(studio.JOBS[jid]['status'], 'failed')
        self.assertIn('GPU memory exhausted', studio.JOBS[jid]['error'])
        image.assert_not_called()
        self.assertEqual(self.client.get('/api/studio/jobs/'+jid+'/file/video').status_code, 409)

    def test_hybrid_twenty_second_export_routes_one_motion_and_three_images(self):
        import shutil
        p = studio.Project(generation_mode='hybrid', duration=20, narration=False, captions=False,
            resolution='720p', scenes=[studio.Scene(visual_prompt=f'Hybrid shot {i}',end=5) for i in range(4)])
        def video(jid,prompt,style,ratio,path,*options): shutil.copyfile(self.video,path)
        def image(prompt,style,ratio,path): shutil.copyfile(self.image,path)
        with patch.object(studio,'motion_service'), patch.object(studio,'motion_asset',side_effect=video) as motion, patch.object(studio,'image_asset',side_effect=image) as images:
            jid=self.job(p);studio.worker(jid,studio.render,p)
            self.assertEqual(studio.JOBS[jid]['status'],'completed',studio.JOBS[jid].get('error'))
            self.assertAlmostEqual(studio.JOBS[jid]['result']['duration'],20,delta=.1)
            self.assertEqual(motion.call_count,1);self.assertEqual(images.call_count,3)
            self.assertEqual(motion.call_args.args[5],'balanced')
            self.assertEqual(motion.call_args.args[-1],[])
        metadata=json.loads((self.root/'renders'/jid/'metadata.json').read_text('utf-8'))
        self.assertIn('Hybrid',metadata['visual_generation'])

    def test_motion_cache_separates_speed_presets(self):
        import shutil
        p=studio.Project(generation_mode='motion',motion_preset='preview',narration=False,captions=False,
            resolution='720p',scenes=[studio.Scene(visual_prompt='Cache speed preset fixture',end=2)])
        def video(jid,prompt,style,ratio,path,*options): shutil.copyfile(self.video,path)
        with patch.object(studio,'motion_service'),patch.object(studio,'motion_asset',side_effect=video) as motion:
            for preset in ['preview','balanced','balanced']:
                p.motion_preset=preset;jid=self.job(p);studio.worker(jid,studio.render,p)
                self.assertEqual(studio.JOBS[jid]['status'],'completed',studio.JOBS[jid].get('error'))
            self.assertEqual(motion.call_count,2)

    def test_motion_narration_uses_measured_audio_and_mute_skips_voice(self):
        import shutil
        p = studio.Project(generation_mode='motion', resolution='720p', captions=False,
                           scenes=[studio.Scene(visual_prompt='A fox runs across a field', text='A fox runs', end=1)])
        def video(jid, prompt, style, ratio, output, *options):
            shutil.copyfile(self.video, output)
        def voice(text, language, output):
            studio.run([self.ff, '-y', '-v', 'error', '-i', str(self.music), str(output)])
            return True
        with patch.object(studio, 'motion_service'), patch.object(studio, 'motion_asset', side_effect=video), \
                patch.object(studio, 'voice_asset', side_effect=voice) as speech:
            jid = self.job(p)
            studio.worker(jid, studio.render, p)
            self.assertEqual(studio.JOBS[jid]['status'], 'completed', studio.JOBS[jid].get('error'))
            self.assertAlmostEqual(studio.JOBS[jid]['result']['duration'], 2, delta=.15)
            self.assertEqual(speech.call_count, 1)
            p.scenes[0].mute = True
            muted = self.job(p)
            studio.worker(muted, studio.render, p)
            self.assertEqual(studio.JOBS[muted]['status'], 'completed', studio.JOBS[muted].get('error'))
            self.assertAlmostEqual(studio.JOBS[muted]['result']['duration'], 1, delta=.1)
            self.assertEqual(speech.call_count, 1)

    def test_later_long_narration_stops_before_any_motion_generation(self):
        p = studio.Project(generation_mode='motion', scenes=[
            studio.Scene(visual_prompt='First shot', text='Short narration', end=5),
            studio.Scene(visual_prompt='Second shot', text='Long narration', end=5)])
        def voice(text, language, output):
            studio.run([self.ff, '-y', '-v', 'error', '-f', 'lavfi', '-i',
                        'sine=frequency=220:duration=' + ('12' if text.startswith('Long') else '2'), str(output)])
            return True
        with patch.object(studio, 'voice_asset', side_effect=voice), \
                patch.object(studio, 'motion_asset') as motion, patch.object(studio, 'motion_service') as service:
            jid = self.job(p)
            studio.worker(jid, studio.render, p)
            self.assertEqual(studio.JOBS[jid]['status'], 'failed')
            self.assertIn('Scene 2/2', studio.JOBS[jid]['error'])
            self.assertIn('No new motion was generated', studio.JOBS[jid]['error'])
            motion.assert_not_called()
            service.assert_not_called()

    def test_motion_bridge_polling_validates_video_and_cancels_corrupt_output(self):
        from types import SimpleNamespace
        cfg = studio.Settings(voice_engine='bridge',image_url='https://example.test', bridge_token='test-token')
        def response(data=None, content=b''):
            return SimpleNamespace(headers={'content-type':'video/mp4'}, content=content,
                                   raise_for_status=lambda: None, json=lambda: data)
        p = studio.Project(generation_mode='motion')
        jid = self.job(p)
        output = self.root/'motion-download.mp4'
        statuses = [response({'status':'running','message':'Step 1/30'}),
                    response({'status':'completed','message':'Done'}), response(content=self.video.read_bytes())]
        with patch.object(studio, 'settings', return_value=cfg), \
                patch.object(studio.requests, 'post', return_value=response()) as post, \
                patch.object(studio.requests, 'get', side_effect=statuses), patch.object(studio.time, 'sleep'):
            reference = self.root/'motion-reference.png'
            reference.write_bytes(b'generated-scene-reference')
            studio.motion_asset(jid, 'A moving robot', 'cinematic', '9:16', output, source_image=reference)
        self.assertTrue(output.exists())
        self.assertEqual(post.call_args.kwargs['json']['aspect_ratio'], '9:16')
        self.assertEqual(base64.b64decode(post.call_args.kwargs['json']['source_image']), b'generated-scene-reference')
        self.assertEqual(post.call_args.kwargs['headers']['Authorization'], 'Bearer test-token')
        invalid = self.root/'corrupt-motion.mp4'
        with patch.object(studio, 'settings', return_value=cfg), \
                patch.object(studio.requests, 'post', return_value=response()) as post, \
                patch.object(studio.requests, 'get', side_effect=[response({'status':'completed'}), response(content=b'bad video')]):
            with self.assertRaises(RuntimeError):
                studio.motion_asset(jid, 'A robot', 'cinematic', '16:9', invalid)
        self.assertFalse(invalid.exists())
        self.assertFalse(invalid.with_suffix('.partial.mp4').exists())
        self.assertTrue(post.call_args.args[0].endswith('/cancel'))

    def test_motion_cancellation_reaches_colab(self):
        from types import SimpleNamespace
        p = studio.Project(generation_mode='motion')
        jid = self.job(p)
        studio.JOBS[jid]['cancel_requested'] = True
        response = SimpleNamespace(raise_for_status=lambda: None)
        with patch.object(studio, 'settings', return_value=studio.Settings(voice_engine='bridge',image_url='https://example.test')), \
                patch.object(studio.requests, 'post', return_value=response) as post, \
                patch.object(studio.requests, 'get') as get:
            with self.assertRaisesRegex(RuntimeError, 'Cancelled'):
                studio.motion_asset(jid, 'A robot', 'cinematic', '16:9', self.root/'cancelled-motion.mp4')
        get.assert_not_called()
        self.assertTrue(post.call_args.args[0].endswith('/cancel'))

    def test_preview_proxy_and_range_requests_for_non_browser_video(self):
        original = self.root/'lossless.mkv'
        studio.run([self.ff,'-y','-v','error','-i',str(self.video),'-t','1','-c:v','ffv1','-c:a','pcm_s16le',str(original)])
        media = self.upload(original)
        self.assertEqual(self.client.get('/api/studio/assets/'+media['id']+'/metadata').json()['kind'],'video')
        url='/api/studio/assets/'+media['id']+'/preview'
        response=self.client.get(url)
        self.assertEqual(response.status_code,200,response.text[:100] if response.status_code!=200 else '')
        preview=studio.path_for('assets',media['id'],'.preview.mp4')
        info=studio.probe(preview)
        self.assertEqual(next(s for s in info['streams'] if s['codec_type']=='video')['codec_name'],'h264')
        self.assertTrue(original.exists())
        modified=preview.stat().st_mtime_ns
        self.assertEqual(self.client.get(url,headers={'Range':'bytes=0-99'}).status_code,206)
        self.assertEqual(preview.stat().st_mtime_ns,modified)

    def test_crop_mirror_and_volume_are_in_encoded_output(self):
        import array
        import math
        source=self.root/'two-colors.mp4'
        studio.run([self.ff,'-y','-v','error','-f','lavfi','-i','color=red:s=320x180:r=30',
                    '-f','lavfi','-i','sine=frequency=440:sample_rate=48000',
                    '-vf','drawbox=x=160:y=0:w=160:h=180:color=blue:t=fill',
                    '-t','1','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac',str(source)])
        media=self.upload(source)
        p=studio.Project(aspect_ratio='1:1',resolution='720p',captions=False,
                         scenes=[studio.Scene(asset_id=media['id'],media_kind='video',end=1,fit='cover',flip=True)])
        rms=[]
        for volume in (1,.25):
            p.scenes[0].volume=volume
            jid=self.job(p);studio.worker(jid,studio.render,p)
            self.assertEqual(studio.JOBS[jid]['status'],'completed',studio.JOBS[jid].get('error'))
            output=self.root/'renders'/jid/'final.mp4'
            pixels=studio.run([self.ff,'-v','error','-ss','0.2','-i',str(output),'-frames:v','1','-pix_fmt','rgb24','-f','rawvideo','-'])
            left=(360*720+150)*3;right=(360*720+570)*3
            self.assertGreater(pixels[left+2],pixels[left]+100,'Mirrored left side should be blue')
            self.assertGreater(pixels[right],pixels[right+2]+100,'Mirrored right side should be red')
            samples=array.array('f',studio.run([self.ff,'-v','error','-i',str(output),'-map','0:a','-ac','1','-f','f32le','-']))
            rms.append(math.sqrt(sum(x*x for x in samples)/len(samples)))
        self.assertAlmostEqual(rms[1]/rms[0],.25,delta=.04)

    def test_scene_properties_validate_volume_and_fit(self):
        for value in [-1,1.1,float('nan')]:
            with self.assertRaises(ValueError): studio.Scene(volume=value)
        with self.assertRaises(ValueError): studio.Scene(fit='unsupported')


if __name__=='__main__':
    unittest.main(verbosity=2)
