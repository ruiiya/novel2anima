import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'database' / 'src'))
from n2m_db import apply_migrations, connect

SCRIPT = ROOT / 'tools' / 'novel2anima' / 'export_identity_prompts.py'


class ExportIdentityPromptTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / 'identity.db'
        con = connect(self.db)
        apply_migrations(con)
        con.execute("INSERT INTO universes(id,slug,display_name) "
                    "VALUES('universe:test','test_series','Test Series')")
        con.execute(
            "INSERT INTO characters(id,universe_id,slug,display_name,age_status,"
            "identity_json,identity_review) VALUES(?,?,?,?,?,?,?)",
            ('character:test:variant', 'universe:test', 'test_variant',
             'Test (variant) (Test Series)', 'CONFIRMED_ADULT',
             json.dumps({'danbooru_tag': 'test_(variant)_(test_series)',
                         'danbooru_copyright': 'test_series'}),
             'REVIEWED'))
        con.execute(
            "INSERT INTO characters(id,universe_id,slug,display_name,age_status,"
            "identity_json,identity_review) VALUES(?,?,?,?,?,?,?)",
            ('character:test:bare', 'universe:test', 'bare_original',
             'Bare Original', 'CONFIRMED_ADULT', '{}', 'REVIEWED'))
        for name, role in (('long_hair', 'APPEARANCE_CANDIDATE'),
                           ('blue_eyes', 'APPEARANCE_CANDIDATE'),
                           ('1girl', 'APPEARANCE_CANDIDATE'),
                           ('strapless_leotard', 'OUTFIT_CANDIDATE')):
            con.execute("INSERT INTO catalog_tags(id,namespace,name,category) "
                        "VALUES(?,?,?,0)", (f'tag:danbooru:{name}', 'danbooru', name))
            con.execute("INSERT INTO character_tags(character_id,tag_id,tag_role) "
                        "VALUES('character:test:variant',?,?)",
                        (f'tag:danbooru:{name}', role))
        con.commit()
        con.close()

    def tearDown(self):
        self.tmp.cleanup()

    def run_script(self, *args):
        out = Path(self.tmp.name) / 'out.jsonl'
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), '--db', str(self.db), '--out', str(out), *args],
            capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return [json.loads(line) for line in out.read_text(encoding='utf-8').splitlines()]

    def test_identity_and_outfit_become_anima_prompt(self):
        record = self.run_script('--character', 'test_variant')[0]
        self.assertEqual(record['identity_tag'], 'test (variant) (test series)')
        self.assertEqual(record['series_tag'], 'test series')
        self.assertEqual(record['subject'], '1girl')
        self.assertEqual(record['identity_anchors'], ['long hair', 'blue eyes'])
        self.assertEqual(record['outfit_tags'], ['strapless leotard'])
        self.assertEqual(
            record['prompt'],
            'masterpiece, best quality, score_7, safe, 1girl, solo, '
            'test (variant) (test series), test series, long hair, blue eyes, strapless leotard')

    def test_packet_mode_and_required_tag_groups(self):
        records = self.run_script('--mode', 'packet')
        self.assertEqual(len(records), 1)
        packet = records[0]
        self.assertEqual(packet['prompt'],
                         'test (variant) (test series), test series, long hair, blue eyes, strapless leotard')
        all_records = self.run_script('--mode', 'packet', '--include-empty')
        bare = next(r for r in all_records if r['slug'] == 'bare_original')
        self.assertIn('NO_IDENTITY_ANCHORS', bare['warnings'])
        self.assertIn('NO_OUTFIT_TAGS', bare['warnings'])
        self.assertEqual(
            [r['slug'] for r in self.run_script('--require-identity')], ['test_variant'])
        self.assertEqual(
            [r['slug'] for r in self.run_script('--require-outfit')], ['test_variant'])


if __name__ == '__main__':
    unittest.main()
