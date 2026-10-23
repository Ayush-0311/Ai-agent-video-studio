"""Startup orchestration calls real routes and never labels failures as passed."""
import base64
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
import SmartEdit_Colab as setup


class FeatureCheckTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.events=[]
        self.image=Mock(side_effect=lambda p:self.events.append('image') or b'portrait')
        self.motion=Mock(side_effect=lambda p,cb:self.events.append('motion') or b'motion-result')
        self.presenter=Mock(side_effect=lambda p,cb:self.events.append('avatar') or b'avatar-result')

    def run_checks(self,available=True,presenter=True):
        def ffmpeg(args,**kw):Path(args[-1]).write_bytes(b'normalized-media')
        with patch.object(setup.subprocess,'run',side_effect=ffmpeg):
            return setup.verify_extra_features(self.image,self.motion,self.presenter,
                {'available':available},presenter,self.root,lambda m:None)

    def test_real_callback_order_and_saved_report(self):
        report=self.run_checks()
        self.assertEqual(self.events,['image','avatar','motion'])
        self.assertEqual(report['motion']['status'],'passed')
        self.assertEqual(report['avatar']['status'],'passed')
        self.assertEqual(self.motion.call_args.args[0]['preset'],'preview')
        self.assertEqual(base64.b64decode(self.presenter.call_args.args[0]['audio']),b'normalized-media')
        self.assertEqual(json.loads((self.root/'smartedit-feature-checks.json').read_text()),report)
        self.assertEqual((self.root/'smartedit-avatar-check.mp4').read_bytes(),b'avatar-result')

    def test_avatar_failure_does_not_skip_motion_or_report_avatar_ready(self):
        self.presenter.side_effect=RuntimeError('lip-sync failed')
        report=self.run_checks()
        self.assertEqual(report['avatar']['status'],'failed')
        self.assertIn('lip-sync failed',report['avatar']['error'])
        self.assertEqual(report['motion']['status'],'passed')
        self.assertFalse((self.root/'smartedit-avatar-check.mp4').exists())

    def test_unavailable_features_do_not_call_inference(self):
        report=self.run_checks(False,False)
        self.assertTrue(all(value['status']=='unavailable' for value in report.values()))
        self.assertEqual(self.events,[])

    def test_motion_failure_is_reported_and_preserves_avatar_result(self):
        self.motion.side_effect=RuntimeError('disk budget exceeded')
        report=self.run_checks()
        self.assertEqual(report['motion']['status'],'failed')
        self.assertIn('disk budget',report['motion']['error'])
        self.assertEqual(report['avatar']['status'],'passed')
