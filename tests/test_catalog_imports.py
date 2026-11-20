import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'database' / 'src'))
from n2m_db import (apply_migrations, connect, parse_deepghs, import_deepghs,
                    search_catalog, create_story, add_role, bind_role)
from catalog_imports import (import_generic_outfits, import_pose_gallery,
                             import_tag_relations_json, import_tags_csv)


class CatalogImportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / 'catalog.db'
        self.con = connect(self.db)
        apply_migrations(self.con)

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()

    def write(self, name, text):
        path = Path(self.tmp.name) / name
        path.write_text(text, encoding='utf-8')
        return path

    def test_tags_csv_keeps_namespaces_and_does_not_create_character_aliases(self):
        danbooru = self.write('danbooru.csv',
            'long_hair,0,100,"longhair,long hair"\nasuna_(blue_archive),4,50,""\n')
        e621 = self.write('e621.csv',
            'long_hair,0,80,"longhair"\nmammal,5,70,"mammals"\n')
        first = import_tags_csv(self.con, danbooru, 'danbooru')
        self.assertEqual(first['new_tags'], 2)
        self.assertEqual(first['new_alias_relations'], 2)
        second = import_tags_csv(self.con, danbooru, 'danbooru')
        self.assertEqual(second['new_tags'], 0)
        self.assertEqual(second['new_alias_relations'], 0)
        other = import_tags_csv(self.con, e621, 'e621')
        self.assertEqual(other['new_tags'], 2)
        self.assertEqual(self.con.execute('SELECT count(*) FROM catalog_tags').fetchone()[0], 4)
        self.assertEqual(self.con.execute(
            "SELECT count(*) FROM catalog_tags WHERE namespace='danbooru' AND name='long_hair'"
        ).fetchone()[0], 1)
        self.assertEqual(self.con.execute(
            "SELECT count(*) FROM catalog_tags WHERE namespace='e621' AND name='long_hair'"
        ).fetchone()[0], 1)
        self.assertEqual(self.con.execute('SELECT count(*) FROM character_aliases').fetchone()[0], 0)
        self.assertEqual(self.con.execute(
            "SELECT label FROM catalog_tag_taxonomy WHERE namespace='danbooru' AND category=0"
        ).fetchone()[0], 'general')
        self.assertEqual(self.con.execute(
            "SELECT label FROM catalog_tag_taxonomy WHERE namespace='e621' AND category=5"
        ).fetchone()[0], 'species')
        alias = self.con.execute('''SELECT antecedent,consequent,status FROM catalog_tag_relations
                                     WHERE namespace='danbooru' AND relation_type='ALIAS'
                                     ORDER BY antecedent LIMIT 1''').fetchone()
        self.assertEqual(tuple(alias), ('long hair', 'long_hair', 'archive_unspecified'))

    def test_gz_headered_dump_and_relations_csv(self):
        import gzip

        def gz(name, text):
            path = Path(self.tmp.name) / name
            with gzip.open(path, 'wt', encoding='utf-8', newline='') as handle:
                handle.write(text)
            return path
        tags = gz('tags.csv.gz',
                  'id,name,category,post_count,created_at,updated_at,is_locked\n'
                  '1,dragon,5,478284,2020-01-01,2020-01-01,f\n'
                  '2,1girl,0,0,2020-01-01,2020-01-01,f\n')
        result = import_tags_csv(self.con, tags, 'e621')
        self.assertEqual(result['rows_processed'], 2)
        self.assertEqual(result['new_tags'], 2)
        self.assertEqual(result['new_alias_relations'], 0)
        self.assertEqual(self.con.execute(
            "SELECT label FROM catalog_tag_taxonomy WHERE namespace='e621' AND category=5"
        ).fetchone()[0], 'species')
        aliases = gz('aliases.csv.gz',
                     'id,antecedent_name,consequent_name,status\n'
                     '1,tits,breasts,active\n'
                     '2,old_name,breasts,deleted\n')
        rel = import_tag_relations_json(self.con, aliases, 'e621', 'alias')
        self.assertEqual(rel['new_relations'], 2)
        self.assertEqual(self.con.execute(
            "SELECT status FROM catalog_tag_relations WHERE antecedent='old_name'"
        ).fetchone()[0], 'deleted')

    def test_tags_csv_can_be_limited_to_character_core_tags(self):
        import_deepghs(self.con, ROOT / 'tests' / 'fixtures' / 'deepghs_sample.md')
        tags = self.write('core_tags.csv',
            'long_hair,0,100,"longhair"\nunrelated_tag,0,1,""\n')
        result = import_tags_csv(self.con, tags, 'danbooru',
                                 from_character_core_tags=True)
        self.assertEqual(result['selected_names'], 3)
        self.assertEqual(result['rows_processed'], 1)
        self.assertEqual(self.con.execute(
            "SELECT count(*) FROM catalog_tags WHERE name='unrelated_tag'").fetchone()[0], 0)
        self.assertEqual(self.con.execute(
            "SELECT post_count FROM catalog_tags WHERE name='long_hair'").fetchone()[0], 100)

    def test_tag_relations_json_alias_and_implication(self):
        aliases = self.write('aliases.json', json.dumps([
            {'antecedent_name': 'longhair', 'consequent_name': 'long_hair',
             'status': 'active'}]))
        result = import_tag_relations_json(self.con, aliases, 'danbooru', 'alias')
        self.assertEqual(result['new_relations'], 1)
        self.assertEqual(import_tag_relations_json(
            self.con, aliases, 'danbooru', 'alias')['new_relations'], 0)
        implications = self.write('implications.json', json.dumps({
            'tag_implications': [
                {'antecedent_name': 'long_hair', 'consequent_name': 'hair'}]}))
        result = import_tag_relations_json(self.con, implications, 'e621', 'implication')
        self.assertEqual(result['new_relations'], 1)
        row = self.con.execute('''SELECT relation_type,status FROM catalog_tag_relations
                                  WHERE namespace='e621' AND antecedent='long_hair' ''').fetchone()
        self.assertEqual(tuple(row), ('IMPLIES', 'active'))

    def test_pose_gallery_groups_views_and_is_idempotent(self):
        items = [
            {'id': 'p1_front', '体系': 'solo', '姿势编号': 'P001', '分类': 'standing',
             '姿势名称': 'stand A', '角度': 'front', '缩略图': 'thumbs/p1_front.jpg',
             '原图': 'img/p1_front.png'},
            {'id': 'p1_side', '体系': 'solo', '姿势编号': 'P001', '分类': 'standing',
             '姿势名称': 'stand A', '角度': 'side', '缩略图': 'thumbs/p1_side.jpg',
             '原图': 'img/p1_side.png'},
            {'id': 'p2_front', '体系': 'solo', '姿势编号': 'P002', '分类': 'sitting',
             '姿势名称': 'sit B', '角度': 'front', '缩略图': 'thumbs/p2_front.jpg',
             '原图': 'img/p2_front.png'},
        ]
        path = self.write('pose.json', json.dumps(items, ensure_ascii=False))
        first = import_pose_gallery(self.con, path)
        self.assertEqual(first['pose_groups'], 2)
        self.assertEqual(first['new_poses'], 2)
        self.assertEqual(first['new_views'], 3)
        self.assertEqual(first['new_captions'], 2)
        second = import_pose_gallery(self.con, path)
        self.assertEqual(second['new_poses'], 0)
        self.assertEqual(second['new_views'], 0)
        self.assertEqual(self.con.execute('SELECT count(*) FROM catalog_assets').fetchone()[0], 0)
        row = self.con.execute('''SELECT vocabulary_id,caption_lang,caption_review,category
                                  FROM pose_references WHERE pose_code='P001' ''').fetchone()
        self.assertIsNone(row['vocabulary_id'])
        self.assertEqual(tuple(row)[1:], ('zh', 'UNREVIEWED', 'standing'))
        views = self.con.execute('''SELECT count(*) FROM pose_reference_views v
                                    JOIN pose_references p ON p.id=v.pose_reference_id
                                    WHERE p.pose_code='P001' ''').fetchone()[0]
        self.assertEqual(views, 2)
        self.assertEqual(self.con.execute('SELECT count(*) FROM characters').fetchone()[0], 0)
        self.assertEqual(self.con.execute('SELECT count(*) FROM outfits').fetchone()[0], 0)

    def test_generic_outfits_never_create_characters_or_canon(self):
        outfits = self.write('costumes.json', json.dumps([
            {'id': 'SPR-1', '服装名称': 'white shirt', '标签': ['white', 'shirt'],
             '关键词': 'white shirt', '缩略图': 'thumbs/1.webp', '原图': 'img/1.webp'},
            {'id': 'SPR-2', '服装名称': 'black skirt', '标签': ['black', 'skirt'],
             '关键词': 'black skirt', '缩略图': 'thumbs/2.webp', '原图': 'img/2.webp'},
        ], ensure_ascii=False))
        first = import_generic_outfits(self.con, outfits)
        self.assertEqual(first['new_outfits'], 2)
        self.assertEqual(first['new_parts'], 2)
        self.assertEqual(first['new_captions'], 4)
        second = import_generic_outfits(self.con, outfits)
        self.assertEqual(second['new_outfits'], 0)
        self.assertEqual(self.con.execute('SELECT count(*) FROM outfits').fetchone()[0], 2)
        self.assertEqual(self.con.execute(
            "SELECT count(*) FROM outfits WHERE outfit_kind!='GENERIC' OR character_id IS NOT NULL"
        ).fetchone()[0], 0)
        self.assertEqual(self.con.execute(
            "SELECT count(*) FROM outfits WHERE verification!='UNVERIFIED'"
        ).fetchone()[0], 0)
        charadb = self.write('charadb.json', json.dumps([
            {'id': 'O001', 'jp': 'セーラー服', 'tags': 'serafuku, pleated skirt'}]))
        result = import_generic_outfits(self.con, charadb, source_id='charadb')
        self.assertEqual(result['new_outfits'], 1)
        self.assertEqual(self.con.execute('SELECT count(*) FROM characters').fetchone()[0], 0)
        self.assertEqual(self.con.execute('SELECT count(*) FROM catalog_assets').fetchone()[0], 0)

    def test_search_catalog_finds_imported_metadata(self):
        tags = self.write('search_tags.csv', 'long_hair,0,100,"longhair"\n')
        import_tags_csv(self.con, tags, 'danbooru')
        self.assertEqual(search_catalog(self.con, 'tag', 'long', namespace='danbooru')[0]['name'],
                         'long_hair')
        pose = self.write('search_pose.json', json.dumps([
            {'id': 'p1', '体系': 'solo', '姿势编号': 'P001', '分类': 'standing',
             '姿势名称': 'stand A', '角度': 'front', '缩略图': 't.jpg', '原图': 'o.png'}]))
        import_pose_gallery(self.con, pose)
        self.assertEqual(search_catalog(self.con, 'pose', 'P001')[0]['pose_code'], 'P001')
        outfit = self.write('search_outfit.json', json.dumps([
            {'id': 'O1', '服装名称': 'sailor uniform', '关键词': 'serafuku'}]))
        import_generic_outfits(self.con, outfit)
        self.assertEqual(search_catalog(self.con, 'outfit', 'sailor')[0]['outfit_kind'], 'GENERIC')
        self.assertEqual(search_catalog(self.con, 'action', 'head_pat')[0]['code'], 'head_pat')

    def test_imported_character_is_consumer_ready_for_casting(self):
        self.assertEqual(search_catalog(self.con, 'character', 'alpha'), [])
        import_deepghs(self.con, ROOT / 'tests' / 'fixtures' / 'deepghs_sample.md')
        result = search_catalog(self.con, 'character', 'alpha')
        self.assertEqual(len(result), 1)
        character_id = result[0]['id']
        story = create_story(self.con, 'Consumer test', 'NON_BLIND',
                             'A simple scene.', ['original'])
        role_id = add_role(self.con, story, 'LEAD')
        self.assertEqual(bind_role(self.con, story, 'LEAD', character_id), 2)
        row = self.con.execute('''SELECT character_id FROM story_castings
                                  WHERE story_role_id=? AND until_revision IS NULL''',
                               (role_id,)).fetchone()
        self.assertEqual(row['character_id'], character_id)

    def test_deepghs_fixture_is_conservative_and_idempotent(self):
        fixture = ROOT / 'tests' / 'fixtures' / 'deepghs_sample.md'
        parsed = list(parse_deepghs(fixture.read_text(encoding='utf-8')))
        self.assertEqual(len(parsed), 2)
        self.assertEqual(parsed[0][0], 'sample_series')
        self.assertEqual(parsed[0][1], 'alpha_(sample_series)')
        self.assertEqual(parsed[1][1], 'beta_(bunny)_(sample_series)')
        self.assertEqual(import_deepghs(self.con, fixture), (2, 0))
        self.assertEqual(import_deepghs(self.con, fixture), (0, 2))
        self.assertEqual(self.con.execute('SELECT count(*) FROM characters').fetchone()[0], 2)
        self.assertEqual(self.con.execute('SELECT count(*) FROM outfits').fetchone()[0], 0)
        self.assertEqual(self.con.execute(
            "SELECT count(*) FROM characters WHERE age_status!='UNKNOWN' OR identity_review!='UNVERIFIED'"
        ).fetchone()[0], 0)
        self.assertEqual(self.con.execute(
            "SELECT count(*) FROM character_tags WHERE tag_role!='CORE_CANDIDATE'"
        ).fetchone()[0], 0)
        self.assertEqual(self.con.execute(
            "SELECT count(*) FROM catalog_tags WHERE original_name IS NULL"
        ).fetchone()[0], 0)


if __name__ == '__main__':
    unittest.main()
