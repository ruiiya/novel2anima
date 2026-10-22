#!/usr/bin/env python3
"""Build a TEST copy of the legacy DB and stage the additive V3 schema; never modifies input."""
import argparse
import hashlib
import json
import pathlib
import sqlite3

SQL_DIR=pathlib.Path(__file__).resolve().parents[1]/'sql'/'proposals'


def digest(payload):return hashlib.sha256(payload.encode('utf-8')).hexdigest()


def migrate_copy(source, target):
    src=pathlib.Path(source).resolve(strict=True)
    dst=pathlib.Path(target).resolve()
    if src==dst:raise ValueError('Source and target DB must be different')
    if dst.exists():raise FileExistsError('Target exists; refuse overwrite: '+str(dst))
    dst.parent.mkdir(parents=True,exist_ok=True)
    # Backup API handles a source database running in WAL mode consistently.
    cin=sqlite3.connect(src.as_uri()+'?mode=ro',uri=True)
    cout=sqlite3.connect(str(dst))
    try:cin.backup(cout)
    finally:cin.close()
    try:
        cout.execute('PRAGMA foreign_keys=ON')
        for name in ('005_db_first_DRAFT.sql','006_normalization_DRAFT.sql'):
            sql=(SQL_DIR/name).read_text(encoding='utf-8')
            cout.executescript(sql)
            cout.execute('INSERT OR IGNORE INTO n2a_schema_migration(version,sha256) VALUES (?,?)',
                        (name,digest(sql)))
            cout.commit()
        audit={'source':str(src),'staging_db':str(dst),'backfilled':{},'manual_reconciliation':[]}
        # Use an explicit transaction for all deterministic backfills.
        cout.execute('BEGIN IMMEDIATE')
        identity=outfits=specs=participants=relation_sources=0
        for cid, ident, outf in cout.execute('SELECT id,identity_json,outfit_json FROM character_profile'):
            if not cout.execute('SELECT 1 FROM character_identity_revision WHERE character_id=?',(cid,)).fetchone():
                cout.execute("INSERT INTO character_identity_revision(character_id,revision,identity_json,sha256,status) VALUES(?,1,?,?,'draft')",
                             (cid,ident,digest(ident)))
                identity+=1
            if outf and outf.strip() not in ('','{}') and not cout.execute(
                'SELECT 1 FROM outfit_revision WHERE character_id=?',(cid,)).fetchone():
                cout.execute("INSERT INTO outfit_revision(character_id,revision,spec_json,spec_sha256,status) VALUES(?,1,?,?,'draft')",
                             (cid,outf,digest(outf)))
                outfits+=1
        for sid,spec,cid,project_id,char_project in cout.execute('''
            SELECT s.id,s.shot_spec_json,s.character_id,a.project_id,c.project_id
            FROM shot s JOIN act a ON a.id=s.act_id
            LEFT JOIN character_profile c ON c.id=s.character_id'''):
            if not cout.execute('SELECT 1 FROM shot_spec_revision WHERE shot_id=?',(sid,)).fetchone():
                cout.execute("INSERT INTO shot_spec_revision(shot_id,revision,spec_json,spec_sha256,status) VALUES(?,1,?,?,'draft')",
                             (sid,spec,digest(spec)))
                specs+=1
            if cid is not None:
                if project_id==char_project:
                    cout.execute('INSERT OR IGNORE INTO shot_participant(shot_id,character_id,slot_no) VALUES (?, ?,1)',(sid,cid))
                    participants+=cout.execute('SELECT changes()').fetchone()[0]
                else:
                    audit['manual_reconciliation'].append({'shot_id':sid,'type':'wrong_project_or_missing_character','character_id':cid})
            try:
                ps=json.loads(spec).get('participants')
                if isinstance(ps,list) and len(ps)>1:
                    audit['manual_reconciliation'].append({'shot_id':sid,'type':'duo_participants_need_explicit_character_mapping','participant_count':len(ps)})
            except (ValueError,TypeError,AttributeError):
                audit['manual_reconciliation'].append({'shot_id':sid,'type':'unparseable_shot_spec'})
        for fr,to,rel,srcid in cout.execute('''
            SELECT from_tag_id,to_tag_id,relation,source_id FROM tag_relation WHERE source_id IS NOT NULL'''):
            cout.execute('INSERT OR IGNORE INTO tag_relation_source(from_tag_id,to_tag_id,relation,source_snapshot_id) VALUES(?,?,?,?)',
                         (fr,to,rel,srcid))
            relation_sources+=cout.execute('SELECT changes()').fetchone()[0]
        audit['backfilled']={
          'character_identity_revision':identity,'outfit_revision_draft':outfits,
          'shot_spec_revision_draft':specs,'shot_participant_from_legacy_character_id':participants,
          'tag_relation_source':relation_sources
        }
        fk=cout.execute('PRAGMA foreign_key_check').fetchmany(21)
        integrity=cout.execute('PRAGMA quick_check').fetchone()[0]
        audit['check']={'quick_check':integrity,'fk_violations_first_20':[list(x) for x in fk[:20]]}
        if integrity!='ok' or fk:raise RuntimeError('Staging integrity failed; no backfill committed')
        cout.commit()
        return audit
    except Exception:
        cout.rollback()
        raise
    finally:cout.close()

if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument('--source',required=True)
    a.add_argument('--target',required=True,help='New path: it MUST NOT already exist')
    a.add_argument('--report',help='Write JSON report')
    x=a.parse_args()
    result=migrate_copy(x.source,x.target)
    output=json.dumps(result,ensure_ascii=False,indent=2)
    if x.report:pathlib.Path(x.report).write_text(output+'\n',encoding='utf-8')
    print(output)
