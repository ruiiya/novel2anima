import hashlib
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'database' / 'src'))
from n2m_db import (connect, apply_migrations, seed, create_story, add_role, bind_role,
                    save_natural_prompt, validate_natural_prompt, import_danbooru_tags,
                    export_bundle, export_story_prompts)
from n2m_workflow import (save_plan, add_act, add_beat, add_event,
                          save_shot, save_continuity, save_qa)

TEXT = ('sensitive, 1girl, solo, aria (original), silver hair, long hair, blue eyes, '
        'white blouse, navy skirt, standing, from side, cowboy shot, reading room, '
        'bookshelves, window, warm daylight\n'
        'Aria stands on the left and passes a notebook with her right hand to Noah, '
        'who sits on the right in a dark shirt and accepts it with a smile.')


class NaturalWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / 'novel.db'
        self.con = connect(self.db)
        apply_migrations(self.con)

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()

    def story(self, mode='BLIND'):
        story = create_story(self.con, 'Example', mode,
                             'Aria hands a notebook to Noah.', ['mature'])
        actor = add_role(self.con, story, 'LEAD')
        target = add_role(self.con, story, 'PARTNER_A')
        return story, actor, target

    def shot(self, story, key='S01', order=1, act_order=1, camera='medium'):
        plan = {'title': 'An illustrated story'}
        save_plan(self.con, story, plan)
        act = add_act(self.con, story, act_order, f'Act {act_order}', f'Sequence {act_order}')
        beat = add_beat(self.con, act, order, 'Meet')
        event = add_event(self.con, beat, 1, {'actor_role_key': 'LEAD',
                                              'target_role_key': 'PARTNER_A',
                                              'action': 'handing_object'})
        spec = {'participants': [{'role_key': 'LEAD'}, {'role_key': 'PARTNER_A'}],
                'interactions': [{'actor_role_key': 'LEAD', 'target_role_key': 'PARTNER_A',
                                  'action_text': 'passes notebook'}],
                'camera': camera, 'focus': 'notebook'}
        shot_id, revision = save_shot(self.con, beat, key, spec, event)
        return shot_id, beat, event, spec

    def test_migration_seven_and_idempotency(self):
        apply_migrations(self.con)
        versions = [x[0] for x in self.con.execute('SELECT version FROM schema_migrations ORDER BY version')]
        self.assertEqual(versions, ['001_init', '002_integrity', '003_history_guards',
                                    '004_catalog_enrichment', '005_db_boundary',
                                    '006_qa_history_guards', '007_natural_prompts', '008_visual_storytelling'])
        self.assertEqual(self.con.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
        self.assertEqual(list(self.con.execute('PRAGMA foreign_key_check')), [])
        self.assertEqual(self.con.execute('SELECT count(*) FROM shot_prompts').fetchone()[0], 0)
        self.assertNotIn('render_jobs', [r[0] for r in self.con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")])

    def test_seed_no_new_layout_templates(self):
        seed(self.con)
        self.assertEqual(self.con.execute('SELECT count(*) FROM vocabulary').fetchone()[0], 47)
        self.assertEqual(self.con.execute('SELECT count(*) FROM layout_templates').fetchone()[0], 0)
        seed(self.con)
        self.assertEqual(self.con.execute('SELECT count(*) FROM vocabulary').fetchone()[0], 47)

    def test_plain_natural_validation(self):
        self.assertEqual(validate_natural_prompt('  ' + TEXT + '  '), TEXT)
        self.assertEqual(validate_natural_prompt('sensitive, 1girl, solo\r\nA girl reads.'),
                         'sensitive, 1girl, solo\nA girl reads.')
        for prompt in ('', '  ', '```\nA cat\n```', '{"caption":"A cat"}',
                       '{"summary":{},"items":[]}', '\x00',
                       'A cat sits on a mat.',              # prose without a tag block
                       '1girl, solo, dark skin'):           # tag block without a safety tag
            with self.subTest(prompt=repr(prompt)), self.assertRaises(ValueError):
                validate_natural_prompt(prompt)
        with self.assertRaises(ValueError):
            validate_natural_prompt(TEXT, 'klingon')

    def test_blind_save_qa_and_export(self):
        story, actor, target = self.story()
        shot_id, beat, event, spec = self.shot(story)
        states = {'snapshots': [{'role_key': 'LEAD', 'before': {'holding': 'notebook'},
                                'delta': {'passes': 'notebook'}, 'after': {'holding': None}}]}
        self.assertEqual(save_continuity(self.con, shot_id, states),
                         save_continuity(self.con, shot_id, states))
        prompt_id, revision = save_natural_prompt(self.con, shot_id, TEXT)
        self.assertEqual(revision, 1)
        self.assertEqual(save_natural_prompt(self.con, shot_id, TEXT), (prompt_id, 1))
        qa = save_qa(self.con, 'PROMPT', prompt_id, 'PASS',
                     {'test': 'source/actor/outfit/camera checked'}, 'N2M-CONTENT-POLICY:1.3.0')
        self.assertEqual(qa, save_qa(self.con, 'PROMPT', prompt_id, 'PASS',
                                      {'test': 'source/actor/outfit/camera checked'},
                                      'N2M-CONTENT-POLICY:1.3.0'))
        folder = Path(self.tmp.name) / 'bundle'
        result = export_bundle(self.con, prompt_id, folder)
        self.assertEqual((folder / 'natural.prompt.txt').read_text(encoding='utf-8'), TEXT)
        self.assertFalse((folder / 'layout.prompt.json').exists())
        manifest = json.loads((folder / 'prompt.manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(manifest['story_id'], story)
        self.assertEqual(manifest['shot_id'], shot_id)
        self.assertEqual(manifest['format'], 'anima-tag-v1')
        self.assertEqual(manifest['prompt_sha256'], hashlib.sha256(TEXT.encode()).hexdigest())
        self.assertEqual(result['prompt_sha256'], manifest['prompt_sha256'])
        self.assertEqual(json.loads((folder / 'fidelity_report.json').read_text())['verdict'], 'PASS')
        self.con.execute("INSERT INTO characters(id,slug,display_name) VALUES('char:demo','demo','Demo')")
        self.con.commit()
        bind_role(self.con, story, 'LEAD', 'char:demo')
        persisted = self.con.execute('SELECT actor_role_id,target_role_id FROM story_events WHERE id=?', (event,)).fetchone()
        self.assertEqual(tuple(persisted), (actor, target))
        self.assertEqual(self.con.execute('SELECT count(*) FROM shot_prompts').fetchone()[0], 1)

    def test_revision_and_guards(self):
        story, _, _ = self.story()
        shot_id, _, _, _ = self.shot(story)
        one, _ = save_natural_prompt(self.con, shot_id, TEXT)
        two, revision = save_natural_prompt(self.con, shot_id, TEXT + ' A green tree outside.')
        self.assertEqual(revision, 2)
        self.assertEqual(self.con.execute('SELECT supersedes_prompt_id FROM shot_prompts WHERE id=?',
                                          (two,)).fetchone()[0], one)
        qa = save_qa(self.con, 'PROMPT', two, 'WARN', {'issue': 'underdetermined color'})
        for sql, params in [
            ('UPDATE shot_prompts SET prompt_text=? WHERE id=?', ('tampered', one)),
            ('DELETE FROM shot_prompts WHERE id=?', (one,)),
            ('UPDATE qa_reports SET verdict=? WHERE id=?', ('PASS', qa)),
            ('DELETE FROM qa_reports WHERE id=?', (qa,)),
            ('UPDATE story_sources SET raw_text=? WHERE story_id=?', ('overwrite', story)),
            ('DELETE FROM shots WHERE id=?', (shot_id,)),
        ]:
            with self.subTest(sql=sql), self.assertRaises(sqlite3.IntegrityError):
                self.con.execute(sql, params)
            self.con.rollback()

    def test_export_without_qa_reports_skip_not_pass(self):
        story, _, _ = self.story()
        shot_id, _, _, _ = self.shot(story)
        prompt, _ = save_natural_prompt(self.con, shot_id, TEXT)
        folder = Path(self.tmp.name) / 'unreviewed'
        export_bundle(self.con, prompt, folder)
        fidelity = json.loads((folder / 'fidelity_report.json').read_text())
        self.assertEqual(fidelity['verdict'], 'SKIP')

    def test_story_and_act_aggregate_string_prompts(self):
        story, _, _ = self.story()
        shot1, _, _, _ = self.shot(story, 'S01', 1, 1)
        shot2, _, _, _ = self.shot(story, 'S02', 2, 1)
        shot3, _, _, _ = self.shot(story, 'S03', 1, 2)
        for idx, shot_id in enumerate((shot1, shot2, shot3), 1):
            prompt_id, _ = save_natural_prompt(self.con, shot_id, TEXT + f' Scene {idx}.')
            save_qa(self.con, 'PROMPT', prompt_id, 'PASS', {'checked': True})
        out = Path(self.tmp.name) / 'all'
        result = export_story_prompts(self.con, story, out)
        self.assertEqual(result['shots'], 3)
        self.assertEqual(result['acts'], 2)
        all_text = (out / 'prompts.all.jsonl').read_text(encoding='utf-8')
        self.assertTrue(all_text.endswith('\n'))
        self.assertNotIn('\n\n\n', all_text)
        records = [json.loads(line) for line in all_text.splitlines() if line.strip()]
        self.assertEqual(len(records), 3)
        self.assertEqual([r['act'] for r in records], ['A01', 'A01', 'A02'])
        self.assertTrue(all(isinstance(r['prompt'], str) for r in records))
        self.assertTrue(all('bbox' not in r['prompt'] for r in records))
        self.assertEqual(len([x for x in (out / 'prompts/A01.jsonl').read_text().splitlines() if x.strip()]), 2)
        self.assertEqual(len([x for x in (out / 'prompts/A02.jsonl').read_text().splitlines() if x.strip()]), 1)
        self.assertEqual(len(list((out / 'bundles').rglob('natural.prompt.txt'))), 3)

    def test_export_story_refuses_missing_current_prompt(self):
        story, _, _ = self.story()
        shot_id, _, _, _ = self.shot(story)
        prompt_id, _ = save_natural_prompt(self.con, shot_id, TEXT)
        # Revised Shot makes the old prompt stale; never reuse silently.
        row = self.con.execute('SELECT * FROM shots WHERE id=?', (shot_id,)).fetchone()
        content = json.loads(row['shot_spec_json'])
        content['camera'] = 'closeup'
        newer, revision = save_shot(self.con, row['beat_id'], row['shot_key'], content,
                                     row['source_event_id'])
        self.assertEqual(revision, 2)
        with self.assertRaisesRegex(ValueError, 'Missing natural prompt'):
            export_story_prompts(self.con, story, Path(self.tmp.name) / 'incomplete')
        self.assertFalse((Path(self.tmp.name) / 'incomplete').exists())
        save_natural_prompt(self.con, newer, TEXT + ' Close-up framing.')
        result = export_story_prompts(self.con, story, Path(self.tmp.name) / 'complete')
        self.assertEqual(result['shots'], 1)


    def test_blocked_qa_refuses_bundle(self):
        story, _, _ = self.story()
        shot_id, *_ = self.shot(story)
        prompt_id, _ = save_natural_prompt(self.con, shot_id, TEXT)
        save_qa(self.con, 'PROMPT', prompt_id, 'BLOCKED', {'issue': 'missing action direction'})
        out = Path(self.tmp.name) / 'blocked'
        with self.assertRaisesRegex(ValueError, 'Blocked QA'):
            export_bundle(self.con, prompt_id, out)
        self.assertFalse(out.exists())

    def test_qa_only_active_subject_types(self):
        story, _, _ = self.story()
        with self.assertRaises(KeyError):
            save_qa(self.con, 'RENDER', 'none', 'PASS', {})
        with self.assertRaises(KeyError):
            save_qa(self.con, 'LAYOUT', 'none', 'PASS', {})

    def test_nonblind_casting(self):
        story, _, _ = self.story('NON_BLIND')
        self.con.execute("INSERT INTO characters(id,slug,display_name) VALUES('char:1','one','One')")
        self.con.commit()
        self.assertEqual(bind_role(self.con, story, 'LEAD', 'char:1'), 2)
        shot_id, *_ = self.shot(story)
        self.assertEqual(self.con.execute('SELECT count(*) FROM shot_participants WHERE shot_id=?',
                                          (shot_id,)).fetchone()[0], 2)

    def test_cross_story_fk_and_atomicity(self):
        story, _, _ = self.story()
        other, _, target_other = self.story('NON_BLIND')
        act = add_act(self.con, story, 1, 'Act')
        beat = add_beat(self.con, act, 1, 'Beat')
        with self.assertRaises(sqlite3.IntegrityError):
            self.con.execute('''INSERT INTO story_events(id,beat_id,event_order,actor_role_id,action)
                                VALUES(?,?,?,?,?)''', ('bad', beat, 1, target_other, 'test'))
        self.con.rollback()
        with self.assertRaises(ValueError):
            save_shot(self.con, beat, 'S01', {
                'participants': [{'role_key': 'LEAD'}],
                'interactions': [{'actor_role_key': 'LEAD', 'target_role_key': 'PARTNER_A',
                                  'action_text': 'waves'}]})
        self.assertEqual(self.con.execute('SELECT count(*) FROM shots').fetchone()[0], 0)

    def test_old_layout_qa_and_data_preserved_after_upgrade(self):
        legacy = Path(self.tmp.name) / 'old.db'
        with connect(legacy) as old:
            for f in sorted((ROOT / 'database/migrations').glob('00[1-6]_*.sql')):
                old.executescript(f.read_text(encoding='utf-8'))
            old.execute("INSERT INTO qa_reports(id,subject_kind,subject_id,verdict,report_json) VALUES('historical','LAYOUT','legacy-layout','WARN','{}')")
            old.execute("INSERT INTO stories(id,title,cast_mode) VALUES('old-story','Old','BLIND')")
            old.execute("INSERT INTO acts(id,story_id,act_order) VALUES('old-act','old-story',1)")
            old.execute("INSERT INTO beats(id,act_id,beat_order) VALUES('old-beat','old-act',1)")
            old.execute("INSERT INTO shots(id,beat_id,shot_key,shot_spec_json) VALUES('old-shot','old-beat','S1','{}')")
            old.execute("INSERT INTO shot_layouts(id,shot_id,width,height,summary_caption) VALUES('old-layout','old-shot',1024,1024,'Old caption')")
        check = connect(legacy)
        apply_migrations(check)
        self.assertEqual(check.execute("SELECT count(*) FROM shot_layouts WHERE id='old-layout'").fetchone()[0], 1)
        self.assertEqual(check.execute("SELECT count(*) FROM qa_reports WHERE id='historical'").fetchone()[0], 1)
        self.assertEqual(check.execute('SELECT count(*) FROM shot_prompts').fetchone()[0], 0)
        self.assertEqual(check.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
        check.close()

    def test_catalog_import_idempotency(self):
        seed(self.con)
        fixture = Path(self.tmp.name) / 'tags.json'
        fixture.write_text(json.dumps([{'id': 1, 'name': 'sitting', 'category': 0, 'post_count': 10}]),
                           encoding='utf-8')
        self.assertEqual(import_danbooru_tags(self.con, fixture), (1, 0))
        self.assertEqual(import_danbooru_tags(self.con, fixture), (0, 1))
        fixture.write_text(json.dumps([{'id': 1, 'name': 'sitting', 'category': 0, 'post_count': 30}]),
                           encoding='utf-8')
        import_danbooru_tags(self.con, fixture)
        self.assertEqual(self.con.execute('SELECT count(*) FROM source_record_versions').fetchone()[0], 2)


if __name__ == '__main__':
    unittest.main()
