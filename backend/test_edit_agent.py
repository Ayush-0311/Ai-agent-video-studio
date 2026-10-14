"""Edit planner transactions, source-time mapping, and actual rendered pixels."""
import json
from pathlib import Path
import tempfile
import unittest
import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient
import main
import studio


class EditAgentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='smartedit-agent-')
        cls.root=Path(cls.temp.name);cls.old_data=studio.DATA;studio.DATA=cls.root
        cls.client=TestClient(main.app)
        source=cls.root/'source.mp4'
        studio.run([main.FFMPEG_PATH,'-y','-v','error','-f','lavfi','-i','color=c=gray:size=160x90:rate=30','-t','4','-c:v','libx264','-pix_fmt','yuv420p',str(source)])
        with source.open('rb') as file:
            cls.media=cls.client.post('/api/studio/assets',files={'file':('source.mp4',file)}).json()

    @classmethod
    def tearDownClass(cls):
        studio.DATA=cls.old_data;cls.temp.cleanup()

    def project(self):
        return studio.Project(narration=False,captions=False,resolution='720p',scenes=[studio.Scene(asset_id=self.media['id'],media_kind='video',end=4)])

    def edit(self,command,project=None,**kwargs):
        return self.client.post('/api/studio/edit',json={'project':(project or self.project()).model_dump(),'command':command,**kwargs})

    def test_hinglish_compound_and_quoted_caption_are_offline(self):
        with patch.object(studio,'chat',side_effect=AssertionError('Local edit contacted AI')):
            response=self.edit('Reel banao, volume 50%, thoda bright karo, caption "Hello, World and नमस्ते" lagao')
        self.assertEqual(response.status_code,200,response.text)
        p=response.json()['project'];s=p['scenes'][0]
        self.assertEqual(p['aspect_ratio'],'9:16');self.assertEqual(s['volume'],.5)
        self.assertEqual(s['brightness'],.04);self.assertEqual(s['fit'],'cover')
        self.assertEqual(s['text'],'Hello, World and नमस्ते');self.assertTrue(p['captions'])

    def test_speed_aware_keep_range_spans_clips(self):
        p=self.project();p.scenes[0].speed=2
        p.scenes.append(studio.Scene(asset_id=self.media['id'],media_kind='video',start=1,end=4))
        response=self.edit('Keep 1 to 3 seconds',p)
        self.assertEqual(response.status_code,200,response.text)
        a,b=response.json()['project']['scenes']
        self.assertEqual((a['start'],a['end'],a['speed']),(2,4,2))
        self.assertEqual((b['start'],b['end']),(1,2))

    def test_fade_commands_are_local_and_validate(self):
        with patch.object(studio,'chat',side_effect=AssertionError('Local fade contacted model')):
            for command,expected in [('Fade through black','fade_black'),('Fade white','fade_white'),('Remove transitions','cut')]:
                response=self.edit(command)
                self.assertEqual(response.status_code,200,response.text)
                self.assertEqual(response.json()['project']['transition'],expected)

    def test_remove_middle_and_unique_split_ids(self):
        response=self.edit('Remove 1 to 3 seconds')
        a,b=response.json()['project']['scenes']
        self.assertEqual((a['start'],a['end'],b['start'],b['end']),(0,1,3,4))
        self.assertNotEqual(a['id'],b['id'])

    def test_selected_scope_and_explicit_clip(self):
        p=self.project();p.scenes.append(studio.Scene(asset_id=self.media['id'],media_kind='video',end=3))
        response=self.edit('Mute',p,scope='selected',selected_id=p.scenes[1].id)
        a,b=response.json()['project']['scenes'];self.assertFalse(a['mute']);self.assertTrue(b['mute'])
        response=self.edit('Clip 2 ko 1.5x speed do',p)
        self.assertEqual(response.json()['project']['scenes'][1]['speed'],1.5)
        self.assertEqual(self.edit('mute',p,scope='selected').status_code,422)

    def test_late_invalid_operation_does_not_write_project(self):
        p=self.project();self.client.put('/api/studio/projects/'+p.id,json=p.model_dump())
        saved=studio.path_for('projects',p.id).read_bytes()
        response=self.edit('Mute, keep 0 to 90 seconds',p)
        self.assertEqual(response.status_code,422)
        self.assertEqual(studio.path_for('projects',p.id).read_bytes(),saved)
        self.assertFalse(p.scenes[0].mute)

    def test_unsupported_part_blocks_whole_request(self):
        response=self.edit('Mute and replace background with a beach')
        self.assertEqual(response.json()['status'],'unsupported')
        self.assertNotIn('project',response.json())

    def test_model_plan_validated_and_reports_actual_changes(self):
        plan={'status':'ready','message':'Everything is perfect','operations':[{'op':'clip','target':[1],'changes':{'contrast':1.06,'sharpness':.2}}]}
        with patch.object(studio,'chat',return_value=plan) as chat:
            response=self.edit('Gently improve definition while keeping a realistic look')
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['project']['scenes'][0]['contrast'],1.06)
        self.assertNotIn('perfect',response.json()['message'])
        self.assertEqual(chat.call_args.kwargs['timeout'],90)

    def test_model_cannot_inject_commands_assets_or_invalid_values(self):
        for changes in ({'ffmpeg':'delete everything'},{'asset_id':'a'*32},{'volume':8},{'brightness':float('inf')},{'mute':'yes'}):
            with self.subTest(changes=changes),patch.object(studio,'chat',return_value={'operations':[{'op':'clip','changes':changes}]}):
                self.assertEqual(self.edit('An unusual detailed request').status_code,422)

    def test_clarification_and_offline_model_leave_timeline_untouched(self):
        with patch.object(studio,'chat',return_value={'status':'clarify','message':'Which clip should move?','operations':[]}):
            response=self.edit('Move that one over there')
        self.assertEqual(response.json()['status'],'clarify');self.assertNotIn('project',response.json())
        with patch.object(studio,'chat',side_effect=ConnectionError('offline')):
            response=self.edit('Please reorganize the second half intelligently')
        self.assertEqual(response.status_code,422);self.assertIn('Connect',response.json()['detail'])

    def test_empty_captions_not_falsely_reported_as_transcription(self):
        self.assertEqual(self.edit('Show captions').status_code,422)
        self.assertEqual(self.edit('Add Hindi subtitles').json()['status'],'unsupported')

    def test_natural_preset_black_white_and_numeric_limits(self):
        response=self.edit('Video ko natural aur clean banao')
        self.assertTrue(response.json()['project']['denoise'])
        self.assertEqual(response.json()['project']['scenes'][0]['sharpness'],.2)
        self.assertEqual(self.edit('Black and white').json()['project']['color'],'noir')
        self.assertEqual(self.edit('Speed 8').status_code,422)
        self.assertEqual(self.edit('Clip 9 mute').status_code,422)

    def test_real_export_brightness_changes_pixels(self):
        means=[]
        for brightness in (0,.1):
            p=self.project();p.scenes[0].end=.5;p.scenes[0].brightness=brightness;p.scenes[0].sharpness=.2
            jid=uuid.uuid4().hex
            studio.JOBS[jid]={'id':jid,'kind':'render','project_id':p.id,'status':'running','progress':0,'events':[]}
            studio.worker(jid,studio.render,p)
            self.assertEqual(studio.JOBS[jid]['status'],'completed',studio.JOBS[jid].get('error'))
            output=studio.DATA/'renders'/jid/'final.mp4'
            pixels=studio.run([main.FFMPEG_PATH,'-v','error','-i',str(output),'-frames:v','1','-vf','scale=16:16','-f','rawvideo','-pix_fmt','gray','pipe:1'])
            means.append(sum(pixels)/len(pixels))
        self.assertGreater(means[1]-means[0],15)


if __name__=='__main__':
    unittest.main()
