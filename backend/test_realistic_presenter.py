"""Real FFmpeg integration, with only the unavailable MuseTalk inference mocked."""
import base64
import importlib.util
import json
from pathlib import Path
import shutil
import unittest
from unittest.mock import patch
from types import SimpleNamespace
import studio
import realistic_presenter as presenter
import test_studio as fixtures


class PresenterTests(unittest.TestCase):
    def test_notebook_plotting_failure_gives_actionable_safe_message(self):
        response = SimpleNamespace(raise_for_status=lambda:None,
            json=lambda:{'presenter_available':False,'presenter_setup_error':
                         "ValueError: module://matplotlib_inline.backend_inline; private-detail"})
        with patch.object(studio,'settings',return_value=studio.Settings(image_url='https://example.test')), \
             patch.object(studio.requests,'get',return_value=response):
            state=presenter.readiness(studio)
        self.assertFalse(state['available'])
        self.assertIn('plotting setting',state['message'])
        self.assertIn('updated SmartEdit notebook',state['message'])
        self.assertNotIn('private-detail',state['message'])

    setUpClass = classmethod(fixtures.StudioTests.setUpClass.__func__)
    tearDownClass = classmethod(fixtures.StudioTests.tearDownClass.__func__)
    upload = classmethod(fixtures.StudioTests.upload.__func__)
    job = fixtures.StudioTests.job
    setUp = fixtures.StudioTests.setUp
    agent_reply = staticmethod(fixtures.StudioTests.agent_reply)

    def project(self, **kw):
        return studio.Project(generation_mode='avatar',presenter_kind='realistic',
            presenter_asset_id=self.video_meta['id'],resolution='720p',captions=True,
            scenes=[studio.Scene(asset_id=self.image_meta['id'],text='Learn from examples.',slide_title='Learning',slide_points=['Compare examples','Find a pattern'],end=3)],**kw)

    def test_missing_setup_and_silent_voice_stop_before_images(self):
        p=self.project()
        with patch.object(presenter,'readiness',return_value={'available':False,'message':'Enable realistic presenter'}),patch.object(studio,'scene_voice') as voice,patch.object(studio,'image_asset') as image:
            with self.assertRaisesRegex(ValueError,'Enable realistic'):studio.render(self.job(p),p)
        voice.assert_not_called();image.assert_not_called()
        with patch.object(presenter,'readiness',return_value={'available':True}),patch.object(studio,'scene_voice',return_value=(None,0)),patch.object(presenter,'cached_clip') as face:
            with self.assertRaisesRegex(ValueError,'audible narration'):studio.render(self.job(p),p)
        face.assert_not_called()
        p.presenter_asset_id=''
        self.assertIsNone(presenter.validate(p,studio,False))
        p.presenter_asset_id=self.image_meta['id']
        with self.assertRaisesRegex(ValueError,'video between'):presenter.validate(p,studio,False)

    def test_composition_contains_presenter_and_voice_in_all_layouts(self):
        red=self.root/'red-presenter.mp4'
        studio.run([self.ff,'-y','-v','error','-f','lavfi','-i','color=red:s=320x180:r=25','-t','3','-c:v','libx264','-pix_fmt','yuv420p',str(red)])
        from avatar_presenter import geometry
        for ratio in ('16:9','9:16','1:1'):
            for layout in ('side','pip-left','pip-right'):
                with self.subTest(ratio=ratio,layout=layout):
                    p=self.project(aspect_ratio=ratio,presenter_layout=layout)
                    jid=self.job(p)
                    with patch.object(presenter,'readiness',return_value={'available':True}),patch.object(presenter,'cached_clip',return_value=red),patch.object(studio,'scene_voice',return_value=(self.music,2)):
                        result=studio.render(jid,p)
                    self.assertAlmostEqual(result['duration'],3,places=2)
                    file=self.root/'renders'/jid/'final.mp4'
                    self.assertTrue(studio.audible(file))
                    info=studio.probe(file);v=next(s for s in info['streams'] if s['codec_type']=='video')
                    w,h=v['width'],v['height'];_,(x,y,aw),_=geometry(w,h,layout)
                    ah=aw*(430/320 if layout=='side' else 1)
                    pixels=studio.run([self.ff,'-v','error','-ss','1','-i',str(file),'-frames:v','1','-pix_fmt','rgb24','-f','rawvideo','-'])
                    pos=(int(y+ah/2)*w+int(x+aw/2))*3
                    self.assertGreater(pixels[pos],pixels[pos+1]+100,'Presenter missing or covered')
                    ass=(self.root/'renders'/jid/'presenter_000.ass').read_text(encoding='utf-8-sig')
                    self.assertNotIn('574033',ass,'Illustrated face must not remain under real presenter')
                    self.assertIn('Learning',ass)

    def test_cache_changes_with_voice_duration_speed_or_presenter(self):
        p=self.project();cache=self.root/'presenter-cache';cache.mkdir(exist_ok=True)
        def write(jid,source,voice,seconds,speed,output,studio):shutil.copyfile(self.video,output)
        with patch.object(presenter,'generate',side_effect=write) as generate:
            a=presenter.cached_clip(self.job(p),p,self.music,3,1,cache,studio)
            self.assertEqual(a,presenter.cached_clip(self.job(p),p,self.music,3,1,cache,studio))
            b=presenter.cached_clip(self.job(p),p,self.music,4,1,cache,studio)
            c=presenter.cached_clip(self.job(p),p,self.music,3,1.05,cache,studio)
        self.assertEqual(generate.call_count,3);self.assertNotEqual(a,b);self.assertNotEqual(a,c)

    def test_remote_result_is_validated_and_cancelled_on_bad_output(self):
        p=self.project();result=self.root/'bad-presenter.mp4'
        def response(data=None,content=b'',mime='application/json'):
            return SimpleNamespace(json=lambda:data,content=content,headers={'content-type':mime},raise_for_status=lambda:None)
        with patch.object(studio,'settings',return_value=studio.Settings(image_url='https://example.test')),patch.object(studio.requests,'post',return_value=response()) as post,patch.object(studio.requests,'get',side_effect=[response({'status':'completed'}),response(content=b'invalid',mime='video/mp4')]):
            with self.assertRaises(Exception):presenter.generate(self.job(p),self.video,self.music,3,1,result,studio)
        self.assertFalse(result.exists());self.assertTrue(post.call_args.args[0].endswith('/cancel'))
        self.assertFalse(list(self.root.glob('presenter-*/result.mp4')))

    def test_real_client_normalizes_audio_and_accepts_valid_response(self):
        p=self.project();out=self.root/'good-presenter.mp4'
        response=lambda data=None,content=b'',mime='application/json':SimpleNamespace(json=lambda:data,content=content,headers={'content-type':mime},raise_for_status=lambda:None)
        def submitted(url,**kwargs):
            payload=kwargs['json']; wav=self.root/'sent-voice.wav';wav.write_bytes(base64.b64decode(payload['audio']))
            self.assertAlmostEqual(float(studio.probe(wav)['format']['duration']),3,places=2)
            return response()
        with patch.object(studio,'settings',return_value=studio.Settings(image_url='https://example.test')),patch.object(studio.requests,'post',side_effect=submitted),patch.object(studio.requests,'get',side_effect=[response({'status':'completed'}),response(content=self.video.read_bytes(),mime='video/mp4')]):
            presenter.generate(self.job(p),self.video,self.music,3,1.05,out,studio)
        self.assertTrue(out.exists())

    def test_sample_endpoint_validation_and_download(self):
        p=self.project();p.presenter_asset_id='';p.narration=False
        response=self.client.post('/api/studio/presenter-test',json=p.model_dump())
        self.assertEqual(response.status_code,422)
        self.assertIn('narration',response.json()['detail'])
        p=self.project();p.presenter_asset_id=''
        with patch.object(studio,'queue',return_value={'id':'a'*32}) as queue:
            response=self.client.post('/api/studio/presenter-test',json=p.model_dump())
        self.assertEqual(response.status_code,200)
        self.assertEqual(queue.call_args.args[0],'presenter_test')
        self.assertIs(queue.call_args.args[2],studio.presenter_test)
        jid=self.job(p);studio.JOBS[jid]['kind']='presenter_test'
        def generate(job,source,voice,seconds,speed,output,context):
            self.assertEqual(seconds,5)
            studio.run([self.ff,'-y','-v','error','-stream_loop','-1','-i',str(source),
                '-i',str(voice),'-map','0:v','-map','1:a','-af','apad','-t','5',
                '-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac',str(output)])
        with patch.object(presenter,'readiness',return_value={'available':True}),patch.object(presenter,'generate',side_effect=generate),patch.object(studio,'scene_voice',return_value=(self.music,2)),patch.object(studio,'image_asset',side_effect=lambda prompt,style,ratio,out:shutil.copyfile(self.image,out)):
            result=studio.presenter_test(jid,p)
        studio.JOBS[jid].update(status='completed',result=result)
        self.assertEqual(self.client.get(result['video_url']).status_code,200)
        self.assertEqual(self.client.get(f'/api/studio/jobs/{jid}/file/metadata').status_code,404)
        self.assertAlmostEqual(float(studio.probe(self.root/'renders'/jid/'final.mp4')['format']['duration']),5,places=2)

    def test_automatic_face_reused_across_scenes_preview_and_test(self):
        p=self.project();p.presenter_asset_id=''
        cache=self.root/'automatic-avatar';cache.mkdir(exist_ok=True)
        def image(prompt,style,ratio,out):
            self.assertEqual(ratio,'1:1')
            self.assertIn('frontal view',prompt)
            self.assertIn('photorealistic',style)
            shutil.copyfile(self.image,out)
        with patch.object(studio,'image_asset',side_effect=image) as create:
            first=presenter.source_video(self.job(p),p,cache,studio)
            self.assertAlmostEqual(float(studio.probe(first)['format']['duration']),2,places=2)
            p.prompt='Explain machine learning';p.duration=20;p.aspect_ratio='9:16'
            self.assertEqual(first,presenter.source_video(self.job(p),p,cache,studio))
            p.id='a'*32;p.resolution='1080p'
            self.assertEqual(first,presenter.source_video(self.job(p),p,cache,studio))
            self.assertEqual(create.call_count,1)
            p.presenter_character='maya'
            other=presenter.source_video(self.job(p),p,cache,studio)
            self.assertNotEqual(first,other)
            self.assertEqual(create.call_count,2)
            p.presenter_theme='teal'
            self.assertNotEqual(other,presenter.source_video(self.job(p),p,cache,studio))

    def test_automatic_face_failure_does_not_cache_partial_or_call_lipsync(self):
        p=self.project();p.presenter_asset_id=''
        cache=self.root/'failed-avatar';cache.mkdir(exist_ok=True)
        def broken(prompt,style,ratio,out):
            out.write_bytes(b'partial')
            raise RuntimeError('Image service failed')
        with patch.object(studio,'image_asset',side_effect=broken),patch.object(presenter,'generate') as lip:
            with self.assertRaisesRegex(RuntimeError,'Image service failed'):
                presenter.cached_clip(self.job(p),p,self.music,3,1,cache,studio)
        lip.assert_not_called()
        self.assertEqual(list(cache.iterdir()),[])

    def test_topic_to_automatic_avatar_export_without_upload(self):
        p=studio.Project(prompt='Explain machine learning',generation_mode='avatar',
            presenter_kind='realistic',duration=20,duration_mode='target',resolution='720p',research=False)
        planned=p.model_copy(deep=True)
        planned.scenes=[studio.Scene(text='Machines learn patterns from examples.',visual_prompt='A computer compares example images.',end=10),
                        studio.Scene(text='Those patterns help predict new results.',visual_prompt='A computer recognizes a cat.',end=10)]
        seen_sources=[]
        def lip(job,source,voice,seconds,speed,output,context):
            seen_sources.append(source)
            studio.run([self.ff,'-y','-v','error','-stream_loop','-1','-i',str(source),
                '-i',str(voice),'-map','0:v','-map','1:a','-af','apad','-t',str(seconds),
                '-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac',str(output)])
        def image(prompt,style,ratio,out):shutil.copyfile(self.image,out)
        jid=self.job(p)
        with patch.object(presenter,'readiness',return_value={'available':True}),patch.object(studio,'plan',return_value=planned.model_dump()) as planner,patch.object(studio,'scene_voice',return_value=(self.music,2)),patch.object(studio,'image_asset',side_effect=image),patch.object(presenter,'generate',side_effect=lip):
            result=studio.generate(jid,p)
        planner.assert_called_once()
        self.assertEqual(result['project']['presenter_asset_id'],'')
        self.assertEqual(result['duration'],20)
        self.assertTrue(studio.audible(self.root/'renders'/jid/'final.mp4'))
        self.assertTrue(seen_sources)
        self.assertEqual(len(set(seen_sources)),1,'Face identity changed between scenes')

    def test_musetalk_payload_limits_and_source_embedding(self):
        root=Path(__file__).resolve().parents[1]
        spec=importlib.util.spec_from_file_location('support',root/'colab/musetalk_support.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        self.assertEqual(module.decode_media(base64.b64encode(b'ab').decode(),2),b'ab')
        for payload in ('','%%%','AAAAA',base64.b64encode(b'123').decode()):
            with self.assertRaises(ValueError):module.decode_media(payload,2)
        import ast
        tree=ast.parse((root/'colab/SmartEdit_Colab.py').read_text(encoding='utf-8'))
        embedded=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(getattr(t,'id',None)=='MUSETALK_SUPPORT_SOURCE' for t in n.targets))
        self.assertEqual(embedded,(root/'colab/musetalk_support.py').read_text(encoding='utf-8-sig'))

if __name__=='__main__':unittest.main(verbosity=2)
