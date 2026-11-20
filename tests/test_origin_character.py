import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/novel2anima'))
sys.path.insert(0, str(ROOT / 'database/src'))

from n2m_db import connect, apply_migrations, create_story, add_role, bind_role
from origin_character import create_origin, revert_origin


class OriginCharacterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.con = connect(self.root / 'db.sqlite')
        self.addCleanup(self.con.close)
        apply_migrations(self.con)
        for name in ('black_hair', 'amber_eyes', 'mole_under_eye', 'black_tank_top'):
            self.con.execute("INSERT INTO catalog_tags(id,namespace,name) VALUES(?,?,?)",
                             (f'tag:danbooru:{name}', 'danbooru', name))
        self.con.execute('INSERT INTO universes(id,slug,display_name) VALUES(?,?,?)',
                         ('universe:blue_archive', 'blue_archive', 'Blue Archive'))
        self.source = 'character:storyaura_danbooru_csv:6b5d42323b39955b84'
        self.con.execute('''INSERT INTO characters(id,universe_id,slug,display_name,age_status,identity_json)
                            VALUES(?,?,?,?,?,?)''',
                         (self.source, 'universe:blue_archive', 'airi_band', 'airi (band)', 'UNKNOWN', '{}'))
        self.con.commit()

    def test_creates_reviewed_adult_origin_and_rebinds(self):
        story = create_story(self.con, 'S', 'NON_BLIND', 'text', ['nsfw'])
        role = add_role(self.con, story, 'LEAD', 'the lead')
        bind_role(self.con, story, 'LEAD', self.source)
        out = create_origin(self.con, self.source, 'lead_a', 'Lead A (original)',
                            ['black hair', 'amber eyes', 'mole under eye'],
                            ['black tank top'], review_id='RV-1', minor_check='AMBIGUOUS')
        bind_role(self.con, story, 'LEAD', out['origin_id'], out['outfit_id'])
        row = self.con.execute('SELECT age_status, identity_json FROM characters WHERE id=?',
                               (out['origin_id'],)).fetchone()
        self.assertEqual(row['age_status'], 'CONFIRMED_ADULT')
        self.assertEqual(json.loads(row['identity_json'])['replacement_mode'], 'user_approved_original')
        self.assertEqual(self.con.execute('SELECT age_status FROM characters WHERE id=?',
                                          (self.source,)).fetchone()[0], 'UNKNOWN')
        self.assertEqual(self.con.execute('''SELECT character_id FROM story_castings
                                             WHERE story_role_id=? AND until_revision IS NULL''',
                                          (role,)).fetchone()[0], out['origin_id'])

    def test_revert_swaps_role_back_and_keeps_origin(self):
        story = create_story(self.con, 'S', 'NON_BLIND', 'text', ['nsfw'])
        role = add_role(self.con, story, 'LEAD', 'the lead')
        bind_role(self.con, story, 'LEAD', self.source)
        out = create_origin(self.con, self.source, 'lead_a', 'Lead A', ['black hair'],
                            ['black tank top'], review_id='RV-2', minor_check='AMBIGUOUS')
        bind_role(self.con, story, 'LEAD', out['origin_id'], out['outfit_id'])
        plan = revert_origin(self.con, out['origin_id'], story, 'LEAD')
        bind_role(self.con, story, 'LEAD', plan['source_id'])
        self.assertEqual(self.con.execute('''SELECT character_id FROM story_castings
                                             WHERE story_role_id=? AND until_revision IS NULL''',
                                          (role,)).fetchone()[0], self.source)
        self.assertTrue(self.con.execute('SELECT 1 FROM characters WHERE id=?',
                                        (out['origin_id'],)).fetchone())

    def test_refuses_explicit_minor_and_unknown_tags(self):
        with self.assertRaisesRegex(ValueError, 'POLICY_BLOCKED'):
            create_origin(self.con, self.source, 'x', 'X', ['black hair'], ['black tank top'],
                          minor_check='EXPLICIT_MINOR')
        with self.assertRaisesRegex(ValueError, 'UNKNOWN_ANCHOR_TAGS'):
            create_origin(self.con, self.source, 'y', 'Y', ['neon rainbow hair'], ['black tank top'])

    def test_refuses_conflicting_hair_colours(self):
        self.con.execute("INSERT INTO catalog_tags(id,namespace,name) VALUES('tag:danbooru:brown_hair','danbooru','brown_hair')")
        with self.assertRaisesRegex(ValueError, 'CONFLICTING_ANCHORS'):
            create_origin(self.con, self.source, 'z', 'Z', ['black hair', 'brown hair'],
                          ['black tank top'])


if __name__ == '__main__':
    unittest.main()
