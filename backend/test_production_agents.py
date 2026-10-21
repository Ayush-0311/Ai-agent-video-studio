import json
import unittest
from unittest.mock import Mock, patch
from production_agents import direct_scenes, validate_direction
import studio


class ProductionAgentsTests(unittest.TestCase):
    def setUp(self):
        self.project = studio.Project(prompt='A blue-haired pilot lands on a quiet moon', generation_mode='motion',duration=10)
        self.scenes = [studio.Scene(text='The pilot arrives', visual_prompt='Pilot lands',end=5),
                       studio.Scene(text='A quiet landscape',visual_prompt='Empty moon landscape',end=5)]
        self.direction = {'characters':[{'key':'pilot','appearance':'blue hair, silver flight suit'}],
                          'shots':[{'scene_id':self.scenes[0].id,'visual_prompt':'Wide shot of the pilot stepping down onto the moon.', 'characters':['pilot']},
                                   {'scene_id':self.scenes[1].id,'visual_prompt':'Wide empty crater under soft blue moonlight.', 'characters':[]}]}

    def test_continuity_applies_only_to_referenced_characters_and_preserves_editor_fields(self):
        original = [s.model_dump() for s in self.scenes]
        revised, report = direct_scenes(self.project,self.scenes,Mock(return_value=self.direction),Mock(),Mock())
        self.assertIn('silver flight suit',revised[0].visual_prompt)
        self.assertNotIn('flight suit',revised[1].visual_prompt)
        self.assertEqual([s.model_dump() for s in self.scenes],original)
        for a,b in zip(self.scenes,revised):
            self.assertEqual(a.model_dump(exclude={'visual_prompt'}),b.model_dump(exclude={'visual_prompt'}))
        self.assertEqual(report['director_attempts'],1)

    def test_wrong_scene_ids_repair_once_with_feedback(self):
        invalid={'characters':[], 'shots':[{'scene_id':'invented','visual_prompt':'A wide scene of a mountain'}]}
        chat=Mock(side_effect=[invalid,self.direction]);emit=Mock()
        revised, report=direct_scenes(self.project,self.scenes,chat,emit,Mock())
        self.assertEqual(len(revised),2)
        self.assertEqual(report['director_attempts'],2)
        self.assertIn('exactly once',json.loads(chat.call_args.args[1])['validation_feedback'])
        self.assertTrue(any(c.args[0]=='Storyboard QA' for c in emit.call_args_list))

    def test_invalid_output_never_loops_forever_or_silently_falls_back(self):
        chat=Mock(return_value={'shots':[]})
        with self.assertRaisesRegex(ValueError,'twice'):
            direct_scenes(self.project,self.scenes,chat,Mock(),Mock())
        self.assertEqual(chat.call_count,2)

    def test_unknown_character_and_duplicate_ids_are_rejected(self):
        self.direction['shots'][0]['characters']=['missing']
        with self.assertRaisesRegex(ValueError,'Unknown'):
            validate_direction(self.direction,self.scenes)
        self.direction['shots'][0]['characters']=[]
        self.direction['shots'][1]['scene_id']=self.scenes[0].id
        with self.assertRaisesRegex(ValueError,'exactly once'):
            validate_direction(self.direction,self.scenes)

    def test_cancel_stops_before_model_call(self):
        chat=Mock()
        with self.assertRaisesRegex(RuntimeError,'Cancelled'):
            direct_scenes(self.project,self.scenes,chat,Mock(),Mock(side_effect=RuntimeError('Cancelled')))
        chat.assert_not_called()

    def test_hybrid_director_gets_selected_settings_and_per_scene_media(self):
        self.project.generation_mode='hybrid'
        self.project.language='hi'
        self.project.aspect_ratio='9:16'
        self.scenes[0].speed=2
        chat=Mock(return_value=self.direction)
        direct_scenes(self.project,self.scenes,chat,Mock(),Mock())
        request=json.loads(chat.call_args.args[1])
        self.assertEqual(request['selected_settings']['aspect_ratio'],'9:16')
        self.assertEqual(request['selected_settings']['language'],'hi')
        self.assertEqual([s['visual_kind'] for s in request['scenes']],['motion','image'])
        self.assertEqual(request['scenes'][0]['seconds'],2.5)

    def test_failed_director_does_not_overwrite_existing_project(self):
        p=self.project.model_copy(update={'scenes':self.scenes,'title':'Saved title'},deep=True)
        before=p.model_dump()
        draft={'title':'New title','scenes':[{'text':'Pilot lands','visual_prompt':'A pilot lands'},
                                           {'text':'A quiet landscape','visual_prompt':'A moon landscape'}]}
        with patch.object(studio,'event'),patch.object(studio,'checkpoint'), \
             patch.object(studio.video_brief,'analyze',return_value=studio.video_brief.fallback(p)), \
             patch.object(studio,'chat',side_effect=[draft,{'shots':[]},{'shots':[]}]),patch.object(studio,'write_json') as save:
            with self.assertRaises(ValueError):
                studio.plan('test',p)
        self.assertEqual(p.model_dump(),before)
        save.assert_not_called()


if __name__=='__main__':
    unittest.main()
