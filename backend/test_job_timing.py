"""Persist real worker time separately from time spent waiting for the worker."""
import unittest
from unittest.mock import patch
import studio


class JobTimingTests(unittest.TestCase):
    def test_queue_wait_does_not_inflate_processing_or_event_time(self):
        with patch.object(studio,'JOBS',{}),patch.object(studio,'write_json'), \
             patch.object(studio.POOL,'submit'),patch.object(studio.time,'time',return_value=100) as clock:
            def work(jid,project):
                clock.return_value=130
                studio.event(jid,'Script writer','completed','Script ready.')
                clock.return_value=135
                return {'ok':True}
            project=studio.Project(prompt='Explain sunlight')
            job=studio.queue('plan',project,work)
            clock.return_value=120
            studio.worker(job['id'],work,project)
            self.assertEqual(job['queued_at'],100)
            self.assertEqual(job['started_at'],120)
            self.assertEqual(job['finished_at'],135)
            self.assertEqual(job['elapsed_seconds'],15)
            self.assertEqual(job['events'][0]['at'],130)
            self.assertEqual(job['events'][0]['elapsed_seconds'],10)
            self.assertEqual(job['status'],'completed')

    def test_failed_jobs_also_record_elapsed_time(self):
        with patch.object(studio,'JOBS',{}),patch.object(studio,'write_json'), \
             patch.object(studio.POOL,'submit'),patch.object(studio.time,'time',return_value=100) as clock:
            def fail(jid,project):
                clock.return_value=115
                raise RuntimeError('Planner unavailable')
            project=studio.Project(prompt='Explain sunlight')
            job=studio.queue('plan',project,fail)
            studio.worker(job['id'],fail,project)
            self.assertEqual(job['status'],'failed')
            self.assertEqual(job['elapsed_seconds'],15)
