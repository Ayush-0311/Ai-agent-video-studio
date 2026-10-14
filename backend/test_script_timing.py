import unittest
from types import SimpleNamespace
from unittest.mock import Mock
import script_timing


class TimingTests(unittest.TestCase):
    def test_frame_budgets_sum_exactly_to_target(self):
        p=SimpleNamespace(duration=20,scenes=[SimpleNamespace(start=0,end=n,speed=1) for n in (3,7,11)])
        values=script_timing.frame_budgets(p)
        self.assertAlmostEqual(sum(values),20)
        self.assertEqual(sum(round(x*30) for x in values),600)

    def test_language_budgets_leave_time_for_pauses(self):
        self.assertEqual(script_timing.word_limit(20,'hi'),33)
        self.assertEqual(script_timing.word_limit(20,'en'),38)

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
