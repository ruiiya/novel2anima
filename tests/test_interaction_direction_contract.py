"""RED regression contracts: actor -> action -> target must survive planning, compilation, QA.

These tests are intentionally written for the *desired* behavior. They should fail
against the audited source until the interaction-orientation changes are merged.
"""
import copy
import json
import pathlib
import sqlite3
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'etl'))
import story_logic


def headpat_plan(actor='M', target='F', scoped=True):
    chars = [
        {'code': 'F', 'name': 'FemaleLead', 'gender': 'girl', 'identity_line': '1girl, blue hair',
         'identity_json': {}, 'outfit_json': {}},
        {'code': 'M', 'name': 'MaleFriend', 'gender': 'boy', 'identity_line': '1boy, black hair',
         'identity_json': {}, 'outfit_json': {}},
    ]
    shot = {
        'n': 1, 'phase': 'meet', 'participants': ['F', 'M'],
        'action': ['headpat'], 'expression': ['smile'], 'pose': ['standing'],
        'caption': 'A friendly moment.',
        'sequence': {'purpose': 'interaction', 'actor': actor, 'target': target,
                     'primaryAction': 'headpat', 'reactionRequired': False, 'eventId': 'meet:1'},
    }
    if scoped:
        shot['character_actions'] = {actor: ['headpat']}
        shot['character_targets'] = {actor: target}
    return {
        'project': {'title': 'DirectionalFixture', 'idea': 'greeting', 'content_profile': 'sfw',
                    'style_json': {}},
        'characters': chars,
        'act': {'act_no': 1, 'revision': 1, 'title': 'Greeting',
                'outline': 'Friendly greeting', 'status': 'draft'},
        'quality_line': 'masterpiece', 'safety_tag': 'safe',
        'shots': [shot], 'prompt_file': 'unused.txt',
    }


def codes(plan, spec=False):
    if spec:
        shot = plan['shots'][0]
        return {i.code for i in story_logic.validate_specs([(1, shot)]) if i.level == 'ERROR'}
    return {i.code for i in story_logic.validate_plan(plan) if i.level == 'ERROR'}


class RoleIntegrity(unittest.TestCase):
    def test_correct_male_to_female_passes(self):
        self.assertEqual(codes(headpat_plan()), set())

    def test_mirror_female_to_male_is_also_valid(self):
        self.assertEqual(codes(headpat_plan(actor='F', target='M')), set())

    def test_reversed_character_actions_is_blocked(self):
        plan = headpat_plan()
        s = plan['shots'][0]
        s['character_actions'] = {'F': ['headpat']}
        s['character_targets'] = {'F': 'M'}
        self.assertIn('INTERACTION_ROLE_MISMATCH', codes(plan))

    def test_role_mismatch_detected_again_on_compiled_spec(self):
        plan = headpat_plan()
        s = plan['shots'][0]
        s['character_actions'] = {'F': ['headpat']}
        s['character_targets'] = {'F': 'M'}
        self.assertIn('INTERACTION_ROLE_MISMATCH', codes(plan, spec=True))

    def test_missing_actor_scope_does_not_silently_pass(self):
        self.assertIn('INTERACTION_ACTOR_ACTION_MISSING', codes(headpat_plan(scoped=False)))

    def test_missing_target_on_directional_interaction_is_blocked(self):
        plan = headpat_plan()
        plan['shots'][0]['sequence'].pop('target')
        self.assertIn('INTERACTION_TARGET_REQUIRED', codes(plan))

    def test_target_must_be_visible_participant(self):
        plan = headpat_plan()
        plan['shots'][0]['participants'] = ['M']
        self.assertIn('INTERACTION_TARGET_NOT_IN_SHOT', codes(plan))

    def test_primary_action_must_match_scoped_actor_action(self):
        plan = headpat_plan()
        plan['shots'][0]['character_actions'] = {'M': ['waving']}
        self.assertIn('INTERACTION_PRIMARY_ACTION_MISMATCH', codes(plan))

    def test_character_target_must_match_sequence_target(self):
        plan = headpat_plan()
        plan['shots'][0]['character_targets'] = {'M': 'M'}
        self.assertIn('INTERACTION_TARGET_MISMATCH', codes(plan))


class CompilerIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='n2a-dir-tests-')
        cls.workdir = pathlib.Path(cls.tmp.name)
        cls.db = cls.workdir/'catalog.sqlite'
        con = sqlite3.connect(cls.db)
        con.executescript((ROOT/'sql/schema_v1.sql').read_text(encoding='utf8'))
        for mig in sorted((ROOT/'sql/migrations').glob('*.sql')):
            con.executescript(mig.read_text(encoding='utf8'))
        con.executemany('INSERT INTO tag(canonical_name,search_name) VALUES(?,?)',
                        [('headpat', 'headpat'), ('standing', 'standing'), ('smile', 'smile')])
        con.commit()
        con.close()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def seed(self, plan, name):
        plan['project']['title'] = 'Fixture-' + name
        plan['prompt_file'] = str(self.workdir / (name+'.txt'))
        src = self.workdir / (name+'.json')
        src.write_text(json.dumps(plan), encoding='utf8')
        res = subprocess.run([sys.executable, str(ROOT/'etl/seed_plan.py'), str(src),
                              '--db', str(self.db)], cwd=ROOT, text=True, capture_output=True)
        return res, pathlib.Path(plan['prompt_file'])

    def test_reverse_direction_is_rejected_before_database_write(self):
        plan = headpat_plan()
        s = plan['shots'][0]
        s['character_actions'] = {'F': ['headpat']}
        s['character_targets'] = {'F': 'M'}
        result, out = self.seed(plan, 'reverse-block')
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertFalse(out.exists())
        con = sqlite3.connect(self.db)
        self.assertIsNone(con.execute('SELECT 1 FROM project WHERE title=?',
                                      ('Fixture-reverse-block',)).fetchone())
        con.close()

    def test_correct_direction_is_prominent_in_compiled_prompt(self):
        result, out = self.seed(headpat_plan(), 'male-to-female')
        self.assertEqual(result.returncode, 0, result.stderr)
        prompt = out.read_text(encoding='utf8')
        # An unambiguous sentence, not only disconnected tags or the vague
        # "interacting with" phrase. Can be generalized if a new renderer has
        # an equally explicit directional serialization.
        self.assertIn('MaleFriend pats FemaleLead on the head', prompt)
        self.assertNotIn('FemaleLead: headpat', prompt)


if __name__ == '__main__':
    unittest.main()
