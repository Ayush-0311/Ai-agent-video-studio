"""Damaged records must not block healthy projects or discard recovery evidence."""
import json,tempfile,unittest
from pathlib import Path
from fastapi import FastAPI
from fastapi.testclient import TestClient
import studio

class StorageRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.original=studio.DATA
        self.jobs=dict(studio.JOBS);studio.JOBS.clear();studio.DATA=Path(self.temp.name)
    def tearDown(self):
        studio.JOBS.clear();studio.JOBS.update(self.jobs);studio.DATA=self.original;self.temp.cleanup()
    def install(self):
        app=FastAPI();studio.install(app,{});return TestClient(app)
    def test_corrupt_jobs_preserved_and_valid_interrupted_job_recovers(self):
        folder=studio.DATA/'jobs';folder.mkdir()
        ident='a'*32;record={'id':ident,'project_id':'b'*32,'kind':'render','status':'running','events':[],'progress':20}
        (folder/(ident+'.json')).write_text(json.dumps(record))
        bad=folder/'broken.json';bad.write_text('{invalid')
        self.client=self.install()
        self.assertEqual(studio.JOBS[ident]['status'],'failed')
        self.assertEqual(bad.read_text(),'{invalid')
        warnings=self.client.get('/api/studio/storage-health').json()['warnings']
        self.assertTrue(any(w['file']=='broken.json' for w in warnings))
    def test_corrupt_and_schema_invalid_projects_do_not_hide_valid_project(self):
        client=self.install();p=studio.Project(title='Healthy')
        self.assertEqual(client.put('/api/studio/projects/'+p.id,json=p.model_dump()).status_code,200)
        folder=studio.DATA/'projects';(folder/'invalid.json').write_text('{')
        (folder/('b'*32+'.json')).write_text(json.dumps({'id':'b'*32,'scenes':'bad'}))
        response=client.get('/api/studio/projects');self.assertEqual(response.status_code,200)
        self.assertEqual([r['id'] for r in response.json()],[p.id])
        self.assertEqual(len(client.get('/api/studio/storage-health').json()['warnings']),2)
        self.assertEqual((folder/'invalid.json').read_text(),'{')
    def test_generated_preview_reference_survives_api_save_and_read(self):
        client=self.install();p=studio.Project(scenes=[studio.Scene(rendered_asset=studio.RenderedAsset(asset_id='c'*32,duration=5),mute=True)])
        self.assertEqual(client.put('/api/studio/projects/'+p.id,json=p.model_dump()).status_code,200)
        scene=client.get('/api/studio/projects').json()[0]['scenes'][0]
        self.assertEqual(scene['rendered_asset']['asset_id'],'c'*32);self.assertTrue(scene['mute']);self.assertEqual(scene['asset_id'],'')
    def test_incomplete_completed_job_is_isolated(self):
        folder=studio.DATA/'jobs';folder.mkdir();ident='d'*32
        file=folder/(ident+'.json');file.write_text(json.dumps({'id':ident,'project_id':'a'*32,'kind':'render','status':'completed','result':{}}))
        client=self.install()
        self.assertNotIn(ident,studio.JOBS)
        self.assertEqual(len(client.get('/api/studio/storage-health').json()['warnings']),1)
        self.assertTrue(file.exists())

    def test_bad_preview_identity_or_nonfinite_duration_rejected(self):
        from pydantic import ValidationError
        for value in ({'asset_id':'../../bad','duration':5},{'asset_id':'c'*32,'duration':float('nan')}):
            with self.assertRaises(ValidationError):studio.RenderedAsset(**value)

if __name__=='__main__':unittest.main()
