"""Tests for V4 packaging/contract shape, no source DB dependencies."""
from pathlib import Path
import csv
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]

class TestV4Packaging(unittest.TestCase):
    def test_prompt_placeholders_are_zero_byte(self):
        files=sorted((ROOT/'llm/prompts').rglob('*.txt'))
        self.assertEqual(len(files),33)
        self.assertTrue(all(p.stat().st_size==0 for p in files))

    def test_master_coverage(self):
        with (ROOT/'mappings/MASTER_MAPPING.csv').open(encoding='utf-8-sig',newline='') as f:rr=list(csv.DictReader(f))
        self.assertEqual(len(rr),121)
        self.assertEqual({k:sum(x['category']==k for x in rr) for k in ('SOURCE_FILE','LEGACY_DB_TABLE','EXTERNAL_RUNTIME')}, {'SOURCE_FILE':80,'LEGACY_DB_TABLE':23,'EXTERNAL_RUNTIME':18})
        self.assertEqual(len(set((x['category'],x['legacy_path_or_table']) for x in rr)),len(rr))

    def test_contract_schemas_are_json(self):
        for p in (ROOT/'llm/schemas').glob('*.json'):
            spec=json.loads(p.read_text(encoding='utf-8'))
            self.assertEqual(spec['type'],'object')
            self.assertEqual(spec['additionalProperties'],False)

    def test_inventory_is_readonly_of_source(self):
        from importlib.util import spec_from_file_location, module_from_spec
        spec=spec_from_file_location('inventory',ROOT/'tools/inventory_external_readonly.py')
        mod=module_from_spec(spec);spec.loader.exec_module(mod)
        with tempfile.TemporaryDirectory() as td:
            d=Path(td);(d/'data/plans').mkdir(parents=True);(d/'data/plans/a.json').write_text('{"story":1}',encoding='utf-8')
            original=(d/'data/plans/a.json').read_bytes()
            result=mod.build(d,True)
            self.assertEqual(result['file_count'],1)
            self.assertEqual((d/'data/plans/a.json').read_bytes(),original)
            self.assertEqual(len(result['items'][0]['sha256']),64)

    def test_staging_tool_on_copy(self):
        from importlib.util import spec_from_file_location, module_from_spec
        spec=spec_from_file_location('stage',ROOT/'tools/stage_migration_copy.py')
        mod=module_from_spec(spec);spec.loader.exec_module(mod)
        with tempfile.TemporaryDirectory() as td:
            src=Path(td)/'legacy.db';dst=Path(td)/'target.db'
            c=sqlite3.connect(src)
            c.executescript((ROOT/'sql/reference/current_schema_20261022.sql').read_text(encoding='utf-8'))
            c.execute("INSERT INTO project(id,title) VALUES (1,'test')")
            c.execute("INSERT INTO character_profile(id,project_id,code) VALUES (1,1,'alice')")
            c.execute("INSERT INTO act(id,project_id,act_no,title) VALUES (1,1,1,'act')")
            c.execute("INSERT INTO shot(id,act_id,shot_no,character_id) VALUES (1,1,1,1)")
            c.commit();c.close()
            result=mod.migrate_copy(str(src),str(dst))
            self.assertEqual(result['check']['quick_check'],'ok')
            self.assertEqual(result['check']['fk_violations_first_20'],[])
            a=sqlite3.connect(src)
            self.assertEqual(a.execute("SELECT COUNT(*) FROM sqlite_master WHERE name='shot_participant'").fetchone()[0],0)
            a.close()
            b=sqlite3.connect(dst)
            self.assertEqual(b.execute('SELECT COUNT(*) FROM shot_participant').fetchone()[0],1)
            b.close()
            with self.assertRaises(FileExistsError):mod.migrate_copy(str(src),str(dst))

if __name__=='__main__':unittest.main()
