import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from runtime_tools import resolve_speech_model


class ModelSetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.cache = Path(self.temp.name)
        self.snapshot = self.cache/'snapshot'
        self.snapshot.mkdir()
        for name in ('model.bin', 'config.json', 'tokenizer.json'):
            (self.snapshot/name).write_bytes(b'fixture')

    def test_complete_cache_never_requests_network(self):
        download = Mock(return_value=str(self.snapshot))
        self.assertEqual(resolve_speech_model(download, 'base', self.cache), str(self.snapshot))
        download.assert_called_once_with('base', cache_dir=str(self.cache), local_files_only=True)

    def test_missing_snapshot_downloads_once(self):
        download = Mock(side_effect=[FileNotFoundError(), str(self.snapshot)])
        resolve_speech_model(download, 'base', self.cache)
        self.assertEqual(download.call_count, 2)
        self.assertFalse(download.call_args.kwargs['local_files_only'])

    def test_partial_cache_is_repaired(self):
        (self.snapshot/'tokenizer.json').write_bytes(b'')
        def download(model, **kwargs):
            if not kwargs['local_files_only']:
                (self.snapshot/'tokenizer.json').write_bytes(b'repaired')
            return str(self.snapshot)
        mocked = Mock(side_effect=download)
        resolve_speech_model(mocked, 'base', self.cache)
        self.assertEqual(mocked.call_count, 2)

    def test_incomplete_download_does_not_report_success(self):
        (self.snapshot/'config.json').unlink()
        with self.assertRaisesRegex(RuntimeError, 'incomplete'):
            resolve_speech_model(Mock(return_value=str(self.snapshot)), 'base', self.cache)

    def test_custom_directory_is_not_overwritten(self):
        download = Mock()
        resolve_speech_model(download, str(self.snapshot), self.cache)
        (self.snapshot/'config.json').unlink()
        with self.assertRaisesRegex(RuntimeError, 'Local Whisper directory is incomplete'):
            resolve_speech_model(download, str(self.snapshot), self.cache)
        download.assert_not_called()

    def test_network_failure_remains_actionable(self):
        download = Mock(side_effect=[FileNotFoundError(), ConnectionError('offline')])
        with self.assertRaisesRegex(ConnectionError, 'offline'):
            resolve_speech_model(download, 'base', self.cache)
