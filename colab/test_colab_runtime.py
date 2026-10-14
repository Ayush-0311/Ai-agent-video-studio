"""Execute the real Colab motion function with lightweight fake GPU boundaries."""
import ast
from contextlib import nullcontext
from pathlib import Path
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import numpy as np
import SmartEdit_Colab as setup


class Tensor:
    def cpu(self): return self
    def to(self, **kwargs): return self


class MotionRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.state = {'pipe':None, 'motion_pipe':None, 'motion_embeddings':{}, 'video_tested':False}
        self.encodes, self.calls, self.loads = [], [], []
        fixture = self
        class Pipe:
            def __init__(self, **kwargs): self.vae = SimpleNamespace(enable_tiling=lambda:None)
            @classmethod
            def from_pretrained(cls,*args,**kwargs): fixture.loads.append('transformer');return cls()
            def enable_model_cpu_offload(self): pass
            def encode_prompt(self,**kwargs): fixture.encodes.append(kwargs['prompt']);return Tensor(),Tensor()
            def __call__(self,**kwargs):
                fixture.calls.append(kwargs)
                for i in range(kwargs['num_inference_steps']): kwargs['callback_on_step_end'](self,i,None,{})
                frames=np.zeros((2,kwargs['height'],kwargs['width'],3),dtype=float)
                frames[:,::2]=1
                return SimpleNamespace(frames=[frames])
        def encoder(*args,**kwargs): self.loads.append('encoder');return object()
        modules={
            'diffusers':SimpleNamespace(WanPipeline=Pipe,AutoencoderKLWan=SimpleNamespace(from_pretrained=lambda *a,**k:SimpleNamespace()),UniPCMultistepScheduler=SimpleNamespace(from_config=lambda *a,**k:None)),
            'diffusers.utils':SimpleNamespace(export_to_video=lambda frames,path,**kwargs:Path(path).write_bytes(b'x'*1500)),
            'transformers':SimpleNamespace(AutoTokenizer=SimpleNamespace(from_pretrained=lambda *a,**k:None),UMT5EncoderModel=SimpleNamespace(from_pretrained=encoder),BitsAndBytesConfig=lambda **k:None),
        }
        self.modules=patch.dict(sys.modules,modules);self.modules.start();self.addCleanup(self.modules.stop)
        def reader(*args):
            c=self.calls[-1];pixels=np.zeros((c['height'],c['width'],3),dtype='uint8');pixels[::2]=255
            return SimpleNamespace(get_data=lambda index:pixels,close=lambda:None)
        imageio=SimpleNamespace(v2=SimpleNamespace(get_reader=reader))
        self.reader=patch.dict(sys.modules,{'imageio':imageio,'imageio.v2':imageio.v2});self.reader.start();self.addCleanup(self.reader.stop)
        torch=SimpleNamespace(float32='float32',bfloat16='bfloat16',device=lambda d:d,Generator=lambda d:SimpleNamespace(manual_seed=lambda s:s),
            inference_mode=nullcontext,isfinite=lambda t:SimpleNamespace(all=lambda:True),cuda=SimpleNamespace(OutOfMemoryError=MemoryError,max_memory_allocated=lambda:1024**3))
        self.env={'state':self.state,'video_profile':setup.motion_profile(15,13,False),'motion_settings':setup.motion_settings,
            'torch':torch,'release_model_memory':lambda t:None,'inference_lock':threading.Lock(),
            'requests':SimpleNamespace(get=lambda *a,**k:SimpleNamespace(raise_for_status=lambda:None,json=lambda:{'models':[]})),
            'download_model_serially':lambda *a:'fixture','time':time,'tempfile':tempfile,'Path':Path}
        tree=ast.parse(Path(setup.__file__).read_text('utf-8'))
        main=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='main')
        generate=next(n for n in main.body if isinstance(n,ast.FunctionDef) and n.name=='generate_motion')
        exec(compile(ast.Module(body=[generate],type_ignores=[]),'<actual-colab-motion>','exec'),self.env)
        self.generate=self.env['generate_motion']

    def test_storyboard_reuses_encoder_and_transformer_and_reports_actual_steps(self):
        # T4 scheduler has a config; use the profile without scheduler replacement in this boundary fixture.
        self.env['video_profile']['flow_shift']=None
        events=[]
        for prompt,following in [('opening',['ending']),('ending',[])]:
            result=self.generate({'prompt':prompt,'following_prompts':following,'preset':'preview','aspect_ratio':'16:9','seed':1},events.append)
            self.assertEqual(len(result),1500)
        self.assertEqual(self.loads,['encoder','transformer'])
        self.assertEqual(self.encodes,['opening','ending'])
        self.assertEqual(self.calls[-1]['num_frames'],49)
        self.assertEqual(self.calls[-1]['num_inference_steps'],12)
        self.assertTrue(any('step 12/12' in e and 'min left' in e for e in events))
        self.assertTrue(any('Reusing' in e for e in events))
        self.assertTrue(self.state['video_tested'])

    def test_cancellation_drops_loaded_model_and_new_prompt_reencodes(self):
        self.env['video_profile']['flow_shift']=None
        def cancel(message):
            if 'step 1/' in message: raise RuntimeError('Cancelled by user.')
        with self.assertRaisesRegex(RuntimeError,'Cancelled'):
            self.generate({'prompt':'opening','preset':'preview','aspect_ratio':'1:1','seed':1},cancel)
        self.assertIsNone(self.state['motion_pipe'])
        self.generate({'prompt':'new subject','preset':'balanced','aspect_ratio':'9:16','seed':1},lambda m:None)
        self.assertEqual(self.loads.count('encoder'),2)
        self.assertEqual(self.calls[-1]['width'],352)
        self.assertEqual(self.calls[-1]['num_inference_steps'],30)


if __name__=='__main__': unittest.main()
