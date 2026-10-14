"""Exercise the actual Colab presenter routes without installing GPU libraries."""
import ast
import importlib.util
from pathlib import Path
import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import Mock
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from fastapi.testclient import TestClient
from pydantic import BaseModel,Field

ROOT=Path(__file__).parent
spec=importlib.util.spec_from_file_location('bridge',ROOT/'SmartEdit_Colab.py')
bridge=importlib.util.module_from_spec(spec);spec.loader.exec_module(bridge)

class PresenterBridgeTests(unittest.TestCase):
    def setUp(self):
        tree=ast.parse((ROOT/'SmartEdit_Colab.py').read_text(encoding='utf-8'))
        main=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='main')
        begin=next(i for i,n in enumerate(main.body) if isinstance(n,ast.FunctionDef) and n.name=='generate_presenter')
        end=next(i for i,n in enumerate(main.body) if isinstance(n,ast.ClassDef) and n.name=='VoiceRequest')
        app=FastAPI()
        self.calls=[]
        def infer(payload,progress):
            self.calls.append(payload);progress('Lip-sync test');return b'test-video-bytes'
        response=SimpleNamespace(raise_for_status=lambda:None,json=lambda:{'models':[{'name':'qwen-test'}]})
        self.ns={'bridge':app,'HTTPException':HTTPException,'Response':Response,'BaseModel':BaseModel,'Field':Field,
            'VideoJobs':bridge.VideoJobs,'inference_lock':threading.Lock(),'presenter_ready':True,
            'presenter_runtime':{'infer':infer},'state':{'pipe':object(),'motion_pipe':object(),'motion_embeddings':{'old':1},'presenter_tested':False},
            'release_model_memory':Mock(),'torch':object(),'requests':SimpleNamespace(get=Mock(return_value=response),post=Mock(return_value=response))}
        exec(compile(ast.Module(body=main.body[begin:end],type_ignores=[]),'presenter_routes','exec'),self.ns)
        self.client=TestClient(app)
        self.addCleanup(self.ns['presenter_jobs'].pool.shutdown,wait=True)

    def test_submit_poll_download_unloads_other_models_and_reports_tested(self):
        payload={'id':'a'*32,'video':'AAAA','audio':'AAAA'}
        response=self.client.post('/presenter/jobs',json=payload)
        self.assertEqual(response.status_code,200,response.text)
        for _ in range(100):
            current=self.client.get('/presenter/jobs/'+payload['id']).json()
            if current['status'] in ('completed','failed'):break
            time.sleep(.01)
        self.assertEqual(current['status'],'completed',current)
        self.assertEqual(current['message'],'Presenter clip encoded')
        self.assertEqual(self.client.get('/presenter/jobs/'+payload['id']+'/file').content,b'test-video-bytes')
        self.assertNotIn('payload',current)
        self.assertIsNone(self.ns['state']['pipe']);self.assertIsNone(self.ns['state']['motion_pipe'])
        self.assertEqual(self.ns['state']['motion_embeddings'],{})
        self.assertTrue(self.ns['state']['presenter_tested'])
        self.assertEqual(self.ns['requests'].post.call_args.kwargs['json'],{'model':'qwen-test','keep_alive':0})
        self.assertEqual(self.client.post('/presenter/jobs',json=payload).status_code,200)
        self.assertEqual(len(self.calls),1,'Retries must not duplicate expensive inference')
        payload['audio']='BBBB'
        self.assertEqual(self.client.post('/presenter/jobs',json=payload).status_code,409)

    def test_setup_missing_bad_id_and_unknown_job_are_clear_errors(self):
        payload={'id':'b'*32,'video':'AAAA','audio':'AAAA'}
        self.ns['presenter_ready']=False
        response=self.client.post('/presenter/jobs',json=payload)
        self.assertEqual(response.status_code,503);self.assertIn('Enable realistic',response.json()['detail'])
        self.ns['presenter_ready']=True;payload['id']='../../path'
        self.assertEqual(self.client.post('/presenter/jobs',json=payload).status_code,422)
        self.assertEqual(self.client.get('/presenter/jobs/'+'c'*32).status_code,404)
        self.assertEqual(self.client.post('/presenter/jobs/'+'c'*32+'/cancel').status_code,404)
        self.assertEqual(self.client.get('/presenter/jobs/'+'c'*32+'/file').status_code,404)

    def test_inference_failure_is_not_reported_as_ready_or_video(self):
        self.ns['presenter_runtime']['infer']=Mock(side_effect=RuntimeError('No face found'))
        ident='d'*32;self.client.post('/presenter/jobs',json={'id':ident,'video':'AAAA','audio':'AAAA'})
        for _ in range(100):
            current=self.client.get('/presenter/jobs/'+ident).json()
            if current['status']=='failed':break
            time.sleep(.01)
        self.assertEqual(current['status'],'failed');self.assertEqual(current['error'],'No face found')
        self.assertFalse(self.ns['state']['presenter_tested'])
        self.assertEqual(self.client.get('/presenter/jobs/'+ident+'/file').status_code,409)

if __name__=='__main__':unittest.main(verbosity=2)
