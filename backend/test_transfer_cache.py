import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import requests
import bridge_cache
import media_transfer
from test_http_support import response


class TransferTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name)/'clip.mp4'

    def interrupted(self):
        first = response(content=b'abcdef', mime='video/mp4', headers={'ETag': 'one'})
        def chunks(**kwargs):
            yield b'abc'
            raise requests.exceptions.ChunkedEncodingError('Interrupted')
        first.iter_content = chunks
        return first

    def test_interrupted_transfer_resumes_with_etag(self):
        tail = response(content=b'def', mime='video/mp4', status=206,
            headers={'ETag': 'one', 'Content-Range': 'bytes 3-5/6'})
        with patch.object(media_transfer.requests, 'get', side_effect=[self.interrupted(), tail]) as get, \
             patch.object(media_transfer.time, 'sleep'):
            media_transfer.download('https://fixture.test/file', self.output, {'Authorization': 'Bearer test'})
        self.assertEqual(self.output.read_bytes(), b'abcdef')
        self.assertEqual(get.call_args.kwargs['headers']['Range'], 'bytes=3-')
        self.assertEqual(get.call_args.kwargs['headers']['If-Range'], 'one')

    def test_server_ignoring_range_restarts_without_duplicate_bytes(self):
        whole = response(content=b'abcdef', mime='video/mp4')
        with patch.object(media_transfer.requests, 'get', side_effect=[self.interrupted(), whole]), \
             patch.object(media_transfer.time, 'sleep'):
            media_transfer.download('https://fixture.test/file', self.output, {})
        self.assertEqual(self.output.read_bytes(), b'abcdef')

    def test_invalid_ranges_or_changed_etag_are_rejected(self):
        for headers in ({'ETag': 'one', 'Content-Range': 'bytes 2-5/6'},
                        {'ETag': 'two', 'Content-Range': 'bytes 3-5/6'}):
            tail = response(content=b'def', mime='video/mp4', status=206, headers=headers)
            with patch.object(media_transfer.requests, 'get', side_effect=[self.interrupted(), tail]), \
                 patch.object(media_transfer.time, 'sleep'), self.assertRaises(ValueError):
                media_transfer.download('https://fixture.test/file', self.output, {})

    def test_nonvideo_oversize_and_cancellation_fail(self):
        for remote, limit in ((response(content=b'html', mime='text/html'), 50),
                              (response(content=b'abcdef', mime='video/mp4'), 3)):
            with patch.object(media_transfer.requests, 'get', return_value=remote), self.assertRaises(ValueError):
                media_transfer.download('https://fixture.test/file', self.output, {}, limit=limit)
        def cancel(): raise RuntimeError('cancelled')
        with patch.object(media_transfer.requests, 'get') as get, self.assertRaisesRegex(RuntimeError, 'cancelled'):
            media_transfer.download('https://fixture.test/file', self.output, {}, checkpoint=cancel)
        get.assert_not_called()


class CacheTests(unittest.TestCase):
    def setUp(self):
        self.previous = dict(bridge_cache._entries)
        bridge_cache._entries.clear()
        self.addCleanup(self.restore)

    def restore(self):
        bridge_cache._entries.clear()
        bridge_cache._entries.update(self.previous)

    def cfg(self, suffix):
        return SimpleNamespace(image_url='https://fixture'+suffix+'.test', bridge_token='private-test-token')

    def test_matching_model_identity_survives_url_change_without_token_in_key(self):
        a, b = self.cfg('a'), self.cfg('b')
        for cfg in (a, b):
            bridge_cache.remember(cfg, {'cache_models': {'motion': ['LTX', 'revision-1']}})
        self.assertEqual(bridge_cache.identity(a, 'motion'), bridge_cache.identity(b, 'motion'))
        self.assertNotIn(a.bridge_token, str(bridge_cache.identity(a, 'motion')))
        bridge_cache.remember(b, {'cache_models': {'motion': ['LTX', 'revision-2']}})
        self.assertNotEqual(bridge_cache.identity(a, 'motion'), bridge_cache.identity(b, 'motion'))

    def test_legacy_models_remain_isolated_by_address(self):
        a, b = self.cfg('a'), self.cfg('b')
        for cfg in (a, b): bridge_cache.remember(cfg, {})
        self.assertNotEqual(bridge_cache.identity(a, 'image'), bridge_cache.identity(b, 'image'))


if __name__ == '__main__':
    unittest.main()
