"""Actual image route with fake GPU pipeline: validates reference routing, not model quality."""
import ast
import base64
import io
from pathlib import Path
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field
from PIL import Image


class ImageReferenceTests(unittest.TestCase):
    def setUp(self):
        source=(Path(__file__).parent/'SmartEdit_Colab.py').read_text('utf-8')
        tree=ast.parse(source)
        main=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='main')
        nodes=[n for n in main.body if isinstance(n,(ast.ClassDef,ast.FunctionDef)) and n.name in ('ImageRequest','image')]
        self.app=FastAPI()
        frame=Image.new('RGB',(256,256),'teal')
        frame.paste('white',(0,0,80,80))
        buffer=io.BytesIO();frame.save(buffer,format='PNG')
        self.encoded=base64.b64encode(buffer.getvalue()).decode()
        self.pipe=Mock(return_value=SimpleNamespace(images=[frame]));self.pipe._smartedit_reference=True
        response=Mock();response.json.return_value={'models':[]}
        self.ns={'bridge':self.app,'BaseModel':BaseModel,'Field':Field,'HTTPException':HTTPException,
            'Response':Response,'io':io,'base64':base64,'inference_lock':threading.Lock(),
            'state':{'pipe':self.pipe,'motion_pipe':None,'image_tested':False},
            'visual_profile':{'family':'sdxl'},'release_model_memory':Mock(),
            'requests':SimpleNamespace(get=Mock(return_value=response)),
            'torch':SimpleNamespace(Generator=Mock(return_value=Mock()),cuda=SimpleNamespace(OutOfMemoryError=MemoryError)),
            'image_options':lambda *args:{'prompt':args[1]}}
        exec(compile(ast.Module(body=nodes,type_ignores=[]),'image-route','exec'),self.ns)
        self.client=TestClient(self.app)

    def test_sdxl_and_flux_receive_decoded_reference(self):
        for family,key in (('sdxl','ip_adapter_image'),('flux','image')):
            with self.subTest(family=family):
                self.ns['visual_profile']['family']=family
                response=self.client.post('/image',json={'prompt':'A man','reference_image':self.encoded})
                self.assertEqual(response.status_code,200,response.text[:100] if response.status_code!=200 else '')
                self.assertIsInstance(self.pipe.call_args.kwargs[key],Image.Image)
                self.assertTrue(self.ns['state']['image_tested'])

    def test_no_reference_preserves_plain_generation(self):
        self.pipe._smartedit_reference=False
        response=self.client.post('/image',json={'prompt':'A landscape'})
        self.assertEqual(response.status_code,200)
        self.assertNotIn('ip_adapter_image',self.pipe.call_args.kwargs)

    def test_invalid_reference_fails_before_model_work(self):
        for value in ('not base64',base64.b64encode(b'not an image').decode()):
            response=self.client.post('/image',json={'prompt':'A man','reference_image':value})
            self.assertEqual(response.status_code,400)
        self.pipe.assert_not_called()
        self.ns['requests'].get.assert_not_called()
