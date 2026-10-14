import json
import unittest
from unittest.mock import Mock, patch
import studio
from production_agents import align_visuals


class VisualAlignmentTests(unittest.TestCase):
    def setUp(self):
        self.p=studio.Project(prompt='Explain machine learning',generation_mode='avatar',language='hi',
            scenes=[studio.Scene(text='कंप्यूटर तस्वीरों से सेब पहचानना सीखता है।',visual_prompt='A glowing computer on a desk')])

    def response(self, matched=True, prompt='', **extra):
        s=self.p.scenes[0]
        return {'scenes':[dict(scene_id=s.id,matched=matched,narration_quote=s.text,
            reason='Apple examples illustrate the narrated recognition task.',replacement_prompt=prompt,**extra)]}

    def align(self, chat, previous=None):
        return align_visuals(self.p,self.p.scenes,chat,Mock(),Mock(),previous)

    def test_hindi_mismatch_repairs_prompt_and_rechecks_without_changing_speech(self):
        original=self.p.model_dump()
        prompt='A table of apple example photographs beside one new apple photograph being compared, no text.'
        chat=Mock(side_effect=[self.response(False,prompt),self.response()])
        scenes,report=self.align(chat)
        self.assertEqual(chat.call_count,2)
        self.assertEqual(json.loads(chat.call_args.args[1])['scenes'][0]['visual_prompt'],prompt)
        self.assertEqual(scenes[0].visual_prompt,prompt)
        self.assertEqual(scenes[0].text,self.p.scenes[0].text)
        self.assertEqual(self.p.model_dump(),original)
        self.assertEqual(report['corrected_scene_ids'],[scenes[0].id])
        self.assertIn('pixels',report['scope'])

    def test_unchanged_review_reused_but_narration_style_and_prompt_invalidate_it(self):
        _,report=self.align(Mock(return_value=self.response()))
        chat=Mock(side_effect=AssertionError('Unchanged review should be reused'))
        self.align(chat,report);chat.assert_not_called()
        for change in ('text','visual_prompt','style'):
            with self.subTest(change=change):
                p=self.p.model_copy(deep=True)
                if change=='style': p.style='Anime'
                else: setattr(p.scenes[0],change,'Changed narration or image description')
                reply=self.response();reply['scenes'][0]['narration_quote']=p.scenes[0].text
                chat=Mock(return_value=reply)
                align_visuals(p,p.scenes,chat,Mock(),Mock(),report)
                chat.assert_called_once()

    def test_unresolved_mismatch_or_invalid_review_fails_bounded_and_preserves_original(self):
        for kind in ('mismatch','foreign_id','quote','extra','string_boolean'):
            reply=self.response(False,'Still unrelated abstract computer imagery') if kind=='mismatch' else self.response()
            v=reply['scenes'][0]
            if kind=='foreign_id': v['scene_id']='unknown'
            if kind=='quote': v['narration_quote']='Invented or translated words'
            if kind=='extra': v['text']='Rewritten narration is not allowed'
            if kind=='string_boolean': v['matched']='true'
            before=self.p.model_dump();chat=Mock(return_value=reply)
            with self.subTest(kind=kind),self.assertRaisesRegex(ValueError,'could not confirm'):
                self.align(chat)
            self.assertEqual(chat.call_count,2)
            self.assertEqual(self.p.model_dump(),before)

    def test_uploaded_media_and_no_text_do_not_trigger_invented_review(self):
        self.p.scenes[0].asset_id='a'*32
        chat=Mock();_,report=self.align(chat)
        chat.assert_not_called();self.assertEqual(report['status'],'not_applicable')
        self.p.scenes[0].asset_id='';self.p.narration=False;self.p.captions=False
        self.align(chat);chat.assert_not_called()

    def test_cancel_prevents_model_request(self):
        chat=Mock()
        with self.assertRaisesRegex(RuntimeError,'Cancelled'):
            align_visuals(self.p,self.p.scenes,chat,Mock(),Mock(side_effect=RuntimeError('Cancelled')))
        chat.assert_not_called()

    def test_failed_visual_regeneration_keeps_original_selected_media(self):
        self.p.scenes[0].asset_id='a'*32
        before=self.p.model_dump()
        with patch.object(studio,'chat',return_value=self.response(False,'Unrelated visual remains')),patch.object(studio,'event'),patch.object(studio,'checkpoint'),patch.object(studio,'image_asset') as image,patch.object(studio,'write_json') as save:
            with self.assertRaisesRegex(ValueError,'could not confirm'):
                studio.create_visual('test',self.p,self.p.scenes[0].id)
        image.assert_not_called();save.assert_not_called();self.assertEqual(self.p.model_dump(),before)


if __name__=='__main__':
    unittest.main()
