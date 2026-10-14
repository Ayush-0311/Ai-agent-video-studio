"""Exercise real subprocess diagnostics without downloading GPU dependencies."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import musetalk_support as setup


class MuseTalkSetupTests(unittest.TestCase):
    def test_child_stderr_is_visible_and_preserved_across_runs(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(setup, 'ROOT', Path(directory)):
            output = io.StringIO()
            with contextlib.redirect_stdout(output), self.assertRaises(RuntimeError) as error:
                setup.run([sys.executable, '-c', "raise ImportError('missing-test-dependency')"],
                          stage='Checking imports')
            self.assertIn('missing-test-dependency', str(error.exception))
            self.assertIn('Checking imports', str(error.exception))
            self.assertIn('ImportError', output.getvalue())
            with contextlib.redirect_stdout(output):
                setup.run([sys.executable, '-c', "print('recovery passed')"])
            log = (Path(directory)/'setup.log').read_text(encoding='utf-8')
            self.assertIn('missing-test-dependency', log)
            self.assertIn('recovery passed', log)

    def test_child_does_not_inherit_notebook_python_path(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(setup, 'ROOT', Path(directory)):
            with patch.dict(setup.os.environ, {'PYTHONPATH': '/fake/notebook/packages',
                                             'MPLBACKEND': 'module://matplotlib_inline.backend_inline'}):
                setup.run([sys.executable, '-c',
                           "import os; assert 'PYTHONPATH' not in os.environ; "
                           "assert os.environ['MPLBACKEND'] == 'Agg'; "
                           "assert os.environ['PYTHONNOUSERSITE'] == '1'"])
                self.assertEqual(setup.os.environ['MPLBACKEND'], 'module://matplotlib_inline.backend_inline')

    def test_inference_uses_isolated_environment(self):
        # Exercise the actual inference launch without importing GPU packages.
        with tempfile.TemporaryDirectory() as directory, patch.object(setup, 'ROOT', Path(directory)):
            (Path(directory)/'repo').mkdir()
            source = {'streams': [{'codec_type': 'video', 'width': 512, 'height': 512}], 'format': {'duration': 2}}
            audio = {'streams': [{'codec_type': 'audio'}], 'format': {'duration': 5}}
            import base64
            media = base64.b64encode(b'test').decode()
            with patch.object(setup, 'check', return_value=True), \
                 patch.dict(setup.os.environ, {'MPLBACKEND': 'module://matplotlib_inline.backend_inline', 'PYTHONPATH': '/colab'}), \
                 patch.object(setup.subprocess, 'check_output', side_effect=[json.dumps(source).encode(), json.dumps(audio).encode()]), \
                 patch.object(setup.subprocess, 'Popen', side_effect=RuntimeError('launch intercepted')) as launch:
                with self.assertRaisesRegex(RuntimeError, 'launch intercepted'):
                    setup.infer({'video': media, 'audio': media}, lambda message: None)
            self.assertEqual(launch.call_args.kwargs['env']['MPLBACKEND'], 'Agg')
            self.assertNotIn('PYTHONPATH', launch.call_args.kwargs['env'])

    def test_failed_revalidation_invalidates_cached_success(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(setup, 'ROOT', Path(directory)):
            marker = Path(directory)/'verified.json'
            marker.write_text('{}')
            with patch.object(setup, 'check', return_value=True), \
                 patch.object(setup, 'verify_runtime', side_effect=RuntimeError('CUDA failed')):
                with self.assertRaisesRegex(RuntimeError, 'CUDA failed'):
                    setup.install()
            self.assertFalse(marker.exists())

    def test_reuse_rechecks_gpu_and_imports_before_marking_ready(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(setup, 'ROOT', Path(directory)):
            with patch.object(setup, 'check', return_value=True), \
                 patch.object(setup, 'verify_runtime') as gpu, \
                 patch.object(setup, 'verify_imports') as imports:
                setup.install()
            gpu.assert_called_once()
            imports.assert_called_once()
            marker = json.loads((Path(directory)/'verified.json').read_text())
            self.assertEqual(marker['installer_version'], setup.INSTALLER_VERSION)
            self.assertFalse(marker['inference_tested'])

    def test_embedded_installer_matches_delivered_module(self):
        import SmartEdit_Colab as notebook
        self.assertEqual(notebook.MUSETALK_SUPPORT_SOURCE,
                         Path(setup.__file__).read_text(encoding='utf-8-sig'))


if __name__ == '__main__':
    unittest.main()
