import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

import video_brief


class BriefTests(unittest.TestCase):
    def setUp(self):
        self.project=SimpleNamespace(prompt='bhai solar power bachchon ko samjhao ghar ka example dena',
            generation_mode='images',language='hi',duration=40,style='cinematic',aspect_ratio='16:9')
        self.valid={'topic':'Solar energy','objective':'Explain how solar power supplies a home',
            'audience':'Children','tone':'Simple and friendly','kind':'explanation',
            'must_include':['A household example'],'avoid':['Jargon'],
            'visual_approach':'Panels connected to home appliances',
            'needs_research':True,'search_query':'Solar power photovoltaics'}

    def test_interpretation_preserves_settings_and_requirements(self):
        chat=Mock(return_value=self.valid)
        result=video_brief.analyze(self.project,chat,Mock())
        self.assertEqual(result['status'],'interpreted')
        self.assertEqual(result['must_include'],['A household example'])
        self.assertEqual(json.loads(chat.call_args.args[1])['selected_settings']['duration_seconds'],40)
        self.assertEqual(self.project.duration,40)

    def test_invalid_or_incomplete_analysis_repairs_once(self):
        for invalid in ({}, {'topic':'X'}, {**self.valid,'needs_research':'yes'},
                        {**self.valid,'search_query':''}, ValueError('Invalid JSON')):
            with self.subTest(invalid=str(invalid)):
                chat=Mock(side_effect=[invalid,self.valid])
                result=video_brief.analyze(self.project,chat,Mock())
                self.assertEqual(result['attempts'],2)
                self.assertTrue(json.loads(chat.call_args.args[1])['validation_feedback'])

    def test_failed_interpretation_keeps_original_prompt(self):
        chat=Mock(return_value={})
        result=video_brief.analyze(self.project,chat,Mock())
        self.assertEqual(chat.call_count,2)
        self.assertEqual(result['status'],'original_prompt')
        self.assertEqual(result['objective'],self.project.prompt)
        self.assertNotIn('sources',result)

    def test_connection_failure_and_cancellation_are_not_swallowed(self):
        for chat,checkpoint in ((Mock(side_effect=RuntimeError('Planner offline')),Mock()),
                                (Mock(return_value=self.valid),Mock(side_effect=RuntimeError('Cancelled')))):
            with self.assertRaises(RuntimeError):
                video_brief.analyze(self.project,chat,checkpoint)

    def test_fiction_can_skip_research(self):
        result=video_brief.analyze(self.project,Mock(return_value={
            **self.valid,'kind':'story','needs_research':False,'search_query':''}),Mock())
        self.assertFalse(result['needs_research'])

    def test_explanations_request_references_even_if_model_disables_them(self):
        result=video_brief.analyze(self.project,Mock(return_value={
            **self.valid,'needs_research':False}),Mock())
        self.assertTrue(result['needs_research'])

    def test_settings_and_visual_kinds_match_selected_modes(self):
        import studio
        for mode in ('images','avatar','hybrid','motion'):
            p=studio.Project(generation_mode=mode,duration=55,language='hi',aspect_ratio='9:16',
                narration=False,captions=True,research=False,motion_preset='preview',
                presenter_character='maya',presenter_layout='pip-left',presenter_theme='teal')
            selected=video_brief.selected_settings(p)
            for key in ('narration','captions','research','motion_preset','presenter_character','presenter_layout','presenter_theme'):
                self.assertEqual(selected[key],getattr(p,key))
            expected={'images':['image','image'],'avatar':['avatar_slide','avatar_slide'],
                      'hybrid':['motion','image'],'motion':['motion','motion']}[mode]
            self.assertEqual([video_brief.visual_kind(p,i) for i in range(2)],expected)
