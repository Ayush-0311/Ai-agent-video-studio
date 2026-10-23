"""Do not accept truncated model output even when its JSON happens to parse."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
import studio


class ChatResponseTests(unittest.TestCase):
    def test_qwen_agents_default_to_reasoning_but_can_opt_out(self):
        cfg=SimpleNamespace(ollama_url='http://test',model='qwen3.5:9b')
        with patch.object(studio,'settings',return_value=cfg),patch.object(studio,'headers',return_value={}), \
             patch.object(studio.requests,'post',return_value=Mock(status_code=200,json=lambda:{'message':{'content':'{}'}})) as post, \
             patch.dict(studio.ENV,{'extract_json_object':__import__('json').loads}):
            studio.chat('system','message',temperature=0,think=True)
            options=post.call_args.kwargs['json']['options']
            self.assertEqual(options['temperature'],1.)
            self.assertEqual(options['presence_penalty'],1.5)
            self.assertEqual(options['num_predict'],6000)
            studio.chat('system','message',temperature=.2)
            self.assertTrue(post.call_args.kwargs['json']['think'])
            self.assertEqual(post.call_args.kwargs['json']['options']['temperature'],1.)
            studio.chat('system','message',temperature=.2,think=False)
            self.assertEqual(post.call_args.kwargs['json']['options'],{'temperature':.2,'num_ctx':8192,'num_predict':6000})

    def request(self, reply):
        cfg=SimpleNamespace(ollama_url='http://test',model='test')
        with patch.object(studio,'settings',return_value=cfg),patch.object(studio,'headers',return_value={}), \
             patch.object(studio.requests,'post',return_value=Mock(status_code=200,json=lambda:reply)), \
             patch.dict(studio.ENV,{'extract_json_object':__import__('json').loads}):
            return studio.chat('system','message')

    def test_output_limit_rejects_even_parseable_partial_result(self):
        with self.assertRaisesRegex(ValueError,'output limit'):
            self.request({'done_reason':'length','message':{'content':'{"segments":[]}'}})

    def test_completed_output_is_parsed(self):
        self.assertEqual(self.request({'done_reason':'stop','message':{'content':'{"ok":true}'}}),{'ok':True})

    def test_older_servers_without_stop_reason_remain_supported(self):
        self.assertEqual(self.request({'message':{'content':'{"ok":true}'}}),{'ok':True})

    def test_planner_unavailability_is_actionable_without_exposing_url(self):
        cfg=SimpleNamespace(ollama_url='http://private-host',model='test')
        for error in (studio.requests.Timeout(),studio.requests.ConnectionError(),None):
            with patch.object(studio,'settings',return_value=cfg),patch.object(studio,'headers',return_value={}), \
                 patch.object(studio.requests,'post',side_effect=error,return_value=Mock(status_code=503)):
                with self.assertRaises(RuntimeError) as caught:
                    studio.chat('system','message')
                self.assertIn('Colab language planner',str(caught.exception))
                self.assertNotIn('private-host',str(caught.exception))
