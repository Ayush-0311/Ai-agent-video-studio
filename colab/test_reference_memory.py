"""Reference encoding releases SDXL first and retains only small CPU tensors."""
from contextlib import nullcontext
from types import SimpleNamespace
import sys
import unittest
from unittest.mock import Mock, patch

import numpy as np
from PIL import Image
import SmartEdit_Colab as setup


class Tensor:
    def __init__(self, values): self.values = np.asarray(values)
    def to(self, **kwargs): return self
    def unsqueeze(self, axis): return Tensor(np.expand_dims(self.values, axis))
    def cpu(self): return self


class ReferenceMemoryTests(unittest.TestCase):
    def test_encode_before_pipeline_load_and_reuse_only_small_embedding(self):
        state = {'pipe': object()}
        calls = []
        class Encoder:
            def to(self, device): return self
            def __call__(self, pixels): return SimpleNamespace(image_embeds=Tensor([[1., 2., 3.]]))
        def load(*args, **kwargs):
            self.assertIsNone(state['pipe'])
            self.assertTrue(kwargs['low_cpu_mem_usage'])
            self.assertTrue(kwargs['local_files_only'])
            self.assertTrue(kwargs['use_safetensors'])
            calls.append('encoder')
            return Encoder()
        download = Mock(return_value='local-adapter')
        modules = {
            'huggingface_hub': SimpleNamespace(snapshot_download=download),
            'transformers': SimpleNamespace(
                CLIPVisionModelWithProjection=SimpleNamespace(from_pretrained=load),
                CLIPImageProcessor=lambda:lambda **kw:SimpleNamespace(pixel_values=Tensor([0.])))
        }
        torch = SimpleNamespace(float16='float16', inference_mode=nullcontext,
            zeros_like=lambda t:Tensor(np.zeros_like(t.values)),
            cat=lambda ts,dim:Tensor(np.concatenate([t.values for t in ts],axis=dim)))
        ref = Image.new('RGB',(8,8),'blue')
        with patch.dict(sys.modules, modules), patch.object(setup,'configure_low_memory_downloads'), patch.object(setup,'release_model_memory',side_effect=lambda t:calls.append('release')):
            folder, embeds = setup.prepare_sdxl_reference(state, ref, torch)
            self.assertEqual(calls, ['release','encoder','release'])
            self.assertEqual(embeds[0].values.shape, (2,1,3))
            self.assertTrue(np.array_equal(embeds[0].values[0], [[0,0,0]]))
            self.assertTrue(np.array_equal(embeds[0].values[1], [[1,2,3]]))
            self.assertEqual(download.call_args.kwargs['max_workers'], 1)
            self.assertFalse(any(name.endswith('.bin') for name in download.call_args.kwargs['allow_patterns']))
            state['pipe'] = 'loaded-sdxl'
            self.assertEqual(setup.prepare_sdxl_reference(state, ref, torch)[0], folder)
            self.assertEqual(state['pipe'], 'loaded-sdxl')
            self.assertEqual(download.call_count, 1)
            setup.prepare_sdxl_reference(state, Image.new('RGB',(8,8),'red'), torch)
            self.assertEqual(download.call_count, 2)
