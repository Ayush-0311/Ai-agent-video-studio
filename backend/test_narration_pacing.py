import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import narration_pacing as pacing


class NarrationPacingTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.folder=Path(temp.name)
        self.identity=['voice','hi','male',-5]

    def observe(self, word, count=30, seconds=10):
        pacing.observe(self.folder,self.identity,' '.join([word]*count),seconds)

    def test_two_distinct_samples_learn_pace_without_counting_cached_replays(self):
        self.observe('पहला')
        self.observe('पहला')
        self.assertIsNone(pacing.measured_rate(self.folder,self.identity))
        self.observe('दूसरा',32,10)
        self.assertAlmostEqual(pacing.measured_rate(self.folder,self.identity),3.1)
        self.assertIsNone(pacing.measured_rate(self.folder,['voice','en','male',-5]))
        self.assertIsNone(pacing.measured_rate(self.folder,['voice','hi','female',-5]))
        self.assertIsNone(pacing.measured_rate(self.folder,['voice','hi','male',10]))
        saved=pacing.profile_path(self.folder,self.identity).read_text('utf-8')
        self.assertNotIn('पहला',saved)

    def test_bad_short_and_expired_audio_cannot_influence_budget(self):
        for seconds in (0,float('nan'),float('inf'),.1,500):
            self.observe('invalid',30,seconds)
        self.observe('short',4,3)
        self.assertIsNone(pacing.measured_rate(self.folder,self.identity))
        self.observe('one');self.observe('two')
        with patch.object(pacing.time,'time',return_value=pacing.time.time()+pacing.MAX_AGE+1):
            self.assertIsNone(pacing.measured_rate(self.folder,self.identity))

    def test_corrupted_optional_cache_is_ignored_and_can_be_replaced(self):
        path=pacing.profile_path(self.folder,self.identity)
        for data in ('not json','{}','[null]',json.dumps([{'id':'bad','words':30,'seconds':0,'at':0}])):
            path.write_text(data,'utf-8')
            self.assertIsNone(pacing.measured_rate(self.folder,self.identity))
        self.observe('one');self.observe('two')
        self.assertEqual(pacing.measured_rate(self.folder,self.identity),3)

    def test_history_is_bounded_and_a_single_outlier_does_not_set_pace(self):
        for i in range(10):
            self.observe(str(i))
        self.observe('outlier',60,10)
        self.assertEqual(len(pacing.samples(pacing.profile_path(self.folder,self.identity))),8)
        self.assertEqual(pacing.measured_rate(self.folder,self.identity),3)
