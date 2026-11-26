"""V6 Studio regression: real DB, gate ordering, pinned prompt exports and feedback."""
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'database'/'src'))
from n2m_db import connect,apply_migrations,create_story,export_story_prompts
from n2m_workflow import save_plan
from n2m_storyboard import save_storyboard,seal_storyboard
from n2a_studio import (submit, review_decision, get_status, list_stories, latest,
                        valid_approval, report_feedback, resolve_feedback,studio_export)
import test_visual_storyboard as legacy

REVIEW={'verdict':'PASS','evidence':'Story source, actors, continuity and stage reviewed with concrete evidence'}
DOC={'research_summary':'References and creative direction have been checked',
     'visual_bible':{'characters':{},'locations':{},'styles':{},'props':{}},
     'references':[{'kind':'user_story','value':'story reference'}]}


class StudioV6Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.con=connect(self.root/'studio.sqlite')
        self.addCleanup(self.con.close)
        apply_migrations(self.con)

    def make_story(self):
        story=create_story(self.con,'Studio V6','BLIND','Two people exchange a book',[])
        save_plan(self.con,story,{'approval':{'status':'APPROVED','evidence':'historical story flag'},
                                  'acts':[{'name':'Scene 1'}]})
        return story

    def approve(self,story,stage,payload=None):
        a=submit(self.con,story,stage,REVIEW,payload)
        review_decision(self.con,story,stage,'APPROVED','User explicitly accepted stage',True)
        return a

    def test_stages_require_human_and_prior_confirmation(self):
        story=self.make_story()
        with self.assertRaisesRegex(ValueError,'PREREQUISITE'):
            submit(self.con,story,'RESEARCH_VISUAL',REVIEW,DOC)
        first=submit(self.con,story,'STORY',REVIEW)
        self.assertEqual(first['status'],'READY_FOR_REVIEW')
        with self.assertRaisesRegex(ValueError,'EXPLICIT_USER'):
            review_decision(self.con,story,'STORY','APPROVED','Implicit',False)
        self.assertEqual(first['artifact_id'],submit(self.con,story,'STORY',REVIEW)['artifact_id'])
        review_decision(self.con,story,'STORY','APPROVED','User said chốt',True)
        with self.assertRaisesRegex(ValueError,'DECISION_ALREADY'):
            review_decision(self.con,story,'STORY','APPROVED','same',True)
        self.approve(story,'RESEARCH_VISUAL',DOC)
        self.assertTrue(valid_approval(self.con,latest(self.con,story,'RESEARCH_VISUAL')))
        self.assertEqual(get_status(self.con,story)['next_stage'],'STORYBOARD')

    def test_story_change_invalidates_entire_approval_chain(self):
        story=self.make_story()
        self.approve(story,'STORY')
        self.approve(story,'RESEARCH_VISUAL',DOC)
        old=latest(self.con,story,'STORY')['revision']
        save_plan(self.con,story,{'approval':{'status':'APPROVED','evidence':'user revised'},'acts':[{'name':'New'}]},old)
        status=get_status(self.con,story)
        self.assertEqual(status['stages'][0]['status'],'STALE')
        self.assertEqual(status['stages'][1]['status'],'STALE')
        self.assertEqual(status['next_stage'],'STORY')
        with self.assertRaisesRegex(ValueError,'PREREQUISITE'):
            submit(self.con,story,'RESEARCH_VISUAL',REVIEW,DOC)
        self.approve(story,'STORY')
        self.approve(story,'RESEARCH_VISUAL',DOC)
        self.assertEqual(get_status(self.con,story)['next_stage'],'STORYBOARD')

    def test_review_and_user_changes_requested(self):
        story=self.make_story()
        submit(self.con,story,'STORY',REVIEW)
        review_decision(self.con,story,'STORY','CHANGES_REQUESTED','Please revise ending',True)
        self.assertEqual(get_status(self.con,story)['stages'][0]['status'],'CHANGES_REQUESTED')
        with self.assertRaisesRegex(ValueError,'DECISION_ALREADY'):
            review_decision(self.con,story,'STORY','APPROVED','Cannot change earlier decision',True)
        save_plan(self.con,story,{'approval':{'status':'APPROVED','evidence':'user review'},'new':True})
        self.approve(story,'STORY')
        self.assertEqual(get_status(self.con,story)['stages'][0]['status'],'APPROVED')

    def full_story(self):
        story,board=legacy.VisualStoryboardTests.fixture(self)
        self.approve(story,'STORY')
        self.approve(story,'RESEARCH_VISUAL',DOC)
        bid,_=save_storyboard(self.con,story,board)
        self.approve(story,'STORYBOARD')
        sealed=legacy.VisualStoryboardTests.materialize(self,bid)
        seal_storyboard(self.con,bid,sealed)
        self.approve(story,'PROMPTS')
        return story,board,bid,sealed

    def test_full_story_export_pinned_and_manifest(self):
        story,board,bid,seal=self.full_story()
        self.assertEqual(get_status(self.con,story)['next_stage'],'COMPLETED')
        result=studio_export(self.con,story,self.root/'export')
        self.assertEqual(result['shots'],2)
        manifest=json.loads((self.root/'export'/'studio.manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(manifest['storyboard_id'],bid)
        self.assertEqual({p['shot_key'] for p in manifest['prompts']},{'S2','S10'})
        output=(self.root/'export'/'prompts.all.jsonl').read_text(encoding='utf-8')
        self.assertLess(output.index('"shot_key":"S2"'),output.index('"shot_key":"S10"'))
        self.assertEqual(len(list(self.con.execute('SELECT * FROM studio_exports'))),1)

    def test_no_export_before_approval_for_all_entrypoints(self):
        story,board=legacy.VisualStoryboardTests.fixture(self)
        self.approve(story,'STORY')
        self.approve(story,'RESEARCH_VISUAL',DOC)
        bid,_=save_storyboard(self.con,story,board)
        self.approve(story,'STORYBOARD')
        sealed=legacy.VisualStoryboardTests.materialize(self,bid)
        seal_storyboard(self.con,bid,sealed)
        with self.assertRaisesRegex(ValueError,'APPROVAL'):
            studio_export(self.con,story,self.root/'notyet')
        with self.assertRaisesRegex(ValueError,'APPROVAL'):
            export_story_prompts(self.con,story,self.root/'legacy-bypass')
        self.approve(story,'PROMPTS')
        export_story_prompts(self.con,story,self.root/'legacy-approved')

    def test_feedback_and_reseal_invalidate_prompt_approval(self):
        story,board,bid,sealed=self.full_story()
        result=report_feedback(self.con,story,'S2','Sai trang phục trong ảnh thực tế')
        self.assertEqual(result['affected_shot_keys'],['S10','S2'])
        self.assertEqual(get_status(self.con,story)['open_feedback'],1)
        with self.assertRaisesRegex(ValueError,'FEEDBACK_REQUIRES_NEW_PROMPT'):
            resolve_feedback(self.con,result['feedback_id'],sealed['bindings']['S2']['prompt_id'],'No change')
        fresh_bid,revision=save_storyboard(self.con,story,board,force_new_revision=True)
        self.assertNotEqual(bid,fresh_bid)
        self.assertEqual(revision,2)
        self.assertEqual(get_status(self.con,story)['stages'][2]['status'],'STALE')
        self.assertEqual(get_status(self.con,story)['stages'][3]['status'],'STALE')
        with self.assertRaisesRegex(ValueError,'APPROVAL'):
            studio_export(self.con,story,self.root/'stale')

    def test_feedback_points_to_exported_edition_not_new_unsealed_draft(self):
        story,board,bid,sealed=self.full_story()
        studio_export(self.con,story,self.root/'published')
        new_id,_=save_storyboard(self.con,story,board,force_new_revision=True)
        self.assertNotEqual(new_id,bid)
        ticket=report_feedback(self.con,story,'S2','Trang đã export sai thông tin')
        row=self.con.execute('SELECT * FROM studio_feedback WHERE id=?',
                             (ticket['feedback_id'],)).fetchone()
        self.assertEqual(row['storyboard_id'],bid)

    def test_research_provenance_is_required(self):
        story=self.make_story()
        self.approve(story,'STORY')
        with self.assertRaisesRegex(ValueError,'PROVENANCE'):
            submit(self.con,story,'RESEARCH_VISUAL',REVIEW,
                   {'research_summary':'recheck','visual_bible':{}})

    def test_new_prompt_revision_revokes_approval_until_reseal(self):
        story,board,bid,sealed=self.full_story()
        shot=sealed['bindings']['S2']['shot_id']
        from n2m_db import save_natural_prompt
        save_natural_prompt(self.con,shot,
            'safe, 2girls, full body, from side, indoors\nA and B exchange a notebook.')
        self.assertEqual(get_status(self.con,story)['stages'][3]['status'],'STALE')
        with self.assertRaisesRegex(ValueError,'APPROVAL'):
            studio_export(self.con,story,self.root/'bypass')

    def test_multiple_stories_stay_isolated(self):
        a=self.make_story();b=self.make_story()
        self.approve(a,'STORY')
        data=list_stories(self.con)
        self.assertEqual(len(data),2)
        states={x['story']['id']:x['next_stage'] for x in data}
        self.assertEqual(states[a],'RESEARCH_VISUAL')
        self.assertEqual(states[b],'STORY')

    def test_artifacts_immutable_and_migration_repeatable(self):
        story=self.make_story();a=submit(self.con,story,'STORY',REVIEW)
        with self.assertRaises(sqlite3.DatabaseError):
            with self.con:
                self.con.execute("UPDATE studio_artifacts SET artifact_json='{}' WHERE id=?",(a['artifact_id'],))
        apply_migrations(self.con)
        count=self.con.execute("SELECT COUNT(*) FROM schema_migrations WHERE version='011_studio_process'").fetchone()[0]
        self.assertEqual(count,1)


if __name__=='__main__':unittest.main()
