"""Execute the real bridge planner routes without requiring a GPU or Ollama."""
import ast
import json
from pathlib import Path
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from fastapi.testclient import TestClient
import requests
import SmartEdit_Colab as setup


class PlannerRuntimeTests(unittest.TestCase):
    def setUp(self):
        main=next(n for n in ast.parse(Path(setup.__file__).read_text('utf-8')).body
                  if isinstance(n,ast.FunctionDef) and n.name=='main')
        nodes=[n for n in main.body if isinstance(n,ast.FunctionDef)
               and n.name in ('chat','run_planner_probe','planner_check')]
        app=FastAPI()
        body=json.dumps({'message':{'content':'{"operations":[{"op":"clip","target":"all","changes":{"volume":0.5}}]}'}})
        self.response=Mock(status_code=200,text=body,content=body.encode(),json=lambda:json.loads(body))
        self.post=Mock(return_value=self.response)
        self.state={'pipe':object(),'motion_pipe':object(),'motion_embeddings':{},
                    'planner_tested':False,'planner_error':'','planner_retry_after':0}
        self.ns={'bridge':app,'state':self.state,'inference_lock':threading.Lock(),
                 'release_model_memory':Mock(),'torch':object(),'MODEL':'qwen3.5:9b',
                 'profile':{'context_length':8192},'bridge_token':'private-token','time':time,
                 'requests':SimpleNamespace(post=self.post,Timeout=requests.Timeout,RequestException=requests.RequestException),
                 'Response':Response,'HTTPException':HTTPException,
                 'bounded_chat_options':setup.bounded_chat_options,
                 'record_planner_result':setup.record_planner_result,
                 'planner_diagnostic':setup.planner_diagnostic,
                 'validate_planner_probe':setup.validate_planner_probe}
        exec(compile(ast.Module(body=nodes,type_ignores=[]),'<actual-planner-routes>','exec'),self.ns)
        self.client=TestClient(app)

    def test_consecutive_stages_keep_runner_warm_and_preserve_schema_and_direct_mode(self):
        schema={'type':'object','properties':{'title':{'type':'string'}}}
        for keep_alive in (0,-1):
            response=self.client.post('/api/chat',json={'model':'qwen3.5:9b','think':False,
                'format':schema,'keep_alive':keep_alive,'stream':True,'options':{'num_ctx':262144}})
            self.assertEqual(response.status_code,200)
            sent=self.post.call_args.kwargs['json']
            self.assertEqual(sent['keep_alive'],'5m')
            self.assertFalse(sent['think'])
            self.assertFalse(sent['stream'])
            self.assertEqual(sent['format'],schema)
            self.assertEqual(sent['options']['num_ctx'],8192)
        self.assertEqual(self.post.call_count,2)
        self.assertIsNone(self.state['pipe'])
        self.assertIsNone(self.state['motion_pipe'])
        self.assertTrue(self.state['planner_tested'])

    def test_recovery_probe_leaves_runner_ready_for_next_stage(self):
        self.assertEqual(self.client.post('/planner/check').json(),{'planner_ready':True})
        sent=self.post.call_args.kwargs['json']
        self.assertEqual(sent['keep_alive'],'5m')
        self.assertFalse(sent['think'])
        self.assertEqual(sent['options']['num_ctx'],8192)

    def test_failed_warm_call_invalidates_readiness_and_recovery_is_bounded(self):
        self.state['planner_tested']=True
        self.post.side_effect=requests.Timeout('private details')
        response=self.client.post('/api/chat',json={'model':'qwen3.5:9b'})
        self.assertEqual(response.status_code,504)
        self.assertFalse(self.state['planner_tested'])
        self.assertNotIn('private details',response.text)
        self.assertEqual(self.client.post('/planner/check').status_code,503)
        self.post.assert_called_once()

    def test_model_mismatch_does_not_load_another_runner(self):
        response=self.client.post('/api/chat',json={'model':'other-model'})
        self.assertEqual(response.status_code,400)
        self.post.assert_not_called()
