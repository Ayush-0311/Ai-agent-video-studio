import ast
import json
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch
import omnivoice_support as omni
import SmartEdit_Colab as notebook


class OmniVoiceTests(unittest.TestCase):
    def test_embedded_source_matches_worker(self):
        self.assertEqual(notebook.OMNIVOICE_SUPPORT_SOURCE,
                         Path(omni.__file__).read_text(encoding='utf-8'))

    def test_synthesis_uses_isolated_interpreter_and_validates_both_formats(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(omni, 'ROOT', Path(folder)):
            calls = []
            def run(args, timeout):
                calls.append(args)
                if str(args[0]) != 'ffmpeg':
                    request = json.loads(Path(args[2]).read_text())
                    self.assertEqual(request['gender'], 'female')
                    self.assertEqual(request['language'], 'hi')
                Path(args[-1]).write_bytes(b'audio')
            validate = Mock()
            service = omni.OmniVoiceService(validate)
            with patch.object(omni, 'run', side_effect=run):
                data, name, provider = service.synthesize('नमस्ते', 'hi', 'hi-IN-SwaraNeural', -5)
            self.assertEqual((data, provider), (b'audio', 'omnivoice'))
            self.assertEqual(validate.call_count, 2)
            self.assertEqual(calls[0][0], omni.python_path())

    def test_failure_invalidates_readiness_without_another_provider(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(omni, 'ROOT', Path(folder)):
            service = omni.OmniVoiceService(Mock())
            service.providers['en'] = 'omnivoice'
            with patch.object(omni, 'run', side_effect=RuntimeError('GPU out of memory')) as run:
                with self.assertRaisesRegex(RuntimeError, 'GPU out of memory'):
                    service.synthesize('Hello', 'en', 'male', 0)
            run.assert_called_once()
            self.assertNotIn('en', service.providers)

    def test_timeout_is_reported_with_saved_log(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(omni, 'ROOT', Path(folder)):
            with patch.object(omni.subprocess, 'run', side_effect=subprocess.TimeoutExpired(['worker'], 1)):
                with self.assertRaisesRegex(RuntimeError, 'timed out'):
                    omni.run(['worker'], timeout=1)
            self.assertTrue((Path(folder)/'runtime.log').exists())

    def test_voice_releases_other_models_under_shared_gpu_lock(self):
        tree = ast.parse(Path(notebook.__file__).read_text(encoding='utf-8'))
        main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'main')
        function = next(n for n in main.body if isinstance(n, ast.FunctionDef) and n.name == 'synthesize_voice')
        lock = threading.Lock()
        service = Mock(mode='omnivoice')
        service.synthesize.side_effect = lambda *a, **kw: self.assertTrue(lock.locked())
        state = {'pipe':object(), 'motion_pipe':object(), 'motion_embeddings':{'cached':1}}
        requests = Mock()
        requests.get.return_value.json.return_value = {'models':[{'name':'planner'}]}
        ns = dict(inference_lock=lock, voice_service=service, state=state, requests=requests,
                  release_model_memory=Mock(), torch=object())
        exec(compile(ast.Module(body=[function], type_ignores=[]), 'voice', 'exec'), ns)
        ns['synthesize_voice']('Hello', 'en', 'male', 0)
        self.assertIsNone(state['pipe'])
        self.assertIsNone(state['motion_pipe'])
        self.assertEqual(state['motion_embeddings'], {})
        self.assertEqual(requests.post.call_args.kwargs['json'], {'model':'planner','keep_alive':0})
        self.assertFalse(lock.locked())


if __name__ == '__main__':
    unittest.main()
