"""Connection regressions; HTTP fixtures never contact or download remote models."""
import base64
import json
import unittest
from unittest.mock import patch

import requests
from fastapi.testclient import TestClient
import main
import studio


def link(token='test-token', origin='https://bridge.test'):
    data = base64.urlsafe_b64encode(json.dumps({'token': token, 'model': 'test-model'}).encode()).decode().rstrip('=')
    return origin + '/#smartedit=' + data


def response(body, code=200):
    result = requests.Response()
    result.status_code = code
    result._content = json.dumps(body).encode()
    return result


class ConnectionTests(unittest.TestCase):
    def test_full_link_in_password_field_recovers_settings(self):
        cfg = studio.Settings(ollama_url='https://bridge.test/', image_url='https://bridge.test/', bridge_token=link())
        self.assertEqual((cfg.bridge_token, cfg.model, cfg.image_url), ('test-token', 'test-model', 'https://bridge.test'))
        self.assertEqual(studio.headers(cfg)['Authorization'], 'Bearer test-token')

    def test_full_link_in_url_field_replaces_stale_token(self):
        cfg = studio.Settings(ollama_url=link(), bridge_token='old-token')
        self.assertEqual(cfg.bridge_token, 'test-token')
        self.assertEqual(cfg.ollama_url, cfg.image_url)
        self.assertNotIn('#', cfg.ollama_url)

    def test_different_host_token_is_not_sent(self):
        for values in ({'ollama_url': 'https://other.test'}, {'ollama_url': 'https://bridge.test', 'image_url': 'https://other.test'}):
            with self.subTest(values=values), self.assertRaisesRegex(ValueError, 'different server'):
                studio.Settings(**values, bridge_token=link())

    def test_invalid_links_and_header_values(self):
        for token in ('https://bridge.test/', 'https://bridge.test/#smartedit=broken', 'Bearer token', 'bad\nheader', 'x'*513):
            with self.subTest(token_kind=token[:8]), self.assertRaises(ValueError):
                studio.Settings(ollama_url='https://bridge.test', bridge_token=token)
        for value in (None, [], {'token': '', 'model': 'x'}, {'token': {}, 'model': 'x'}):
            encoded = base64.urlsafe_b64encode(json.dumps(value).encode()).decode()
            with self.assertRaises(ValueError):
                studio.Settings(ollama_url='https://bridge.test/#smartedit='+encoded)

    def health(self, responses, **settings):
        cfg = studio.Settings(voice_engine='bridge',ollama_url='https://bridge.test', image_url='https://bridge.test', model='test-model', bridge_token='test-token').model_copy(update=settings)
        with patch.object(studio, 'settings', return_value=cfg), patch.object(studio.requests, 'get', side_effect=responses) as get:
            result = TestClient(main.app).get('/api/studio/health')
        self.assertEqual(result.status_code, 200)
        for call in get.call_args_list:
            self.assertEqual(call.kwargs['headers']['Authorization'], 'Bearer test-token')
            self.assertNotIn('test-token', call.args[0])
        return result.json()

    def test_authenticated_ready_bridge(self):
        result = self.health([response({'models':[{'name':'test-model'}]}), response({'image_ready':True,'voice_ready':True,'video_available':True,'video_tested':True})])
        self.assertTrue(all(result[key] for key in ('ollama','bridge_connected','image','voice','video_available','video_tested')))
        self.assertEqual(result['errors'], [])

    def test_rejected_token_is_not_reported_as_offline_or_gpu_failure(self):
        for code in (401, 403):
            result = self.health([response({'detail':'private test-token'}, code)]*2)
            self.assertEqual(result['services']['language_model']['status'], 'auth_required')
            self.assertEqual(result['services']['bridge']['http_status'], code)
            self.assertFalse(result['bridge_connected'])
            self.assertIn('currently running Colab', result['errors'][0])
            self.assertNotIn('test-token', json.dumps(result))
            self.assertNotIn('GPU', json.dumps(result))

    def test_timeout_network_and_tunnel_failures(self):
        for error, expected in ((requests.Timeout('private test-token'), 'timeout'), (requests.ConnectionError('private test-token'), 'network_error')):
            result = self.health([error, error])
            self.assertEqual(result['services']['bridge']['status'], expected)
            self.assertNotIn('test-token', json.dumps(result))
        result = self.health([response({'error':'ERR_NGROK_3200'},404)]*2)
        self.assertEqual(result['services']['bridge']['status'], 'tunnel_offline')

    def test_partial_startup_and_missing_model(self):
        result = self.health([response({'models':[{'name':'other-model'}]}), response({'image_ready':False,'voice_ready':False,'video_available':False})])
        self.assertTrue(result['bridge_connected'])
        self.assertFalse(result['ollama'])
        self.assertEqual(result['services']['language_model']['status'], 'model_missing')
        self.assertEqual(result['services']['bridge']['status'], 'check_failed')
        self.assertEqual(len(result['errors']), 3)

    def test_incompatible_service_and_missing_bridge(self):
        result = self.health([response({'unrelated':True})]*2)
        self.assertEqual(result['services']['bridge']['status'], 'invalid_response')
        self.assertFalse(result['bridge_connected'])
        result = self.health([response({'models':[{'name':'test-model'}]})], image_url='')
        self.assertEqual(result['services']['bridge']['status'], 'not_configured')


if __name__ == '__main__':
    unittest.main()
