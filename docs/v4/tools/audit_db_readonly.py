#!/usr/bin/env python3
"""Read-only audit of an existing Novel2Anima SQLite DB. NO writes / migrations."""
import argparse
import datetime as dt
import json
import pathlib
import sqlite3

EXPECTED = [
 'source_snapshot','tag','tag_source','tag_alias','tag_role','tag_relation',
 'tag_content_label','visual_concept','concept_tag','concept_relation',
 'model_profile','project','character_profile','act','shot','generation',
 'shot_state','act_continuity','visual_concept_fts','shot_observation','act_observation',
 'act_publication','shot_finding'
]


def audit(db_path, full=False):
    p=pathlib.Path(db_path).resolve(strict=True)
    con=sqlite3.connect(p.as_uri() + '?mode=ro', uri=True)
    try:
        con.row_factory=sqlite3.Row
        schema={r['name'] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        result={
          'database':str(p), 'audited_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
          'size_bytes':p.stat().st_size, 'sqlite_version':sqlite3.sqlite_version,
          'missing_expected_tables':sorted(set(EXPECTED)-schema),
          'table_counts':{},'warnings':[], 'checks':{}
        }
        for table in EXPECTED:
            if table in schema:
                result['table_counts'][table]=con.execute('SELECT count(*) FROM "'+table+'"').fetchone()[0]
        mode='integrity_check' if full else 'quick_check'
        result['checks'][mode]=con.execute('PRAGMA '+mode).fetchone()[0]
        fk=con.execute('PRAGMA foreign_key_check').fetchmany(21)
        result['checks']['foreign_key_check_first_20']=[list(x) for x in fk[:20]]
        result['checks']['foreign_key_check_more_than_20']=(len(fk)>20)
        if 'shot' in schema and 'act' in schema and 'character_profile' in schema:
            result['checks']['shot_character_wrong_project']=con.execute('''
              SELECT count(*) FROM shot s
              JOIN act a ON a.id=s.act_id
              JOIN character_profile c ON c.id=s.character_id
              WHERE a.project_id<>c.project_id''').fetchone()[0]
            result['checks']['shot_missing_character_id']=con.execute(
                'SELECT count(*) FROM shot WHERE character_id IS NULL').fetchone()[0]
        if 'generation' in schema:
            result['checks']['generation_with_path_only']=con.execute('''
              SELECT count(*) FROM generation WHERE image_path IS NOT NULL AND length(trim(image_path))>0
              ''').fetchone()[0]
        if 'act_publication' in schema:
            result['checks']['legacy_file_publications']=con.execute('SELECT count(*) FROM act_publication').fetchone()[0]
        if 'tag' in schema:
            result['checks']['tags_without_category']=con.execute('SELECT count(*) FROM tag WHERE danbooru_category IS NULL').fetchone()[0]
        if result['missing_expected_tables']:result['warnings'].append('Some baseline tables are missing')
        if result['checks'].get(mode)!='ok':result['warnings'].append('SQLite integrity check failed')
        if fk:result['warnings'].append('Foreign key violations were found')
        if result['checks'].get('shot_character_wrong_project',0)>0:
            result['warnings'].append('Some shots reference characters from another project')
        return result
    finally:con.close()

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db',required=True,help='Real SQLite DB file (READ ONLY)')
    parser.add_argument('--full',action='store_true',help='Use more expensive integrity_check')
    parser.add_argument('--output',help='Optional report JSON path; database is never written')
    args=parser.parse_args()
    obj=audit(args.db,args.full)
    report=json.dumps(obj,ensure_ascii=False,indent=2)
    print(report)
    if args.output:pathlib.Path(args.output).write_text(report+'\n',encoding='utf-8')
