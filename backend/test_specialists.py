import json
import unittest
from unittest.mock import Mock, patch
import studio
from production_agents import SPECIALISTS, specialist_review, revise_text


class SpecialistTests(unittest.TestCase):
    def setUp(self):
        self.project = studio.Project(scenes=[studio.Scene(text='The pilot arrives.', end=6, speed=2),
                                             studio.Scene(text='The moon is quiet.', end=4)])

    def test_each_brief_is_scoped_and_does_not_mutate_media_or_text(self):
        self.project.language='hi'
        self.project.duration=55
        self.project.aspect_ratio='9:16'
        self.project.production_notes={'video_brief':{'audience':'Children','avoid':['Jargon']},
                                      'research':{'status':'retrieved','sources':[{'title':'Example reference'}]}}
        original = self.project.model_dump()
        instructions = []
        for agent in SPECIALISTS:
            with self.subTest(agent=agent):
                chat = Mock(return_value={'summary':'Professional review', 'findings':[
                    {'scene_id':self.project.scenes[1].id,'recommendation':'Use a wide composition.'}]})
                report = specialist_review(agent,self.project,chat,Mock())
                self.assertIn('findings', report)
                instructions.append(chat.call_args.args[0])
                brief=json.loads(chat.call_args.args[1])
                self.assertEqual(brief['scenes'][1]['output_start'],3)
                self.assertEqual(brief['video_brief']['audience'],'Children')
                self.assertEqual(brief['references']['status'],'retrieved')
                self.assertEqual(brief['selected_settings']['duration_seconds'],55)
                self.assertEqual(brief['selected_settings']['aspect_ratio'],'9:16')
                self.assertEqual(brief['selected_settings']['language'],'hi')
                self.assertEqual(self.project.model_dump(),original)
        self.assertEqual(len(set(instructions)),len(SPECIALISTS))

    def test_foreign_scene_id_repairs_once(self):
        chat=Mock(side_effect=[{'summary':'Review draft','findings':[{'scene_id':'wrong','recommendation':'Use a close-up.'}]},
                               {'summary':'Review repaired','findings':[{'scene_id':'','recommendation':'Use a close-up.'}]}])
        specialist_review('thumbnail_gen',self.project,chat,Mock())
        self.assertEqual(chat.call_count,2)
        self.assertIn('original scene ID',json.loads(chat.call_args.args[1])['validation_feedback'])

    def test_bad_reports_fail_bounded_and_cancel_does_not_call_model(self):
        chat=Mock(return_value={'summary':'empty','findings':[]})
        with self.assertRaisesRegex(ValueError,'twice'):
            specialist_review('seo_metadata',self.project,chat,Mock())
        self.assertEqual(chat.call_count,2)
        chat.reset_mock()
        with self.assertRaisesRegex(RuntimeError,'Cancelled'):
            specialist_review('seo_metadata',self.project,chat,Mock(side_effect=RuntimeError('Cancelled')))
        chat.assert_not_called()

    def test_translation_preserves_source_media_and_timing(self):
        self.project.scenes[0].media_kind='video'
        self.project.scenes[0].asset_id='a'*32
        reply={'scenes':[{'id':s.id,'text':'नमस्ते'} for s in self.project.scenes]}
        translated=revise_text(self.project,Mock(return_value=reply),Mock(),'hi')
        for original,result in zip(self.project.scenes,translated):
            self.assertEqual(original.model_dump(exclude={'text'}),result.model_dump(exclude={'text'}))
            self.assertEqual(result.text,'नमस्ते')
        optimized=revise_text(self.project,Mock(return_value=reply),Mock())
        self.assertEqual(optimized[0].text,self.project.scenes[0].text)

    def test_duplicate_revision_ids_and_empty_text_are_rejected(self):
        rows=[{'id':s.id,'text':'New narration'} for s in self.project.scenes]
        for bad in [rows+[rows[0]], [dict(row,text=' ') for row in rows]]:
            with self.subTest(bad=bad),self.assertRaisesRegex(ValueError,'twice'):
                revise_text(self.project,Mock(return_value={'scenes':bad}),Mock())

    def test_optimizer_and_translation_receive_language_timing_and_brief(self):
        self.project.language='hi'
        self.project.production_notes={'video_brief':{'tone':'Plain Hindi'},'research':{'status':'unavailable','sources':[]}}
        for language in (None,'es'):
            chat=Mock(return_value={'scenes':[{'id':s.id,'text':'Improved words.'} for s in self.project.scenes]})
            revise_text(self.project,chat,Mock(),language)
            request=json.loads(chat.call_args.args[1])
            self.assertEqual(request['target_language'],language or 'hi')
            self.assertEqual(request['video_brief']['tone'],'Plain Hindi')
            self.assertEqual(request['scenes'][0]['seconds'],3)
            self.assertEqual(request['references']['status'],'unavailable')

    def test_polish_preserves_brief_and_does_not_mutate_on_report_failure(self):
        self.project.production_notes={'video_brief':{'topic':'The moon'},'research':{'status':'retrieved'}}
        original=self.project.model_dump()
        draft={'scenes':[{'id':s.id,'text':'A revised sentence.'} for s in self.project.scenes]}
        for report in ([],{'seo':{'title':'Moon story'},'video_brief':{'topic':'Unrelated'}}):
            with patch.object(studio,'event'),patch.object(studio,'checkpoint'), \
                 patch.object(studio,'chat',side_effect=[draft,report]),patch.object(studio,'write_json') as save:
                if isinstance(report,list):
                    with self.assertRaisesRegex(ValueError,'Editorial report'):
                        studio.polish('test',self.project)
                    save.assert_not_called()
                else:
                    result=studio.polish('test',self.project)
                    self.assertEqual(result['production_notes']['video_brief'],{'topic':'The moon'})
                    save.assert_called_once()
            self.assertEqual(self.project.model_dump(),original)

    def test_agent_report_is_saved_without_overwriting_other_notes(self):
        self.project.production_notes={'agent_workflow':{'checks':['scene_ids']}}
        report={'summary':'Accurate title ideas','findings':[{'scene_id':'','recommendation':'Use a concise title.'}]}
        with patch.object(studio,'chat',return_value=report),patch.object(studio,'event'),patch.object(studio,'checkpoint'),patch.object(studio,'write_json') as save:
            result=studio.run_specialist('test',self.project,'seo_metadata')
        self.assertIn('agent_workflow',result['production_notes'])
        self.assertEqual(result['production_notes']['specialists']['seo_metadata'],report)
        self.assertEqual(result['scenes'],[s.model_dump() for s in self.project.scenes])
        save.assert_called_once()
        self.assertNotIn('specialists',self.project.production_notes)

    def test_invalid_agent_result_does_not_save(self):
        with patch.object(studio,'chat',return_value={}),patch.object(studio,'event'),patch.object(studio,'checkpoint'),patch.object(studio,'write_json') as save:
            with self.assertRaises(ValueError):studio.run_specialist('test',self.project,'seo_metadata')
        save.assert_not_called()

    def test_chapters_use_edit_speed_without_model(self):
        with patch.object(studio,'chat') as chat,patch.object(studio,'event'),patch.object(studio,'checkpoint'),patch.object(studio,'write_json'):
            result=studio.run_specialist('test',self.project,'chapter_marker')
        self.assertEqual(result['production_notes']['specialists']['chapter_marker']['chapters'][1]['start'],3)
        chat.assert_not_called()

    def test_request_rejects_unsupported_agents_and_language(self):
        for args in [dict(agent='lip_sync'),dict(agent='shell'),dict(agent='multi_language',language='unknown')]:
            with self.assertRaises(ValueError):studio.AgentRequest(project=self.project,**args)


if __name__ == '__main__':
    unittest.main()
