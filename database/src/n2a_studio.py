#!/usr/bin/env python3
"""Novel2Anima V6: prompt-only Studio approval, revisions, feedback and resume.

No LLM, remote services, image generation, or silent user approval. The CLI
persists evidence; a human must explicitly confirm each approval decision.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

from n2m_db import DEFAULT_DB, apply_migrations, connect, js, sha, uid, export_story_prompts
from n2m_storyboard import sealed_selection

STAGES = ('STORY', 'RESEARCH_VISUAL', 'STORYBOARD', 'PROMPTS')


def need(ok, code):
    if not ok:
        raise ValueError(code)


def one(con, query, values=(), label='MISSING'):
    result = con.execute(query, values).fetchone()
    need(result is not None, label)
    return result


def latest(con, story_id, stage):
    return con.execute('''SELECT * FROM studio_artifacts WHERE story_id=? AND stage=?
        ORDER BY revision DESC LIMIT 1''', (story_id, stage)).fetchone()


def decision(con, artifact_id):
    return con.execute('''SELECT * FROM studio_decisions WHERE artifact_id=?
        ORDER BY rowid DESC LIMIT 1''', (artifact_id,)).fetchone()


def material(con, story_id, stage, payload=None):
    """Return (source reference, digest, content snapshot), from the real V5 tables."""
    one(con, 'SELECT id FROM stories WHERE id=?', (story_id,), 'STORY_NOT_FOUND')
    if stage == 'STORY':
        story = one(con, 'SELECT current_revision FROM stories WHERE id=?', (story_id,))
        plan = one(con, '''SELECT id,revision,plan_json,source_sha256 FROM story_revisions
            WHERE story_id=? AND revision=?''', (story_id,story['current_revision']), 'STORY_PLAN_MISSING')
        content = {'story_revision':plan['revision'], 'story_plan_id':plan['id'],
                   'story_plan_sha256':sha(plan['plan_json']), 'source_sha256':plan['source_sha256']}
        return plan['id'], sha(js(content)), content
    if stage == 'RESEARCH_VISUAL':
        need(isinstance(payload, dict), 'RESEARCH_DOCUMENT_REQUIRED')
        need(isinstance(payload.get('visual_bible'), dict) and
             isinstance(payload.get('research_summary'), str) and payload['research_summary'].strip(),
             'RESEARCH_REQUIRES_BIBLE_AND_SUMMARY')
        need(isinstance(payload.get('references'),list) and bool(payload['references']) and
             all(isinstance(item,dict) and str(item.get('value','')).strip()
                 for item in payload['references']), 'RESEARCH_PROVENANCE_REQUIRED')
        content = payload
        return 'studio-research', sha(js(content)), content
    if stage == 'STORYBOARD':
        board = one(con, '''SELECT * FROM storyboards WHERE story_id=?
            ORDER BY revision DESC LIMIT 1''', (story_id,), 'STORYBOARD_MISSING')
        story = one(con, 'SELECT current_revision FROM stories WHERE id=?', (story_id,))
        need(board['story_revision'] == story['current_revision'], 'STALE_STORYBOARD_STORY_REVISION')
        need(sha(board['plan_json']) == board['plan_sha256'], 'STORYBOARD_HASH_MISMATCH')
        content = {'storyboard_id':board['id'], 'storyboard_revision':board['revision'],
                   'story_revision':board['story_revision'], 'plan_sha256':board['plan_sha256']}
        return board['id'], sha(js(content)), content
    if stage == 'PROMPTS':
        board = one(con, 'SELECT id FROM storyboards WHERE story_id=? ORDER BY revision DESC LIMIT 1',
                    (story_id,), 'STORYBOARD_MISSING')
        board_id, bindings = sealed_selection(con, story_id,board['id'])
        prompts = []
        for b in bindings:
            prompt = one(con, 'SELECT id,revision,prompt_sha256 FROM shot_prompts WHERE id=?',
                         (b['prompt_id'],),'PINNED_PROMPT_MISSING')
            current = one(con, '''SELECT id FROM shot_prompts WHERE shot_id=? ORDER BY revision DESC LIMIT 1''',
                          (b['shot_id'],))
            need(current['id'] == prompt['id'], 'NEWER_PROMPT_REQUIRES_REVIEW_AND_RESEAL')
            prompts.append({'shot_key':b['shot_key'], 'shot_order':b['shot_order'],
                            'shot_id':b['shot_id'], 'prompt_id':prompt['id'],
                            'revision':prompt['revision'], 'sha256':prompt['prompt_sha256'],
                            'qa_id':b['qa_id']})
        seal = one(con, 'SELECT seal_sha256 FROM storyboard_seals WHERE storyboard_id=?',
                   (board_id,), 'STORYBOARD_NOT_SEALED')
        content={'storyboard_id':board_id, 'seal_sha256':seal['seal_sha256'], 'prompts':prompts}
        return board_id, sha(js(content)), content
    raise ValueError('UNKNOWN_STAGE')


def valid_approval(con, artifact):
    """Checks latest decision, latest stage revision and transitive upstream hashes."""
    if artifact is None:
        return False
    current = latest(con, artifact['story_id'], artifact['stage'])
    if current is None or current['id'] != artifact['id']:
        return False
    action = decision(con,artifact['id'])
    if action is None or action['decision'] != 'APPROVED':
        return False
    try:
        if artifact['stage'] != 'RESEARCH_VISUAL':
            _, digest, _ = material(con,artifact['story_id'],artifact['stage'])
            if artifact['source_sha256'] != digest:
                return False
        else:
            if artifact['source_sha256'] != sha(artifact['artifact_json']):
                return False
    except (ValueError,sqlite3.Error):
        return False
    index=STAGES.index(artifact['stage'])
    if index:
        pre=latest(con,artifact['story_id'],STAGES[index-1])
        return pre is not None and artifact['prerequisite_id']==pre['id'] and valid_approval(con,pre)
    return True


def submit(con, story_id, stage, review, payload=None):
    need(stage in STAGES, 'UNKNOWN_STAGE')
    need(isinstance(review,dict) and review.get('verdict')=='PASS' and
         isinstance(review.get('evidence'),str) and review['evidence'].strip(),
         'REVIEW_PASS_WITH_EVIDENCE_REQUIRED')
    prerequisite=None
    if stage!='STORY':
        prerequisite=latest(con,story_id,STAGES[STAGES.index(stage)-1])
        need(valid_approval(con,prerequisite), 'PREREQUISITE_NOT_APPROVED_OR_STALE')
    ref,digest,content=material(con,story_id,stage,payload)
    prev=latest(con,story_id,stage)
    review_json=js(review)
    # Repeated identical requests are idempotent, including after a previous approval.
    if prev and (prev['source_sha256'],prev['prerequisite_id'],prev['review_json']) == (
            digest,prerequisite['id'] if prerequisite else None,review_json):
        return {'artifact_id':prev['id'],'revision':prev['revision'],'status':'READY_FOR_REVIEW'}
    revision=prev['revision']+1 if prev else 1
    artifact_id=uid('stage')
    with con:
        con.execute('''INSERT INTO studio_artifacts(id,story_id,stage,revision,source_ref,
            source_sha256,artifact_json,artifact_sha256,prerequisite_id,review_json)
            VALUES(?,?,?,?,?,?,?,?,?,?)''', (artifact_id,story_id,stage,revision,ref,digest,
            js(content),sha(js(content)),prerequisite['id'] if prerequisite else None,review_json))
    return {'artifact_id':artifact_id,'revision':revision,'status':'READY_FOR_REVIEW'}


def review_decision(con, story_id, stage, action, evidence, user_confirmed=False):
    need(stage in STAGES and action in ('APPROVED','CHANGES_REQUESTED'), 'INVALID_DECISION')
    need(user_confirmed, 'EXPLICIT_USER_CONFIRMATION_REQUIRED')
    need(isinstance(evidence,str) and evidence.strip(), 'USER_DECISION_EVIDENCE_REQUIRED')
    artifact=latest(con,story_id,stage)
    need(artifact is not None,'STAGE_ARTIFACT_MISSING')
    prior=decision(con,artifact['id'])
    need(prior is None, 'DECISION_ALREADY_RECORDED_SUBMIT_NEW_REVISION')
    if action=='APPROVED':
        if stage!='RESEARCH_VISUAL':
            _,digest,_=material(con,story_id,stage)
            need(artifact['source_sha256']==digest,'STAGE_ARTIFACT_STALE')
        if stage!='STORY':
            prereq=latest(con,story_id,STAGES[STAGES.index(stage)-1])
            need(valid_approval(con,prereq) and artifact['prerequisite_id']==prereq['id'],
                 'UPSTREAM_APPROVAL_CHANGED')
    with con:
        event=uid('decision')
        con.execute('INSERT INTO studio_decisions(id,artifact_id,decision,actor,evidence) VALUES(?,?,?,?,?)',
                    (event,artifact['id'],action,'USER',evidence))
    return {'decision_id':event,'artifact_id':artifact['id'],'decision':action}


def get_status(con, story_id):
    story=one(con,'SELECT id,title,cast_mode,current_revision FROM stories WHERE id=?',
              (story_id,),'STORY_NOT_FOUND')
    stages=[]
    for stage in STAGES:
        artifact=latest(con,story_id,stage)
        action=decision(con,artifact['id']) if artifact else None
        valid=valid_approval(con,artifact)
        state=('NOT_STARTED' if not artifact else
               'APPROVED' if valid else
               'CHANGES_REQUESTED' if action and action['decision']=='CHANGES_REQUESTED' else
               'STALE' if action and action['decision']=='APPROVED' else
               'READY_FOR_REVIEW' if not action else 'STALE')
        stages.append({'stage':stage,'status':state,'revision':artifact['revision'] if artifact else None,
                       'artifact_id':artifact['id'] if artifact else None})
    next_stage=next((s['stage'] for s in stages if s['status']!='APPROVED'),'COMPLETED')
    feedback_count=con.execute("SELECT COUNT(*) FROM studio_feedback WHERE story_id=? AND status='OPEN'",
                               (story_id,)).fetchone()[0]
    return {'story':dict(story),'stages':stages,'next_stage':next_stage,'open_feedback':feedback_count}


def list_stories(con):
    return [get_status(con,r['id']) for r in con.execute('SELECT id FROM stories ORDER BY updated_at DESC,id')]


def affected_shots(con, board_id, shot_key):
    graph={}
    for row in con.execute('SELECT previous_shot_key,shot_key FROM shot_dependencies WHERE storyboard_id=?',
                           (board_id,)):
        graph.setdefault(row['previous_shot_key'],set()).add(row['shot_key'])
    affected={shot_key}
    pending=[shot_key]
    while pending:
        for key in graph.get(pending.pop(),()):
            if key not in affected:
                affected.add(key);pending.append(key)
    return sorted(affected)


def report_feedback(con, story_id, shot_key, description):
    need(description.strip(),'FEEDBACK_DESCRIPTION_REQUIRED')
    # Feedback must target the user's *exported* board, even if the agent has
    # already drafted another storyboard revision in the meantime.
    exported=con.execute('''SELECT a.artifact_json FROM studio_exports e
         JOIN studio_artifacts a ON a.id=e.prompts_artifact_id
         WHERE e.story_id=? ORDER BY e.rowid DESC LIMIT 1''', (story_id,)).fetchone()
    if exported:
        board_id=json.loads(exported['artifact_json'])['storyboard_id']
        board=one(con,'SELECT id FROM storyboards WHERE id=? AND story_id=?',
                  (board_id,story_id),'EXPORTED_STORYBOARD_MISSING')
    else:
        board=one(con,'SELECT id FROM storyboards WHERE story_id=? ORDER BY revision DESC LIMIT 1',
                  (story_id,),'STORYBOARD_MISSING')
    one(con,'SELECT shot_key FROM storyboard_shots WHERE storyboard_id=? AND shot_key=?',
        (board['id'],shot_key),'SHOT_KEY_NOT_IN_STORYBOARD')
    bind=sealed_selection(con,story_id,board['id'])
    current=next((b for b in bind[1] if b['shot_key']==shot_key),None) if bind else None
    affected=affected_shots(con,board['id'],shot_key)
    feedback_id=uid('feedback')
    with con:
        con.execute('''INSERT INTO studio_feedback(id,story_id,storyboard_id,shot_key,prompt_id,
            description,affected_json) VALUES(?,?,?,?,?,?,?)''',
            (feedback_id,story_id,board['id'],shot_key,current['prompt_id'] if current else None,
             description,js(affected)))
    return {'feedback_id':feedback_id,'affected_shot_keys':affected,'status':'OPEN'}


def resolve_feedback(con, feedback_id, prompt_id, note):
    need(isinstance(note,str) and note.strip(),'RESOLUTION_NOTE_REQUIRED')
    feedback=one(con,'SELECT * FROM studio_feedback WHERE id=?',(feedback_id,),'FEEDBACK_NOT_FOUND')
    need(feedback['status']=='OPEN','FEEDBACK_ALREADY_RESOLVED')
    prompt=one(con,'''SELECT p.*,s.shot_key,a.story_id FROM shot_prompts p
        JOIN shots s ON s.id=p.shot_id JOIN beats b ON b.id=s.beat_id
        JOIN acts a ON a.id=b.act_id WHERE p.id=?''',(prompt_id,),'PROMPT_NOT_FOUND')
    need((prompt['story_id'],prompt['shot_key']) == (feedback['story_id'],feedback['shot_key']),
         'RESOLVED_PROMPT_WRONG_SHOT')
    need(prompt_id!=feedback['prompt_id'],'FEEDBACK_REQUIRES_NEW_PROMPT_REVISION')
    with con:
        con.execute('''UPDATE studio_feedback SET status='RESOLVED',resolved_prompt_id=?,
            resolution_note=?,resolved_at=datetime('now') WHERE id=?''', (prompt_id,note,feedback_id))
    return {'feedback_id':feedback_id,'resolved_prompt_id':prompt_id,
            'notice':'Re-review affected storyboard/prompts and obtain new approvals before studio export.'}


def studio_export(con, story_id, out_dir):
    artifact=latest(con,story_id,'PROMPTS')
    need(valid_approval(con,artifact),'PROMPTS_APPROVAL_REQUIRED_OR_STALE')
    content=json.loads(artifact['artifact_json'])
    # This export is strictly pinned to an already approved seal, never newest unpublished prompts.
    result=export_story_prompts(con,story_id,out_dir,content['storyboard_id'])
    output=Path(result['output'])
    manifest={'story_id':story_id,'format':'novel2anima-studio-v6',
              'approval_artifact_id':artifact['id'],'approval_hash':artifact['artifact_sha256'],
              'storyboard_id':content['storyboard_id'],'seal_sha256':content['seal_sha256'],
              'prompts':content['prompts'],'output':'prompts.all.jsonl',
              'output_sha256':sha(output.read_bytes())}
    path=out_dir/'studio.manifest.json'
    path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    with con:
        con.execute('''INSERT INTO studio_exports(id,story_id,prompts_artifact_id,manifest_sha256,export_dir)
            VALUES(?,?,?,?,?)''',(uid('export'),story_id,artifact['id'],sha(path.read_bytes()),str(out_dir.resolve())))
    return {**result,'studio_manifest':str(path),'approval_artifact_id':artifact['id']}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--db',type=Path,default=DEFAULT_DB)
    subs=p.add_subparsers(dest='command',required=True)
    cmd=subs.add_parser('submit-stage');cmd.add_argument('--story-id',required=True)
    cmd.add_argument('--stage',required=True,choices=STAGES)
    cmd.add_argument('--review-file',required=True,type=Path)
    cmd.add_argument('--file',type=Path,help='Required only for RESEARCH_VISUAL')
    cmd=subs.add_parser('decide-stage');cmd.add_argument('--story-id',required=True)
    cmd.add_argument('--stage',required=True,choices=STAGES)
    cmd.add_argument('--decision',choices=('APPROVED','CHANGES_REQUESTED'),required=True)
    cmd.add_argument('--evidence',required=True)
    cmd.add_argument('--user-confirmed',action='store_true',help='Only after explicit confirmation from the user')
    cmd=subs.add_parser('status');cmd.add_argument('--story-id',required=True)
    subs.add_parser('list-stories')
    cmd=subs.add_parser('report-feedback');cmd.add_argument('--story-id',required=True)
    cmd.add_argument('--shot-key',required=True);cmd.add_argument('--description',required=True)
    cmd=subs.add_parser('resolve-feedback');cmd.add_argument('--feedback-id',required=True)
    cmd.add_argument('--prompt-id',required=True);cmd.add_argument('--note',required=True)
    cmd=subs.add_parser('export');cmd.add_argument('--story-id',required=True)
    cmd.add_argument('--out-dir',required=True,type=Path)
    args=p.parse_args()
    con=connect(args.db)
    try:
        apply_migrations(con)
        command=args.command
        if command=='submit-stage':
            review=json.loads(args.review_file.read_text(encoding='utf-8'))
            doc=json.loads(args.file.read_text(encoding='utf-8')) if args.file else None
            result=submit(con,args.story_id,args.stage,review,doc)
        elif command=='decide-stage':
            result=review_decision(con,args.story_id,args.stage,args.decision,args.evidence,args.user_confirmed)
        elif command=='status':result=get_status(con,args.story_id)
        elif command=='list-stories':result=list_stories(con)
        elif command=='report-feedback':result=report_feedback(con,args.story_id,args.shot_key,args.description)
        elif command=='resolve-feedback':result=resolve_feedback(con,args.feedback_id,args.prompt_id,args.note)
        elif command=='export':result=studio_export(con,args.story_id,args.out_dir)
        else:raise ValueError('UNKNOWN_COMMAND')
        print(json.dumps({'status':'PASS','result':result},ensure_ascii=False,indent=2))
    finally:
        con.close()

if __name__=='__main__':
    try:main()
    except (ValueError,KeyError,TypeError,sqlite3.Error,FileNotFoundError,json.JSONDecodeError) as exc:
        print(json.dumps({'status':'ERROR','message':str(exc)},ensure_ascii=False),file=sys.stderr)
        sys.exit(1)
