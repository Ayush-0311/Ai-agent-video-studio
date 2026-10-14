"""Exercise the actual pinned pyngrok code; only CLI/network boundaries are mocked.

Run with pyngrok 7.5.1 installed or its wheel on PYTHONPATH. No tunnel is opened.
"""
import contextlib
import io
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import SmartEdit_Colab as setup

try:
    import pyngrok
    from pyngrok import conf, installer, process
    from pyngrok.exception import PyngrokError
except ImportError:
    pyngrok = None


@unittest.skipIf(pyngrok is None, 'Run with the pinned pyngrok wheel to check real library integration')
class RealNgrokTests(unittest.TestCase):
    def test_audit_uses_exact_dependency_version(self):
        self.assertEqual(pyngrok.__version__, '7.5.1')
        self.assertIn('pyngrok==7.5.1', setup.COLAB_REQUIREMENTS)

    def test_previous_version_value_reproduces_reported_library_failure(self):
        with self.assertRaisesRegex(PyngrokError, 'ngrok_version.*supported version'):
            installer.get_default_config('3', '2')
        self.assertEqual(installer.get_default_config('v3', '2')['version'], '2')

    def test_prepare_calls_real_config_installer_and_builds_valid_cli_arguments(self):
        with tempfile.TemporaryDirectory() as directory:
            # No real executable: the process boundary below is mocked.
            (Path(directory)/'ngrok').touch()
            with patch.object(installer, 'install_ngrok', side_effect=AssertionError('Unexpected download')), \
                 patch.object(process.subprocess, 'check_output', return_value=b'Authtoken saved') as cli, \
                 patch.object(process, 'get_process') as start, contextlib.redirect_stdout(io.StringIO()):
                config = setup.prepare_ngrok('fake-test-token', directory)
            saved = installer.get_ngrok_config(config.config_path, use_cache=False)
            self.assertEqual(saved['version'], '2')
            self.assertEqual(config.ngrok_version, 'v3')
            self.assertEqual(config.startup_timeout, 60)
            argv = cli.call_args.args[0]
            self.assertTrue(all(isinstance(value, str) for value in argv))
            self.assertEqual(argv[:4], [str(Path(directory)/'ngrok'), 'config', 'add-authtoken', 'fake-test-token'])
            self.assertIn(config.config_path, argv)
            start.assert_called_once_with(config)

    def test_real_wrapper_failure_preserves_output_and_writes_redacted_log(self):
        token = 'fake-private-token'
        failure = subprocess.CalledProcessError(1, ['ngrok', 'config', 'add-authtoken', token],
                                               output=f'configuration invalid: {token}'.encode())
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory)/'ngrok').touch()
            with patch.object(process.subprocess, 'check_output', side_effect=failure), \
                 patch.object(process, 'get_process') as start, contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaisesRegex(RuntimeError, 'configuration invalid') as result:
                    setup.prepare_ngrok(token, directory)
            log = (Path(directory)/'startup-error.log').read_text(encoding='utf-8')
            self.assertNotIn(token, str(result.exception)+log)
            self.assertIn('[REDACTED]', log)
            self.assertIn('installing ngrok', log)
            start.assert_not_called()


if __name__ == '__main__':
    unittest.main()
