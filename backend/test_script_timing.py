import unittest
import json
from types import SimpleNamespace
from unittest.mock import Mock
import script_timing


class TimingTests(unittest.TestCase):
    def test_speech_budgets_reject_long_padding_and_balance_short_pauses(self):
        self.assertIsNone(script_timing.speech_budgets([2.5]*7,55))
        values=script_timing.speech_budgets([7,12,9,10,14],55)
        self.assertAlmostEqual(sum(values),55)
        self.assertTrue(all(0 <= b-s <= 1 for s,b in zip([7,12,9,10,14],values)))
        self.assertIsNone(script_timing.speech_budgets([20]*5,55))

    def test_frame_budgets_sum_exactly_to_target(self):
        p=SimpleNamespace(duration=20,scenes=[SimpleNamespace(start=0,end=n,speed=1) for n in (3,7,11)])
        values=script_timing.frame_budgets(p)
        self.assertAlmostEqual(sum(values),20)
        self.assertEqual(sum(round(x*30) for x in values),600)

    def test_forty_second_motion_budget_respects_clip_limits(self):
        values = script_timing.speech_budgets([4.7]*8,40,[6]*8)
        self.assertEqual(sum(round(x*30) for x in values),1200)
        self.assertTrue(all(x <= 6 for x in values))
        self.assertIsNone(script_timing.speech_budgets([7,4.3,4.3,4.3,4.3,4.3,4.3,4.3],40,[6]*8))
        self.assertIsNone(script_timing.speech_budgets([4]*8,40,[6]*8))

    def test_language_budgets_leave_time_for_pauses(self):
        self.assertEqual(script_timing.word_limit(20,'hi'),33)
        self.assertEqual(script_timing.word_limit(20,'en'),38)

    def test_long_avatar_targets_keep_every_frame(self):
        for seconds, count in ((60,8),(65,8),(180,12)):
            with self.subTest(seconds=seconds):
                p=SimpleNamespace(duration=seconds,scenes=[
                    SimpleNamespace(start=0,end=seconds/count,speed=1) for _ in range(count)])
                values=script_timing.frame_budgets(p)
                self.assertEqual(sum(round(x*30) for x in values),seconds*30)
                self.assertAlmostEqual(sum(values),seconds)

    def test_shortener_rejects_id_changes_and_over_budget_text(self):
        scene=SimpleNamespace(id='original',text='Original words')
        for reply in ({'scenes':[{'id':'wrong','text':'Test'}]}, {'scenes':[{'id':'original','text':'Too many words here'}]}):
            with self.assertRaises(ValueError):
                script_timing.shorten([scene],[2],'en',Mock(return_value=reply),'duration')

    def test_over_budget_rewrite_retries_once_without_changing_original(self):
        from studio import Scene
        scene=Scene(id='a'*32,text='Trees protect the riverbanks from soil erosion.',visual_prompt='Forest river')
        chat=Mock(side_effect=[{'scenes':[{'id':scene.id,'text':'This is still far too long'}]},
                               {'scenes':[{'id':scene.id,'text':'Trees protect riverbanks.'}]}])
        result=script_timing.shorten([scene],[3],'en',chat,'Fit 5 seconds.')
        self.assertEqual(chat.call_count,2)
        retry = json.loads(chat.call_args_list[1].args[1])
        self.assertEqual(retry['scenes'][0]['text'],'This is still far too long')
        self.assertEqual(retry['scenes'][0]['max_words'],3)
        self.assertEqual(result[0].text,'Trees protect riverbanks.')
        self.assertEqual(result[0].visual_prompt,scene.visual_prompt)
        self.assertEqual(scene.text,'Trees protect the riverbanks from soil erosion.')

    def test_repeated_over_budget_rewrite_is_bounded(self):
        scene=SimpleNamespace(id='original',text='Original words')
        chat=Mock(return_value={'scenes':[{'id':scene.id,'text':'Still much too long'}]})
        with self.assertRaises(ValueError):script_timing.shorten([scene],[2],'en',chat,'duration')
        self.assertEqual(chat.call_count,2)


if __name__ == '__main__':
    unittest.main()
