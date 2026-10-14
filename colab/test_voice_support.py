import contextlib
import ast
import io
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from unittest.mock import Mock
from typing import Literal
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

import voice_support as voice
import SmartEdit_Colab as notebook


class VoiceTests(unittest.TestCase):
    def test_chunks_preserve_words_and_bound_long_hindi_input(self):
        text = ('नमस्ते यह आवाज का परीक्षण है। Hello world! '*100).strip()
        parts = voice.chunks(text)
        self.assertTrue(all(0 < len(p) <= 220 for p in parts))
        self.assertEqual(' '.join(parts), text)
        self.assertEqual(''.join(voice.chunks('a'*1000)), 'a'*1000)

    def test_worker_is_embedded_in_uploadable_notebook(self):
        self.assertEqual(notebook.VOICE_SUPPORT_SOURCE, Path(voice.__file__).read_text(encoding='utf-8'))

    def service(self, directory, mode='auto'):
        return voice.VoiceService('worker.py', Path(directory)/'voice.log', mode)

    def test_edge_failure_uses_mms_and_cooldown_skips_repeat_network_failures(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stdout(io.StringIO()):
            service = self.service(directory)
            commands = []
            def run(command, timeout):
                commands.append(command)
                if 'edge_tts' in command:
                    raise RuntimeError('NoAudioReceived')
                if command[0] == 'ffmpeg':
                    Path(command[-1]).write_bytes(b'validated-mp3')
            with patch.object(service, 'run', side_effect=run), patch.object(voice, 'validate_audio'):
                result = service.synthesize('नमस्ते', 'hi', 'hi-IN-MadhurNeural', -5)
                second = service.synthesize('Hello', 'en', 'en-US-JennyNeural', 0)
            self.assertEqual(result[1:], ('facebook/mms-tts-hin', 'mms'))
            self.assertEqual(second[2], 'mms')
            self.assertEqual(sum('edge_tts' in c for c in commands), 2)
            self.assertEqual(service.providers, {'hi': 'mms', 'en': 'mms'})
            self.assertIn('NoAudioReceived', service.log_path.read_text())

    def test_edge_success_does_not_download_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            service = self.service(directory)
            def run(command, timeout):
                self.assertIn('edge_tts', command)
                Path(command[-1]).write_bytes(b'validated-mp3')
            with patch.object(service, 'run', side_effect=run) as runner, patch.object(voice, 'validate_audio'):
                self.assertEqual(service.synthesize('Hello', 'en', 'Jenny', 0)[2], 'edge-tts')
            runner.assert_called_once()

    def test_all_providers_fail_without_marking_voice_ready(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stdout(io.StringIO()):
            service = self.service(directory)
            service.providers['hi'] = 'edge-tts'
            with patch.object(service, 'run', side_effect=RuntimeError('network denied')):
                with self.assertRaisesRegex(RuntimeError, 'MMS: network denied'):
                    service.synthesize('नमस्ते', 'hi', 'Madhur', 0)
            self.assertNotIn('hi', service.providers)

    def test_explicit_edge_mode_never_uses_mms(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stdout(io.StringIO()):
            service = self.service(directory, 'edge')
            with patch.object(service, 'run', side_effect=RuntimeError('offline')) as runner:
                with self.assertRaises(RuntimeError):
                    service.synthesize('Hello', 'en', 'Jenny', 0)
            self.assertEqual(runner.call_count, 2)
            self.assertTrue(all('edge_tts' in c.args[0] for c in runner.call_args_list))

    def test_invalid_audio_and_silence_are_rejected(self):
        for code, pcm in [(1, b''), (0, b'\0'*5000), (0, b'\1\0'*100)]:
            with patch.object(voice.subprocess, 'run', return_value=subprocess.CompletedProcess([], code, pcm)):
                with self.assertRaises(RuntimeError):
                    voice.validate_audio('bad.mp3')
        with patch.object(voice.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, b'\0\1'*3000)):
            voice.validate_audio('good.mp3')

    def test_production_route_reports_actual_provider_and_failed_readiness(self):
        tree = ast.parse(Path(notebook.__file__).read_text(encoding='utf-8'))
        main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'main')
        start = next(i for i, n in enumerate(main.body) if isinstance(n, ast.ClassDef) and n.name == 'VoiceRequest')
        end = next(i for i, n in enumerate(main.body) if isinstance(n, ast.FunctionDef) and n.name == 'voice')+1
        app = FastAPI()
        service = Mock(providers={'hi': 'mms', 'en': 'mms'})
        service.synthesize.return_value = (b'actual-audio', 'facebook/mms-tts-hin', 'mms')
        state = {'voice_tested': False}
        ns = dict(bridge=app, voice_service=service, synthesize_voice=service.synthesize, state=state, BaseModel=BaseModel,
                  Field=Field, Literal=Literal, Response=Response, HTTPException=HTTPException)
        exec(compile(ast.Module(body=main.body[start:end], type_ignores=[]), 'voice_route', 'exec'), ns)
        client = TestClient(app)
        response = client.post('/voice', json={'text': 'नमस्ते', 'language': 'hi'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['x-smartedit-voice-provider'], 'mms')
        self.assertEqual(response.headers['x-smartedit-voice-license'], 'CC-BY-NC-4.0')
        self.assertTrue(state['voice_tested'])
        service.providers.clear()
        service.synthesize.side_effect = RuntimeError('Both providers failed')
        response = client.post('/voice', json={'text': 'Hello', 'language': 'en'})
        self.assertEqual(response.status_code, 502)
        self.assertFalse(state['voice_tested'])


if __name__ == '__main__':
    unittest.main()
