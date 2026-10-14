"""Offline checks for memory policy and the notebook users actually upload."""
import json
from pathlib import Path
import unittest
import contextlib
import io
import sys
import tempfile
import ast
import fnmatch
import types
from unittest.mock import patch, Mock
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
import SmartEdit_Colab as setup

from SmartEdit_Colab import bounded_chat_options, select_profile, image_profile, image_options, validate_planner_probe


class ColabSetupTests(unittest.TestCase):
    def test_token_validation_rejects_dicts_and_pasted_commands_without_leaking_values(self):
        secret = 'private-test-token_123'
        self.assertEqual(setup.validate_ngrok_token('  '+secret+'\n'), secret)
        for value in ({'authtoken':secret}, [secret], None, 123, '', '  ',
                      '{"authtoken":"'+secret+'"}', 'ngrok config add-authtoken '+secret,
                      'https://example.test/'+secret, '"'+secret+'"'):
            with self.subTest(kind=type(value).__name__):
                with self.assertRaises(ValueError) as raised:
                    setup.validate_ngrok_token(value)
                self.assertNotIn(secret, str(raised.exception))

    def test_bad_colab_secret_recovers_with_hidden_plain_text_prompt(self):
        prompt = Mock(return_value='  valid-test-token_123  ')
        with patch.dict(setup.os.environ, {}, clear=True), contextlib.redirect_stdout(io.StringIO()) as output:
            token = setup.read_ngrok_token(secret_getter=lambda name: {'token':'private-bad-value'}, prompt=prompt)
        self.assertEqual(token, 'valid-test-token_123')
        prompt.assert_called_once()
        self.assertNotIn(token, output.getvalue())
        self.assertNotIn('private-bad-value', output.getvalue())

    def test_valid_secret_or_environment_does_not_prompt(self):
        prompt = Mock(side_effect=AssertionError('Unexpected prompt'))
        with patch.dict(setup.os.environ, {}, clear=True):
            self.assertEqual(setup.read_ngrok_token(lambda name:'secret-value', prompt), 'secret-value')
        with patch.dict(setup.os.environ, {'NGROK_AUTHTOKEN':'env-value'}, clear=True):
            getter = Mock(side_effect=AssertionError('Unexpected secret read'))
            self.assertEqual(setup.read_ngrok_token(getter, prompt), 'env-value')

    def test_bad_prompt_is_bounded_and_never_reaches_ngrok(self):
        prompt = Mock(return_value={'token':'hidden-test-value'})
        with patch.dict(setup.os.environ, {}, clear=True), contextlib.redirect_stdout(io.StringIO()) as output:
            with self.assertRaisesRegex(RuntimeError, 'Colab Secrets') as raised:
                setup.read_ngrok_token(lambda name:None, prompt)
        self.assertEqual(prompt.call_count, 2)
        self.assertNotIn('hidden-test-value', output.getvalue()+str(raised.exception))

    def test_ngrok_uses_explicit_string_paths_and_checks_agent_before_returning(self):
        module = types.ModuleType('pyngrok')
        module.conf = types.SimpleNamespace(PyngrokConfig=lambda **kw: types.SimpleNamespace(**kw))
        module.ngrok = Mock()
        with tempfile.TemporaryDirectory() as folder, patch.dict(sys.modules, {'pyngrok':module}), \
             contextlib.redirect_stdout(io.StringIO()):
            config = setup.prepare_ngrok('test-token', folder)
        self.assertIsInstance(config.ngrok_path, str)
        self.assertIsInstance(config.config_path, str)
        self.assertEqual(config.ngrok_version, 'v3')
        module.ngrok.set_auth_token.assert_called_once_with('test-token', pyngrok_config=config)
        module.ngrok.get_ngrok_process.assert_called_once_with(pyngrok_config=config)
        self.assertEqual([call[0] for call in module.ngrok.mock_calls], ['set_auth_token','get_ngrok_process'])

    def test_ngrok_failure_exposes_error_code_but_not_secret_argv(self):
        module = types.ModuleType('pyngrok')
        module.conf = types.SimpleNamespace(PyngrokConfig=lambda **kw: types.SimpleNamespace(**kw))
        module.ngrok = Mock()
        module.ngrok.set_auth_token.side_effect = RuntimeError('ERR_NGROK_105 argv secret-token-value')
        with tempfile.TemporaryDirectory() as folder, patch.dict(sys.modules, {'pyngrok':module}), \
             contextlib.redirect_stdout(io.StringIO()) as output:
            with self.assertRaisesRegex(RuntimeError, 'ERR_NGROK_105') as raised:
                setup.prepare_ngrok('secret-token-value', folder)
        self.assertNotIn('secret-token-value', str(raised.exception)+output.getvalue())
        self.assertTrue(raised.exception.__suppress_context__)
        module.ngrok.get_ngrok_process.assert_not_called()

    def test_ngrok_error_retains_diagnostics_without_an_ngrok_error_code(self):
        import subprocess
        token = 'secret-token-example'
        error = subprocess.CalledProcessError(1, ['ngrok',token], output=b'unsupported config version',
                                             stderr=('bad value: '+token).encode())
        diagnostic = setup.ngrok_error_details(error, token)
        self.assertIn('unsupported config version', diagnostic)
        self.assertIn('bad value: [REDACTED]', diagnostic)
        self.assertNotIn(token, diagnostic)

    def test_ngrok_preflight_precedes_large_downloads_and_uses_same_config_for_tunnel(self):
        tree = ast.parse(Path(setup.__file__).read_text(encoding='utf-8'))
        main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'main')
        calls = [n for n in ast.walk(main) if isinstance(n, ast.Call)]
        def line(name):
            return next(n.lineno for n in calls if isinstance(n.func, ast.Name) and n.func.id == name)
        self.assertLess(line('read_ngrok_token'), line('install_dependencies'))
        self.assertLess(line('prepare_ngrok'), line('install_ollama'))
        for call in calls:
            if (isinstance(call.func, ast.Attribute) and isinstance(call.func.value, ast.Name)
                    and call.func.value.id == 'ngrok' and call.func.attr in ('connect','disconnect')):
                self.assertTrue(any(k.arg == 'pyngrok_config' and isinstance(k.value, ast.Name)
                                    and k.value.id == 'ngrok_config' for k in call.keywords))

    def test_serial_download_policy_overrides_previous_session_settings(self):
        constants = types.SimpleNamespace(HF_HUB_DISABLE_XET=False, HF_HUB_ENABLE_HF_TRANSFER=True)
        with patch.dict(setup.os.environ, {'HF_ENABLE_PARALLEL_LOADING':'true'}), \
             patch.dict(sys.modules, {'huggingface_hub.constants':constants}):
            setup.configure_low_memory_downloads()
            self.assertEqual(setup.os.environ['HF_ENABLE_PARALLEL_LOADING'], 'false')
            self.assertEqual(setup.os.environ['HF_PARALLEL_LOADING_WORKERS'], '1')
            self.assertEqual(setup.os.environ['HF_HUB_DISABLE_XET'], '1')
            self.assertEqual(setup.os.environ['USE_TF'], '0')
            self.assertTrue(constants.HF_HUB_DISABLE_XET)
            self.assertFalse(constants.HF_HUB_ENABLE_HF_TRANSFER)

    def test_download_uses_one_worker_and_failure_cannot_report_success(self):
        snapshot = Mock(return_value='/cache/snapshot')
        hub = types.ModuleType('huggingface_hub')
        hub.snapshot_download = snapshot
        progress = Mock()
        with patch.dict(sys.modules, {'huggingface_hub':hub}), patch.dict(setup.os.environ):
            self.assertEqual(setup.download_model_serially('test/model', 'wan', progress), '/cache/snapshot')
            self.assertEqual(snapshot.call_args.kwargs['max_workers'], 1)
            self.assertNotIn('force_download', snapshot.call_args.kwargs)
            snapshot.side_effect = OSError('disk full')
            progress.reset_mock()
            with self.assertRaisesRegex(OSError, 'disk full'):
                setup.download_model_serially('test/model', 'wan', progress)
            self.assertEqual(progress.call_count, 1)

    def test_download_filters_include_required_shards_and_skip_duplicate_formats(self):
        def included(family, name):
            return any(fnmatch.fnmatchcase(name, p) for p in setup.model_download_patterns(family))
        for path in ('model_index.json', 'tokenizer/spiece.model', 'text_encoder/model.safetensors.index.json',
                     'text_encoder/model-00005-of-00005.safetensors', 'transformer/diffusion_pytorch_model.safetensors',
                     'vae/config.json', 'scheduler/scheduler_config.json'):
            self.assertTrue(included('wan',path), path)
        for path in ('text_encoder/model.fp16.safetensors', 'unet/diffusion_pytorch_model.fp16.safetensors',
                     'tokenizer/merges.txt', 'tokenizer_2/vocab.json'):
            self.assertTrue(included('sdxl',path), path)
        for path in ('sd_xl_base_1.0.safetensors', 'unet/diffusion_pytorch_model.safetensors',
                     'unet/diffusion_pytorch_model.bin', 'unet/model.onnx'):
            self.assertFalse(included('sdxl',path), path)
        self.assertTrue(included('flux','transformer/diffusion_pytorch_model-00001-of-00002.safetensors'))

    def test_all_model_loaders_are_offline_after_explicit_download(self):
        tree = ast.parse(Path(setup.__file__).read_text(encoding='utf-8'))
        loaders = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                   and isinstance(node.func, ast.Attribute) and node.func.attr == 'from_pretrained']
        self.assertGreaterEqual(len(loaders), 6)
        for node in loaders:
            self.assertTrue(any(k.arg == 'local_files_only' and isinstance(k.value, ast.Constant)
                                and k.value.value is True for k in node.keywords), f'Online loader at line {node.lineno}')

    def test_ollama_installs_missing_zstd_before_executing_official_script(self):
        installed = set()
        calls = []
        def which(command):
            return None if command == 'zstd' and 'zstd' not in installed else command
        def run(command, log, label):
            calls.append(command)
            if command[:3] == ['apt-get', 'install', '-y']:
                installed.add('zstd')
            if command[0] == 'sh':
                self.assertIn('zstd', installed)
                self.assertEqual(Path(command[1]).read_bytes(), b'#!/bin/sh\nexit 0\n')
        response = Mock(content=b'#!/bin/sh\nexit 0\n')
        with patch.object(setup.sys, 'platform', 'linux'), \
             patch.object(setup.os, 'geteuid', return_value=0, create=True), \
             patch.object(setup.shutil, 'which', side_effect=which), \
             patch.object(setup, 'run_setup_step', side_effect=run), \
             patch('requests.get', return_value=response) as get, \
             contextlib.redirect_stdout(io.StringIO()):
            setup.install_ollama('unused-test.log')
        self.assertEqual(calls[0], ['apt-get', 'update'])
        self.assertEqual(calls[1], ['apt-get', 'install', '-y', '--no-install-recommends', 'zstd'])
        self.assertEqual(calls[-1], ['ollama', '--version'])
        get.assert_called_once_with('https://ollama.com/install.sh', timeout=60)
        response.raise_for_status.assert_called_once()

    def test_ollama_skips_apt_when_tools_exist_and_preserves_installer_error(self):
        def run(command, log, label):
            self.assertEqual(command[0], 'sh')
            raise RuntimeError('archive download failed: HTTP 503')
        with patch.object(setup.sys, 'platform', 'linux'), \
             patch.object(setup.shutil, 'which', side_effect=lambda command: command), \
             patch.object(setup, 'run_setup_step', side_effect=run) as runner, \
             patch('requests.get', return_value=Mock(content=b'#!/bin/sh\nexit 1\n')), \
             contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(RuntimeError, 'HTTP 503'):
                setup.install_ollama('unused-test.log')
            self.assertEqual(runner.call_count, 1)

    def test_ollama_dependency_failure_stops_before_download(self):
        with patch.object(setup.sys, 'platform', 'linux'), \
             patch.object(setup.os, 'geteuid', return_value=0, create=True), \
             patch.object(setup.shutil, 'which', side_effect=lambda command: None if command == 'zstd' else command), \
             patch.object(setup, 'run_setup_step', side_effect=RuntimeError('apt mirror unavailable')) as run, \
             patch('requests.get') as get:
            with self.assertRaisesRegex(RuntimeError, 'apt mirror unavailable'):
                setup.install_ollama('unused-test.log')
            self.assertEqual(run.call_count, 1)
            get.assert_not_called()

    def test_hub_pin_satisfies_both_library_constraints(self):
        # Requires-Dist read from official PyPI release metadata, 2026-10-02.
        constraints = {
            ('diffusers','0.37.1'): '>=0.34.0,<2.0',
            ('transformers','4.57.6'): '>=0.34.0,<1.0',
        }
        pins={r.name:next(iter(r.specifier)).version for r in map(Requirement,setup.COLAB_REQUIREMENTS)
              if len(r.specifier)==1 and next(iter(r.specifier)).operator=='=='}
        for name in ('diffusers','transformers'):
            self.assertIn(pins['huggingface-hub'],SpecifierSet(constraints[(name,pins[name])]))
        self.assertNotIn(pins['huggingface-hub'],SpecifierSet('>=1.23.0,<2.0'))

    def test_install_resolves_before_mutation_and_checks_pipeline_imports(self):
        with patch.object(setup,'run_setup_step') as run,contextlib.redirect_stdout(io.StringIO()):
            setup.install_dependencies('unused-test.log')
        calls=run.call_args_list
        self.assertEqual(len(calls),3)
        self.assertIn('--dry-run',calls[0].args[0])
        self.assertNotIn('--dry-run',calls[1].args[0])
        self.assertIn('huggingface-hub==0.36.2',calls[0].args[0])
        self.assertIn('Flux2KleinPipeline',calls[2].args[0][-1])
        with patch.object(setup,'run_setup_step',side_effect=RuntimeError('ResolutionImpossible')) as run,contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(RuntimeError,'ResolutionImpossible'):
                setup.install_dependencies('unused-test.log')
            self.assertEqual(run.call_count,1)

    def test_installer_retains_the_real_failure_message(self):
        with tempfile.TemporaryDirectory() as folder,contextlib.redirect_stdout(io.StringIO()) as output:
            log=Path(folder)/'install.log'
            with self.assertRaisesRegex(RuntimeError,'dependency-conflict-example'):
                setup.run_setup_step([sys.executable,'-c','import sys; print("dependency-conflict-example", file=sys.stderr); sys.exit(1)'],log,'Test installation')
            self.assertIn('dependency-conflict-example',log.read_text())
            self.assertIn('dependency-conflict-example',output.getvalue())
    def test_free_t4_and_larger_gpu_keep_quality_profile(self):
        for vram, ram in [(14.7, 12.7), (22.5, 50)]:
            profile = select_profile(vram, ram)
            self.assertEqual(profile['model'], 'qwen3.5:9b')
            self.assertEqual(profile['offload'], 'model')
        self.assertEqual(select_profile(40,80)['model'],'qwen3.5:27b')
        self.assertEqual(select_profile(40,12.7)['model'],'qwen3.5:9b')

    def test_smaller_gpu_uses_lower_memory_paths(self):
        profile = select_profile(8, 12)
        self.assertEqual(profile['model'], 'qwen3.5:4b')
        self.assertEqual(profile['offload'], 'sequential')
        self.assertEqual(profile['context_length'], 4096)

    def test_override_and_insufficient_resources(self):
        self.assertEqual(select_profile(14.7, 12.7, 'qwen3.5:4b')['model'], 'qwen3.5:4b')
        for args in [(0, 12), (16, 8), (8, 12, 'qwen3.5:9b'), (16, 12, 'unknown:27b')]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                select_profile(*args)
        with self.assertRaises(ValueError):
            select_profile(14.7,12.7,'qwen3.5:27b')

    def test_image_model_matches_real_hardware_and_call_signature(self):
        t4=image_profile(14.7,12.7,False)
        self.assertEqual(t4['family'],'sdxl')
        self.assertEqual(image_profile(40,12,True)['family'],'sdxl')
        modern=image_profile(22.5,32,True)
        self.assertEqual(modern['family'],'flux')
        call=image_options(modern,'a landscape',1344,768,40)
        self.assertEqual(call['num_inference_steps'],4)
        self.assertEqual(call['guidance_scale'],1)
        self.assertNotIn('negative_prompt',call)
        self.assertEqual(image_options(t4,'a landscape',1344,768,40)['num_inference_steps'],40)
        self.assertEqual(image_profile(40,80,True,'sdxl')['family'],'sdxl')
        for args in [(14.7,12.7,False,'flux'),(40,80,False,'flux'),(40,80,True,'unknown')]:
            with self.subTest(args=args),self.assertRaises(ValueError):
                image_profile(*args)

    def test_planner_startup_checks_the_actual_requested_edit(self):
        validate_planner_probe('{"operations":[{"op":"clip","target":"all","changes":{"volume":0.5}}]}')
        for content in ('hello','{"ready":true}','{"operations":[]}',
                        '{"operations":[{"op":"clip","target":"all","changes":{"volume":50}}]}'):
            with self.subTest(content=content),self.assertRaises(RuntimeError):
                validate_planner_probe(content)

    def test_context_and_generation_cannot_overallocate(self):
        options = {'num_ctx': 262144, 'num_predict': -1, 'temperature': 0.6}
        self.assertEqual(bounded_chat_options(options, 4096),
                         {'num_ctx': 4096, 'num_predict': 6000, 'temperature': 0.6})
        self.assertEqual(options['num_ctx'], 262144)
        self.assertEqual(bounded_chat_options({'num_predict': 32}, 8192)['num_predict'], 32)
        self.assertEqual(bounded_chat_options({'num_ctx': 'invalid'}, 8192)['num_ctx'], 8192)

    def test_uploaded_notebook_matches_source(self):
        root = Path(__file__).parent
        notebook = json.loads((root/'SmartEdit_Colab.ipynb').read_text(encoding='utf-8'))
        cells = [cell for cell in notebook['cells'] if cell['cell_type'] == 'code']
        self.assertEqual(len(cells), 1)
        self.assertEqual(''.join(cells[0]['source']), (root/'SmartEdit_Colab.py').read_text(encoding='utf-8'))
        self.assertEqual((root.parent/'Colab_Ollama_Setup.py').read_text(encoding='utf-8'),
                         (root/'SmartEdit_Colab.py').read_text(encoding='utf-8'))
        self.assertEqual((root.parent/'Colab_Ollama_Setup.py').read_bytes(), (root/'SmartEdit_Colab.py').read_bytes())
        self.assertEqual(cells[0]['outputs'], [])
        self.assertIsNone(cells[0]['execution_count'])
        self.assertEqual((root/'requirements-colab.txt').read_text().splitlines(),list(setup.COLAB_REQUIREMENTS))

    def test_every_delivered_entry_point_compiles_for_colab_python_313(self):
        root = Path(__file__).parent
        notebook = json.loads((root/'SmartEdit_Colab.ipynb').read_text(encoding='utf-8'))
        sources = {
            'notebook-cell': ''.join(next(cell for cell in notebook['cells'] if cell['cell_type'] == 'code')['source']),
            'root-python-file': (root.parent/'Colab_Ollama_Setup.py').read_text(encoding='utf-8'),
            'canonical-python-file': (root/'SmartEdit_Colab.py').read_text(encoding='utf-8'),
        }
        for name, source in sources.items():
            with self.subTest(entry=name):
                tree = ast.parse(source, filename=name, feature_version=(3,13))
                compile(tree, name, 'exec')


if __name__ == '__main__':
    unittest.main()
