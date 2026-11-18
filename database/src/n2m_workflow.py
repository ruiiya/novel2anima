#!/usr/bin/env python3
"""Giao diện ghi dữ liệu Story/Shot/Natural Prompt/QA cho Novel2Anima, SQLite chuẩn thư viện.

Không chạy LLM / network / renderer. Không tự tạo nội dung truyện; chỉ xác thực và lưu artifact.
Dùng cùng SQLite schema với n2m_db.py. Ghi thay đổi trong transaction, append-only với revision.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

from n2m_db import connect, apply_migrations, uid, js, DEFAULT_DB, save_natural_prompt
from n2m_storyboard import save_storyboard, get_storyboard, seal_storyboard, compare_storyboards, apply_delta, compile_bound_prompt
from n2m_continuity import validate_moment


def load_json(path: Path):
    obj = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(obj, dict):
        raise ValueError('Expected a JSON object')
    return obj


def required(con, sql, params, what):
    row = con.execute(sql, params).fetchone()
    if row is None:
        raise ValueError(f'{what} not found')
    return row


def story_from_beat(con, beat_id):
    return required(con, '''SELECT a.story_id FROM beats b JOIN acts a ON a.id=b.act_id WHERE b.id=?''',
                    (beat_id,), 'Beat')['story_id']


def story_from_shot(con, shot_id):
    return required(con, '''SELECT a.story_id FROM shots s JOIN beats b ON b.id=s.beat_id
                    JOIN acts a ON a.id=b.act_id WHERE s.id=?''', (shot_id,), 'Shot')['story_id']


def role_id(con, story_id, key):
    if key is None:
        return None
    return required(con, 'SELECT id FROM story_roles WHERE story_id=? AND role_key=?',
                    (story_id, key), f'Role {key}')['id']


def save_plan(con, story_id, obj, expected_revision=None):
    body = js(obj)
    with con:
        story = required(con, 'SELECT current_revision FROM stories WHERE id=?', (story_id,), 'Story')
        current = story['current_revision']
        if expected_revision is not None and current != expected_revision:
            raise ValueError(f'Stale story revision: expected {expected_revision}, actual {current}')
        previous = con.execute('SELECT revision,plan_json FROM story_revisions WHERE story_id=? ORDER BY revision DESC LIMIT 1', (story_id,)).fetchone()
        if previous and previous['plan_json'] == body:
            return previous['revision']
        rev = current if previous is None and con.execute(
            'SELECT 1 FROM story_revisions WHERE story_id=? AND revision=?', (story_id,current)).fetchone() is None else current + 1
        src = required(con, 'SELECT content_sha256 FROM story_sources WHERE story_id=? ORDER BY recorded_at,id LIMIT 1',
                       (story_id,), 'Story source')
        con.execute('INSERT INTO story_revisions(id,story_id,revision,plan_json,source_sha256) VALUES(?,?,?,?,?)',
                    (uid('plan'),story_id,rev,body,src['content_sha256']))
        con.execute("UPDATE stories SET current_revision=?,updated_at=datetime('now') WHERE id=?", (rev,story_id))
    return rev


def add_act(con, story_id, order, title=None, summary=None, spec=None):
    required(con, 'SELECT id FROM stories WHERE id=?', (story_id,), 'Story')
    with con:
        existing = con.execute('SELECT * FROM acts WHERE story_id=? AND act_order=?', (story_id,order)).fetchone()
        body = js(spec or {})
        if existing:
            if (existing['title'],existing['summary'],existing['spec_json']) != (title,summary,body):
                raise ValueError('Act already exists with different content; preserve approved revision')
            return existing['id']
        id_ = uid('act')
        con.execute('INSERT INTO acts(id,story_id,act_order,title,summary,spec_json) VALUES(?,?,?,?,?,?)',
                    (id_,story_id,order,title,summary,body))
        return id_


def add_beat(con, act_id, order, summary=None, spec=None):
    required(con, 'SELECT id FROM acts WHERE id=?', (act_id,), 'Act')
    with con:
        existing = con.execute('SELECT * FROM beats WHERE act_id=? AND beat_order=?', (act_id,order)).fetchone()
        body = js(spec or {})
        if existing:
            if (existing['summary'],existing['spec_json']) != (summary,body):
                raise ValueError('Beat already exists with different content; preserve approved revision')
            return existing['id']
        id_ = uid('beat')
        con.execute('INSERT INTO beats(id,act_id,beat_order,summary,spec_json) VALUES(?,?,?,?,?)',
                    (id_,act_id,order,summary,body))
        return id_


def add_event(con, beat_id, order, event):
    story_id = story_from_beat(con,beat_id)
    actor = role_id(con,story_id,event.get('actor_role_key'))
    target = role_id(con,story_id,event.get('target_role_key'))
    if 'action' not in event or not isinstance(event['action'],str) or not event['action'].strip():
        raise ValueError('Event requires non-empty action')
    data = (actor,target,event['action'],event.get('reaction'),js(event.get('raw_labels',[])),
            event.get('source_fragment'),js(event.get('spec',{})))
    with con:
        existing=con.execute('SELECT * FROM story_events WHERE beat_id=? AND event_order=?',(beat_id,order)).fetchone()
        if existing:
            names=('actor_role_id','target_role_id','action','reaction','raw_labels_json','source_fragment','spec_json')
            if tuple(existing[k] for k in names) != data:
                raise ValueError('Event conflict: do not overwrite approved event')
            return existing['id']
        id_=uid('event')
        con.execute('''INSERT INTO story_events(id,beat_id,event_order,actor_role_id,target_role_id,action,
                       reaction,raw_labels_json,source_fragment,spec_json) VALUES(?,?,?,?,?,?,?,?,?,?)''',
                    (id_,beat_id,order,*data))
        return id_


def save_shot(con, beat_id, shot_key, obj, event_id=None):
    story_id=story_from_beat(con,beat_id)
    if event_id:
        required(con,'SELECT id FROM story_events WHERE id=? AND beat_id=?',(event_id,beat_id),'Event in beat')
    participants=obj.get('participants',[])
    interactions=obj.get('interactions',[])
    if not isinstance(participants,list) or not isinstance(interactions,list):
        raise ValueError('participants and interactions must be lists')
    pr=[]
    for p in participants:
        pr.append((role_id(con,story_id,p['role_key']), p.get('pose_vocab_id'),
                   p.get('outfit_override_id'),js(p.get('spec',{}))))
    if len({v[0] for v in pr})!=len(pr):
        raise ValueError('Duplicate shot role')
    ia=[]
    for a in interactions:
        actor=role_id(con,story_id,a['actor_role_key'])
        target=role_id(con,story_id,a.get('target_role_key'))
        if actor not in {p[0] for p in pr} or (target and target not in {p[0] for p in pr}):
            raise ValueError('Interaction roles must be shot participants')
        if not a.get('action_text'):
            raise ValueError('Interaction requires action_text')
        ia.append((actor,target,a.get('action_vocab_id'),a['action_text'],a.get('reaction_text'),
                   js(a.get('constraints',[]))))
    body=js(obj)
    with con:
        previous=con.execute('''SELECT id,revision,shot_spec_json,source_event_id FROM shots
                 WHERE beat_id=? AND shot_key=? ORDER BY revision DESC LIMIT 1''',(beat_id,shot_key)).fetchone()
        if previous and previous['shot_spec_json']==body and previous['source_event_id']==event_id:
            return previous['id'],previous['revision']
        rev=previous['revision']+1 if previous else 1
        id_=uid('shot')
        con.execute('''INSERT INTO shots(id,beat_id,shot_key,revision,source_event_id,shot_spec_json,supersedes_shot_id)
                      VALUES(?,?,?,?,?,?,?)''',(id_,beat_id,shot_key,rev,event_id,body,previous['id'] if previous else None))
        for r,pose,outfit,spec in pr:
            con.execute('''INSERT INTO shot_participants(shot_id,story_role_id,pose_vocab_id,outfit_override_id,spec_json)
                       VALUES(?,?,?,?,?)''',(id_,r,pose,outfit,spec))
        for actor,target,vocab,action,reaction,constraints in ia:
            con.execute('''INSERT INTO shot_interactions(id,shot_id,actor_role_id,target_role_id,action_vocab_id,
                       action_text,reaction_text,constraints_json) VALUES(?,?,?,?,?,?,?,?)''',
                        (uid('interaction'),id_,actor,target,vocab,action,reaction,constraints))
    return id_,rev


def save_continuity(con, shot_id, obj):
    story_id=story_from_shot(con,shot_id)
    rows=obj.get('snapshots',[])
    if not isinstance(rows,list) or not rows:
        raise ValueError('snapshots must be a non-empty list')
    keys=[r.get('role_key') for r in rows]
    if len(keys)!=len(set(keys)):
        raise ValueError('Duplicate continuity role')
    with con:
        result=[]
        for snapshot in rows:
            role=role_id(con,story_id,snapshot.get('role_key'))
            values=[js(snapshot[k]) for k in ('before','delta','after')]
            moment=snapshot.get('moment')
            if moment is not None:
                if apply_delta(snapshot['before'],snapshot['delta'])!=snapshot['after']:
                    raise ValueError('CONTINUITY_DELTA_MISMATCH')
                validate_moment(snapshot,apply_delta)
            moment_json=js(moment) if moment is not None else None
            previous=con.execute('''SELECT * FROM continuity_snapshots
                            WHERE shot_id=? AND story_role_id IS ?''',(shot_id,role)).fetchone()
            if previous:
                if tuple(previous[k+'_json'] for k in ('before','delta','after')) != tuple(values) or previous['moment_json']!=moment_json:
                    raise ValueError('Continuity is immutable: create new shot revision')
                result.append(previous['id'])
                continue
            id_=uid('state')
            con.execute('''INSERT INTO continuity_snapshots(id,shot_id,story_role_id,before_json,delta_json,after_json,moment_json)
                       VALUES(?,?,?,?,?,?,?)''',(id_,shot_id,role,*values,moment_json))
            result.append(id_)
    return result


def save_qa(con,kind,subject_id,verdict,report,policy_ref=None):
    tables={'STORY':'stories','SHOT':'shots','PROMPT':'shot_prompts'}
    table=tables[kind]
    required(con,f'SELECT id FROM {table} WHERE id=?',(subject_id,),kind)
    with con:
        body=js(report)
        previous=con.execute('''SELECT id,verdict,policy_ref,report_json FROM qa_reports
                    WHERE subject_kind=? AND subject_id=? ORDER BY rowid DESC LIMIT 1''',
                    (kind,subject_id)).fetchone()
        if previous and (previous['verdict'],previous['policy_ref'],previous['report_json']) == (verdict,policy_ref,body):
            return previous['id']
        id_=uid('qa')
        con.execute('''INSERT INTO qa_reports(id,subject_kind,subject_id,verdict,policy_ref,report_json)
                     VALUES(?,?,?,?,?,?)''',(id_,kind,subject_id,verdict,policy_ref,body))
        return id_


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--db',type=Path,default=DEFAULT_DB)
    sub=p.add_subparsers(dest='command',required=True)
    q=sub.add_parser('save-plan');q.add_argument('--story-id',required=True);q.add_argument('--file',type=Path,required=True);q.add_argument('--expected-revision',type=int)
    q=sub.add_parser('save-storyboard');q.add_argument('--story-id',required=True);q.add_argument('--file',type=Path,required=True);q.add_argument('--expected-revision',type=int)
    q=sub.add_parser('get-storyboard');q.add_argument('--storyboard-id',required=True)
    q=sub.add_parser('compare-storyboards');q.add_argument('--old-id',required=True);q.add_argument('--new-id',required=True)
    q=sub.add_parser('seal-storyboard');q.add_argument('--storyboard-id',required=True);q.add_argument('--file',type=Path,required=True)
    q=sub.add_parser('add-act');q.add_argument('--story-id',required=True);q.add_argument('--order',type=int,required=True);q.add_argument('--title');q.add_argument('--summary');q.add_argument('--spec-file',type=Path)
    q=sub.add_parser('add-beat');q.add_argument('--act-id',required=True);q.add_argument('--order',type=int,required=True);q.add_argument('--summary');q.add_argument('--spec-file',type=Path)
    q=sub.add_parser('add-event');q.add_argument('--beat-id',required=True);q.add_argument('--order',type=int,required=True);q.add_argument('--file',type=Path,required=True)
    q=sub.add_parser('save-shot');q.add_argument('--beat-id',required=True);q.add_argument('--shot-key',required=True);q.add_argument('--file',type=Path,required=True);q.add_argument('--event-id')
    q=sub.add_parser('save-continuity');q.add_argument('--shot-id',required=True);q.add_argument('--file',type=Path,required=True)
    q=sub.add_parser('save-natural-prompt');q.add_argument('--shot-id',required=True);q.add_argument('--file',type=Path,required=True);q.add_argument('--language',choices=('en','vi','zh'),default='en')
    q=sub.add_parser('compile-prompt');q.add_argument('--shot-id',required=True);q.add_argument('--save',action='store_true')
    q=sub.add_parser('save-qa');q.add_argument('--kind',choices=('STORY','SHOT','PROMPT'),required=True);q.add_argument('--subject-id',required=True);q.add_argument('--verdict',choices=('PASS','WARN','BLOCKED','SKIP'),required=True);q.add_argument('--file',type=Path,required=True);q.add_argument('--policy-ref')
    args=p.parse_args()
    con=connect(args.db)
    try:
        apply_migrations(con)
        c=args.command
        if c=='save-plan':value=save_plan(con,args.story_id,load_json(args.file),args.expected_revision)
        elif c=='save-storyboard':value=save_storyboard(con,args.story_id,load_json(args.file),args.expected_revision)
        elif c=='get-storyboard':value=get_storyboard(con,args.storyboard_id)
        elif c=='compare-storyboards':value=compare_storyboards(con,args.old_id,args.new_id)
        elif c=='seal-storyboard':value=seal_storyboard(con,args.storyboard_id,load_json(args.file))
        elif c=='add-act':value=add_act(con,args.story_id,args.order,args.title,args.summary,load_json(args.spec_file) if args.spec_file else None)
        elif c=='add-beat':value=add_beat(con,args.act_id,args.order,args.summary,load_json(args.spec_file) if args.spec_file else None)
        elif c=='add-event':value=add_event(con,args.beat_id,args.order,load_json(args.file))
        elif c=='save-shot':value=save_shot(con,args.beat_id,args.shot_key,load_json(args.file),args.event_id)
        elif c=='save-continuity':value=save_continuity(con,args.shot_id,load_json(args.file))
        elif c=='save-natural-prompt':value=save_natural_prompt(con,args.shot_id,args.file.read_text(encoding='utf-8'),args.language)
        elif c=='compile-prompt':
            prompt=compile_bound_prompt(con,args.shot_id)
            value={'prompt':prompt}
            if args.save:value['saved']=save_natural_prompt(con,args.shot_id,prompt)
        elif c=='save-qa':value=save_qa(con,args.kind,args.subject_id,args.verdict,load_json(args.file),args.policy_ref)
        print(json.dumps({'status':'PASS','result':value},ensure_ascii=False))
    finally:con.close()

if __name__=='__main__':
    try:main()
    except (ValueError,KeyError,TypeError,sqlite3.Error,FileNotFoundError,json.JSONDecodeError) as exc:
        print(json.dumps({'status':'ERROR','message':str(exc)},ensure_ascii=False),file=sys.stderr)
        sys.exit(1)
