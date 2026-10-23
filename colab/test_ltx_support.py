"""Exercise LTX wiring with real images and fake GPU libraries; no model download."""
import ast
import base64
from contextlib import nullcontext
import io
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from PIL import Image
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field
from typing import Literal
import ltx_support as ltx
import SmartEdit_Colab as setup


def encoded_image():
    output = io.BytesIO()
    Image.new('RGB', (128, 96), 'teal').save(output, format='PNG')
    return base64.b64encode(output.getvalue()).decode('ascii')


class LTXTests(unittest.TestCase):
    def test_default_setup_supports_t4_without_ltx_override(self):
        self.assertEqual(setup.MOTION_ENGINE, 'auto')
        profile = setup.motion_profile(14.6, 12.7, False, setup.MOTION_ENGINE)
        self.assertTrue(profile['available'])
        self.assertEqual(profile['engine'], 'wan2.1')
        self.assertFalse(profile['image_to_video'])

    def test_embedded_source_and_memory_guard(self):
        self.assertEqual(setup.LTX_SUPPORT_SOURCE, Path(ltx.__file__).read_text('utf-8'))
        for gpu, ram, bf16 in ((15, 13, False), (24, 64, True), (40, 32, True), (80, 128, False)):
            profile = setup.motion_profile(gpu, ram, bf16, 'ltx-13b')
            self.assertFalse(profile['available'])
            self.assertEqual(profile['model'], ltx.MODEL)
            self.assertIn('38 GiB', profile['unavailable_reason'])
        self.assertTrue(setup.motion_profile(40, 80, True, 'ltx-13b')['available'])

    def test_all_aspects_and_presets_keep_distilled_schedule(self):
        profile = ltx.profile(40, 80, True)
        for preset in ('preview', 'balanced', 'quality'):
            options = setup.motion_settings(profile, preset)
            self.assertEqual(options['steps'], 7)
            self.assertEqual((options['frames']-1) % 8, 0)
            self.assertEqual(options['fps'], 30)
            for width, height in options['sizes'].values():
                self.assertEqual(width % 32, 0)
                self.assertEqual(height % 32, 0)
        self.assertEqual(profile['sizes']['16:9'], (1216, 704))

    def test_image_validation(self):
        self.assertEqual(ltx.decode_image(encoded_image()).size, (128, 96))
        for invalid in ('', 'broken base64', base64.b64encode(b'not an image').decode(), 'a'*8000001):
            with self.assertRaises(ValueError):
                ltx.decode_image(invalid)

    def test_ltx_download_checks_disk_before_starting_large_shards(self):
        files = [SimpleNamespace(rfilename='transformer/diffusion_pytorch_model-00001-of-00006.safetensors',size=5*1024**3),
                 SimpleNamespace(rfilename='text_encoder/model-00001-of-00004.safetensors',size=5*1024**3),
                 SimpleNamespace(rfilename='LTX-Video-Open-Weights-License-0.X.txt',size=15000)]
        api = SimpleNamespace(model_info=lambda *args,**kwargs:SimpleNamespace(siblings=files))
        with self.assertRaisesRegex(RuntimeError,'No model files were downloaded'):
            setup.preflight_ltx_disk(ltx.MODEL,free_bytes=10*1024**3,api=api)
        self.assertEqual(setup.preflight_ltx_disk(ltx.MODEL,free_bytes=24*1024**3,api=api),
                         sum(item.size for item in files))

    def test_actual_call_uses_image_and_reuses_pipeline(self):
        pipe = Mock()
        pipe.return_value = SimpleNamespace(frames=['generated-frames'])
        loader = Mock(return_value=pipe)
        torch = SimpleNamespace(bfloat16='bf16', inference_mode=nullcontext,
            Generator=Mock(return_value=SimpleNamespace(manual_seed=lambda seed: seed)))
        state = {'motion_pipe': None}
        payload = {'source_image': encoded_image(), 'prompt': 'A man walks forward',
                   'seed': 42, 'aspect_ratio': '9:16'}
        events = []
        with patch.dict(sys.modules, {'torch': torch,
                'diffusers': SimpleNamespace(LTXConditionPipeline=SimpleNamespace(from_pretrained=loader))}):
            for _ in range(2):
                self.assertEqual(ltx.generate(state, 'local-snapshot', payload,
                    ltx.settings(ltx.profile(40, 80, True), 'balanced'), events.append), 'generated-frames')
        loader.assert_called_once()
        self.assertTrue(loader.call_args.kwargs['local_files_only'])
        pipe.enable_model_cpu_offload.assert_called_once()
        call = pipe.call_args.kwargs
        self.assertEqual(call['image'].size, (480, 832))
        self.assertEqual(call['timesteps'], ltx.TIMESTEPS)
        self.assertEqual(call['guidance_scale'], 1)
        self.assertEqual(call['frame_rate'], 30)
        call['callback_on_step_end'](pipe, 6, None, {})
        self.assertIn('step 7/7', events[-1])

    def test_motion_request_rejects_missing_image_before_job_submission(self):
        tree = ast.parse(Path(setup.__file__).read_text('utf-8'))
        main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'main')
        nodes = [n for n in main.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))
                 and n.name in ('VideoRequest', 'submit_video')]
        app = FastAPI()
        jobs = Mock()
        jobs.submit.return_value = {'status': 'queued'}
        env = dict(bridge=app, BaseModel=BaseModel, Field=Field, Literal=Literal,
            HTTPException=HTTPException, video_profile=ltx.profile(40, 80, True),
            video_jobs=jobs, ltx_runtime={'decode_image': ltx.decode_image})
        exec(compile(ast.Module(body=nodes, type_ignores=[]), 'actual-video-route', 'exec'), env)
        client = TestClient(app)
        payload = {'id': 'a'*32, 'prompt': 'A man walks'}
        self.assertEqual(client.post('/video/jobs', json=payload).status_code, 422)
        jobs.submit.assert_not_called()
        payload['source_image'] = encoded_image()
        self.assertEqual(client.post('/video/jobs', json=payload).status_code, 200)
        self.assertEqual(jobs.submit.call_args.args[1]['source_image'], payload['source_image'])
        env['video_profile'] = ltx.profile(15, 13, False)
        jobs.reset_mock()
        self.assertEqual(client.post('/video/jobs', json=payload).status_code, 503)
        jobs.submit.assert_not_called()


if __name__ == '__main__':
    unittest.main()
