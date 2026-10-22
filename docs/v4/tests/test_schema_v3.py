"""Offline structural smoke tests on IN-MEMORY SQLite. Never touches a real DB."""
from pathlib import Path
import hashlib
import json
import sqlite3
import unittest

ROOT = Path(__file__).resolve().parents[1] / 'sql'
REFERENCE = ROOT / 'reference'
PROPOSALS = ROOT / 'proposals'
SQL_FILES = [REFERENCE / 'current_schema_20261022.sql', PROPOSALS / '005_db_first_DRAFT.sql', PROPOSALS / '006_normalization_DRAFT.sql']


def conn():
    c = sqlite3.connect(':memory:')
    c.execute('PRAGMA foreign_keys=ON')
    for f in SQL_FILES:
        c.executescript(f.read_text('utf-8'))
    return c


def seed(c):
    c.executemany('INSERT INTO project(id,title) VALUES (?,?)', [(1,'Alpha'),(2,'Beta')])
    c.executemany('INSERT INTO character_profile(id,project_id,code) VALUES (?,?,?)',
                  [(10,1,'alice'),(11,1,'bob'),(20,2,'eve')])
    c.execute("INSERT INTO act(id,project_id,act_no,title) VALUES (100,1,1,'Act')")
    c.executemany('INSERT INTO shot(id,act_id,shot_no) VALUES (?,?,?)', [(1000,100,1),(1001,100,2)])
    c.execute("INSERT INTO model_profile(id,code,model_name) VALUES (1,'anima','Anima')")
    c.execute("INSERT INTO outfit_revision(id,character_id,revision,spec_json,spec_sha256,status) VALUES (1,10,1,'{}',?, 'approved')", ('a'*64,))
    c.execute("INSERT INTO outfit_revision(id,character_id,revision,spec_json,spec_sha256,status) VALUES (2,11,1,'{}',?, 'approved')", ('b'*64,))
    c.execute("INSERT INTO shot_prompt_revision(id,shot_id,revision,positive_tags,negative_prompt,source_shot_spec_sha256,compiler_version,content_sha256) VALUES (1,1000,1,'headpat','',?,'c1',?)", ('c'*64,'d'*64))
    c.execute("INSERT INTO shot_prompt_revision(id,shot_id,revision,positive_tags,negative_prompt,source_shot_spec_sha256,compiler_version,content_sha256) VALUES (2,1001,1,'walk','',?,'c1',?)", ('e'*64,'f'*64))


class SqlContractTest(unittest.TestCase):
    def setUp(self):
        self.c = conn()
        seed(self.c)
    def tearDown(self):self.c.close()

    def test_schema_is_healthy(self):
        self.assertEqual(self.c.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
        self.assertEqual(self.c.execute('PRAGMA foreign_key_check').fetchall(), [])
        n=self.c.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchone()[0]
        self.assertGreaterEqual(n,45)

    def test_duo_actor_target_and_cross_project_rejection(self):
        self.c.executemany('INSERT INTO shot_participant(shot_id,character_id,slot_no) VALUES (1000,?,?)',[(10,1),(11,2)])
        self.c.execute("INSERT INTO shot_interaction(shot_id,actor_character_id,target_character_id,action_code) VALUES (1000,11,10,'headpat')")
        pair=self.c.execute('SELECT actor_character_id,target_character_id FROM shot_interaction').fetchone()
        self.assertEqual(pair,(11,10))
        with self.assertRaises(sqlite3.IntegrityError):
            self.c.execute("INSERT INTO shot_interaction(shot_id,actor_character_id,target_character_id,action_code,sort_order) VALUES (1000,10,20,'headpat',2)")
        with self.assertRaises(sqlite3.IntegrityError):
            self.c.execute('INSERT INTO shot_participant(shot_id,character_id,slot_no) VALUES (1000,20,3)')

    def test_outfit_character_and_participant_binding(self):
        self.c.execute('INSERT INTO shot_participant(shot_id,character_id,slot_no) VALUES (1000,10,1)')
        self.c.execute('INSERT INTO shot_outfit_binding VALUES (1000,10,1)')
        with self.assertRaises(sqlite3.IntegrityError):
            self.c.execute('INSERT INTO shot_outfit_binding VALUES (1000,11,1)')
        with self.assertRaises(sqlite3.IntegrityError):
            self.c.execute('INSERT INTO shot_outfit_binding VALUES (1001,11,2)')

    def test_generation_must_match_shot_prompt(self):
        self.c.execute("INSERT INTO generation(id,shot_id,model_profile_id,prompt) VALUES (99,1000,1,'headpat')")
        self.c.execute('INSERT INTO generation_provenance(generation_id,shot_prompt_revision_id) VALUES (99,1)')
        with self.assertRaises(sqlite3.IntegrityError):
            self.c.execute('UPDATE generation_provenance SET shot_prompt_revision_id=2 WHERE generation_id=99')

    def test_outfit_approved_immutable(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.c.execute("INSERT INTO outfit_item(outfit_revision_id,item_code,slot,garment_type) VALUES (1,'top','upper','shirt')")

    def test_frozen_shot_cannot_swap_participants_or_interactions(self):
        self.c.executemany('INSERT INTO shot_participant(shot_id,character_id,slot_no) VALUES (1000,?,?)',[(10,1),(11,2)])
        self.c.execute("INSERT INTO shot_interaction(shot_id,actor_character_id,target_character_id,action_code) VALUES (1000,11,10,'headpat')")
        self.c.execute("UPDATE shot SET status='approved' WHERE id=1000")
        with self.assertRaises(sqlite3.IntegrityError):
            self.c.execute('DELETE FROM shot_participant WHERE shot_id=1000 AND character_id=11')
        with self.assertRaises(sqlite3.IntegrityError):
            self.c.execute('UPDATE shot_interaction SET actor_character_id=10,target_character_id=11 WHERE shot_id=1000')

    def test_prompt_spec_same_shot(self):
        self.c.executemany("INSERT INTO shot_spec_revision(id,shot_id,revision,spec_json,spec_sha256) VALUES (?, ?, 1, '{}', ?)", [(10,1000,'a'*64),(11,1001,'b'*64)])
        self.c.execute('INSERT INTO shot_prompt_spec VALUES(1,10)')
        with self.assertRaises(sqlite3.IntegrityError):
            self.c.execute('INSERT INTO shot_prompt_spec VALUES(2,10)')

    def test_locked_revision_cannot_downgrade_and_edit(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.c.execute("UPDATE outfit_revision SET status='draft' WHERE id=1")
        self.c.execute("UPDATE outfit_revision SET status='retired' WHERE id=1")
        with self.assertRaises(sqlite3.IntegrityError):
            self.c.execute("UPDATE outfit_revision SET spec_json='{" + '"red":1' + "}' WHERE id=1")

    def test_invariant_revisions(self):
        self.c.execute("INSERT INTO character_identity_revision(character_id,revision,identity_json,sha256,status) VALUES (10,1,'{}',?, 'approved')",('a'*64,))
        with self.assertRaises(sqlite3.IntegrityError):
            self.c.execute("UPDATE character_identity_revision SET identity_json='{}',sha256=? WHERE character_id=10",('b'*64,))
        self.c.execute("INSERT INTO shot_spec_revision(shot_id,revision,spec_json,spec_sha256,status) VALUES (1000,1,'{}',?, 'approved')", ('a'*64,))
        with self.assertRaises(sqlite3.IntegrityError):
            self.c.execute("UPDATE shot_spec_revision SET spec_json='{" + '"test":1' + "}' WHERE shot_id=1000")

if __name__=='__main__': unittest.main()
