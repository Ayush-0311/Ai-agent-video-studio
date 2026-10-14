"""Offline queue/resource checks; these do not claim GPU inference quality."""
import threading
import time
import unittest

from SmartEdit_Colab import VideoJobs, motion_profile, motion_settings


class MotionBridgeTests(unittest.TestCase):
    def test_request_presets_bound_workload_without_mutating_model_profile(self):
        base = motion_profile(14.7,12.7,False)
        draft, balanced, quality = [motion_settings(base, p) for p in ('preview','balanced','quality')]
        self.assertEqual((draft['steps'], draft['frames'], draft['sizes']['16:9']), (12,49,(512,288)))
        self.assertEqual((balanced['steps'], balanced['frames'], balanced['sizes']['16:9']), (30,81,(640,352)))
        self.assertEqual(quality['steps'], 50)
        self.assertEqual(base['sizes']['16:9'], (832,480))
        for profile in (draft,balanced,quality):
            self.assertEqual(profile['frames'] % 4, 1)
            self.assertTrue(all(w % 16 == h % 16 == 0 for w,h in profile['sizes'].values()))
            self.assertEqual(profile['dtype'], 'float32')
        with self.assertRaises(ValueError): motion_settings(base,'unbounded')

    def wait_done(self, jobs, ident):
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            result = jobs.snapshot(ident)
            if result['status'] not in ('queued', 'running'):
                return result
            time.sleep(.01)
        self.fail('Worker did not finish')

    def test_t4_avoids_bfloat16_and_small_gpu_is_not_advertised(self):
        self.assertEqual(motion_profile(14.7, 12.7, False)['dtype'], 'float32')
        self.assertTrue(motion_profile(14.7, 12.7, False)['available'])
        self.assertEqual(motion_profile(40, 80, True)['dtype'], 'bfloat16')
        self.assertFalse(motion_profile(8, 12, False)['available'])
        self.assertFalse(motion_profile(16, 8, False)['available'])

    def test_quality_profiles_and_explicit_override_guards(self):
        t4=motion_profile(14.7,12.7,False)
        self.assertIn('1.3B',t4['model']);self.assertEqual(t4['steps'],50)
        self.assertEqual(t4['flow_shift'],3)
        hd=motion_profile(40,80,True)
        self.assertIn('5B',hd['model']);self.assertEqual(hd['fps'],24)
        self.assertEqual(hd['frames'],121);self.assertEqual(hd['sizes']['16:9'],(1280,704))
        self.assertIsNone(hd['flow_shift'])
        self.assertEqual(motion_profile(40,80,True,'wan2.1','balanced')['steps'],30)
        self.assertIn('1.3B',motion_profile(40,12,True)['model'])
        for args in [(14.7,12.7,False,'wan2.2'),(40,80,False,'wan2.2'),(40,80,True,'unknown'),(40,80,True,'auto','invalid')]:
            with self.subTest(args=args),self.assertRaises(ValueError):
                motion_profile(*args)

    def test_polling_idempotency_busy_and_cancellation(self):
        started, release = threading.Event(), threading.Event()
        def generate(payload, progress):
            started.set()
            release.wait(3)
            progress('Step 1')
            return b'video'
        jobs = VideoJobs(generate)
        try:
            jobs.submit('one', {'prompt':'robot'})
            self.assertTrue(started.wait(2))
            self.assertEqual(jobs.submit('one', {'prompt':'robot'})['status'], 'running')
            with self.assertRaisesRegex(ValueError, 'already running'):
                jobs.submit('two', {})
            with self.assertRaisesRegex(ValueError, 'different request'):
                jobs.submit('one', {'prompt':'bird'})
            jobs.cancel('one')
            release.set()
            self.assertEqual(self.wait_done(jobs, 'one')['status'], 'cancelled')
            with self.assertRaises(ValueError):
                jobs.data('one')
        finally:
            release.set()
            jobs.pool.shutdown(wait=True)

    def test_completed_output_is_bounded_and_private_from_status(self):
        jobs = VideoJobs(lambda payload, progress: b'mp4 fixture')
        try:
            for number in range(10):
                ident = str(number)
                jobs.submit(ident, {'prompt':'topic'})
                self.assertEqual(self.wait_done(jobs, ident)['status'], 'completed')
            self.assertEqual(len(jobs.jobs), 8)
            self.assertEqual(jobs.data('9'), b'mp4 fixture')
            self.assertNotIn('data', jobs.snapshot('9'))
            self.assertNotIn('payload', jobs.snapshot('9'))
            self.assertEqual(jobs.cancel('9')['status'], 'completed')
        finally:
            jobs.pool.shutdown(wait=True)

    def test_provider_error_never_exposes_download(self):
        def generate(payload, progress):
            raise RuntimeError('GPU exhausted')
        jobs = VideoJobs(generate)
        try:
            jobs.submit('failed', {})
            result = self.wait_done(jobs, 'failed')
            self.assertEqual(result['status'], 'failed')
            self.assertEqual(result['error'], 'GPU exhausted')
            with self.assertRaises(ValueError):
                jobs.data('failed')
        finally:
            jobs.pool.shutdown(wait=True)


if __name__ == '__main__':
    unittest.main()
