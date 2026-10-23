"""Real tensor conversion, offline downloads, interruption and disk-budget checks."""
import json
from pathlib import Path
import shutil
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import torch
from safetensors.torch import load_file, save_file
import compact_wan as compact


class CompactWanTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.upstream = self.root/'upstream'
        (self.upstream/'text_encoder').mkdir(parents=True)
        save_file({'first':torch.arange(1024,dtype=torch.float32)}, str(self.upstream/'text_encoder/a.safetensors'))
        save_file({'second':torch.arange(1024,dtype=torch.float32)}, str(self.upstream/'text_encoder/b.safetensors'))
        (self.upstream/'text_encoder/config.json').write_text('{"torch_dtype":"float32"}')
        (self.upstream/'text_encoder/model.safetensors.index.json').write_text(json.dumps({
            'metadata':{'total_size':8192}, 'weight_map':{'first':'a.safetensors','second':'b.safetensors'}}))
        self.files = [SimpleNamespace(rfilename=p.relative_to(self.upstream).as_posix(),size=p.stat().st_size)
                      for p in self.upstream.rglob('*') if p.is_file()]
        self.info = SimpleNamespace(sha='a'*40,siblings=self.files)
        self.downloads = []
        def fetch(model, name, revision, local_dir):
            self.downloads.append(name)
            out = Path(local_dir)/name
            out.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(self.upstream/name,out)
            return str(out)
        self.fetch = Mock(side_effect=fetch)
        self.hub = SimpleNamespace(HfApi=lambda:SimpleNamespace(model_info=lambda *a,**k:self.info), hf_hub_download=self.fetch)

    def download(self):
        with patch.dict(sys.modules, {'huggingface_hub':self.hub}):
            return Path(compact.download('Wan/test',['text_encoder/*'],lambda m:None, self.root/'cache',reserve=0))

    def test_real_shards_preserve_keys_values_and_reuse_completed_download(self):
        folder = self.download()
        for name,key in [('a','first'),('b','second')]:
            values=load_file(str(folder/f'text_encoder/{name}.safetensors'))
            self.assertEqual(set(values),{key})
            self.assertEqual(values[key].dtype,torch.bfloat16)
            self.assertTrue(torch.equal(values[key],torch.arange(1024,dtype=torch.float32).to(torch.bfloat16)))
        index=json.loads((folder/'text_encoder/model.safetensors.index.json').read_text())
        self.assertEqual(index['metadata']['total_size'],4096)
        self.assertEqual(json.loads((folder/'text_encoder/config.json').read_text())['torch_dtype'],'bfloat16')
        self.assertFalse(list((folder/'.source').rglob('*.safetensors')))
        count=len(self.downloads)
        self.assertEqual(self.download(),folder)
        self.assertEqual(len(self.downloads),count)

    def test_interruption_reuses_first_shard_and_cleans_owned_staging_only(self):
        original=compact.compact_shard
        def fail_second(source,output):
            if source.name=='b.safetensors':raise RuntimeError('interrupted')
            return original(source,output)
        with patch.object(compact,'compact_shard',side_effect=fail_second):
            with self.assertRaisesRegex(RuntimeError,'interrupted'):self.download()
        folder=self.download()
        self.assertEqual(self.downloads.count('text_encoder/a.safetensors'),1)
        self.assertTrue((self.upstream/'text_encoder/a.safetensors').exists())
        self.assertFalse(list((folder/'.source').rglob('*.safetensors')))

    def test_disk_reserve_stops_before_downloading_or_deleting(self):
        with patch.object(compact.shutil,'disk_usage',return_value=SimpleNamespace(free=0)):
            with self.assertRaisesRegex(RuntimeError,'Insufficient Colab disk'):self.download()
        self.fetch.assert_not_called()
        self.assertTrue((self.upstream/'text_encoder/a.safetensors').exists())

    def test_paths_cannot_escape_staging(self):
        for name in ('../other','/other','C:/other','foo\\bar'):
            with self.assertRaises(ValueError):compact.child(self.root,name)

    def test_nonfloating_tensor_is_preserved_and_failed_write_is_not_published(self):
        source=self.root/'mixed.safetensors';out=self.root/'converted.safetensors'
        save_file({'int':torch.arange(5), 'float':torch.ones(10)},str(source))
        compact.compact_shard(source,out)
        self.assertEqual(load_file(str(out))['int'].dtype,torch.int64)
        before=out.read_bytes()
        with patch('safetensors.torch.save_file',side_effect=OSError('disk full')):
            with self.assertRaisesRegex(OSError,'disk full'):compact.compact_shard(source,out)
        self.assertEqual(out.read_bytes(),before)
        self.assertFalse(out.with_suffix('.partial').exists())

    def test_compact_checkpoint_loads_into_real_transformers_encoder(self):
        from transformers import UMT5Config, UMT5EncoderModel
        torch.manual_seed(42)
        model=UMT5EncoderModel(UMT5Config(vocab_size=32,d_model=16,d_kv=4,d_ff=32,num_layers=1,num_heads=4)).eval()
        source=self.root/'tiny-upstream'
        model.save_pretrained(source/'text_encoder',max_shard_size='2KB',safe_serialization=True)
        self.upstream=source
        self.info.siblings=[SimpleNamespace(rfilename=p.relative_to(source).as_posix(),size=p.stat().st_size)
                            for p in source.rglob('*') if p.is_file()]
        folder=self.download()
        loaded, info=UMT5EncoderModel.from_pretrained(folder/'text_encoder',local_files_only=True,
            torch_dtype=torch.float32,output_loading_info=True)
        self.assertEqual(info['missing_keys'],[])
        self.assertEqual(info['unexpected_keys'],[])
        with torch.inference_mode():
            ids=torch.tensor([[2,3,4]])
            self.assertTrue(torch.allclose(model(ids).last_hidden_state, loaded.eval()(ids).last_hidden_state,atol=.05,rtol=.05))
