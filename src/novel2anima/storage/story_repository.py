"""Safe, idempotent shot reseeding; never discard generations silently."""
from __future__ import annotations

import json

from novel2anima.storage.domain_repository import ensure_shot_spec_revision
from novel2anima.storage.shot_specs import latest_shot_spec


class ReseedConflict(RuntimeError):
    pass


def upsert_shot(cur, aid, shot_no, spec, content_mode='nsfw', pose_id=None):
    """Write the shot row and its approved spec revision.

    Returns ``(shot_id, changed)``. The legacy ``character_id`` and
    ``shot_spec_json`` columns are never written.
    """
    row = cur.execute(
        'SELECT id,status FROM shot WHERE act_id=? AND shot_no=?', (aid, shot_no)
    ).fetchone()
    signature = spec.get('signature')
    if row is None:
        cur.execute(
            "INSERT INTO shot(act_id, shot_no, action_concept_id, expression_concept_id,"
            " pose_concept_id, camera_concept_id, signature, content_mode, status, created_at)"
            " VALUES(?,?,NULL,NULL,?,NULL,?,?,'planned',CURRENT_TIMESTAMP)",
            (aid, shot_no, pose_id, signature, content_mode),
        )
        sid = int(cur.lastrowid)
        ensure_shot_spec_revision(cur, sid, spec, status='approved')
        return sid, True

    sid, status = int(row[0]), row[1]
    prior = latest_shot_spec(cur, sid)
    if prior == spec:
        return sid, False
    has_generation = cur.execute(
        'SELECT 1 FROM generation WHERE shot_id=? LIMIT 1', (sid,)
    ).fetchone()
    if has_generation or status in ('approved', 'generated', 'locked'):
        raise ReseedConflict(
            'Shot %s of act %s has render history/status=%s and content changed; '
            'increment act.revision to protect original image decisions'
            % (shot_no, aid, status)
        )
    # Findings are a projection; drop stale rows for an unrendered shot.
    cur.execute('DELETE FROM shot_finding WHERE shot_id=?', (sid,))
    cur.execute(
        'UPDATE shot SET pose_concept_id=?, signature=?, content_mode=? WHERE id=?',
        (pose_id, signature, content_mode, sid),
    )
    ensure_shot_spec_revision(cur, sid, spec, status='approved')
    return sid, True


def replace_participants(cur, shot_id, character_ids):
    """Replace explicit participants and directed interactions for an unrendered shot."""
    if cur.execute(
        'SELECT 1 FROM continuity_assertion WHERE shot_id=? LIMIT 1', (shot_id,)
    ).fetchone():
        raise ReseedConflict(
            'Shot %s has continuity assertions; create a new act revision instead'
            % shot_id
        )
    cur.execute('DELETE FROM shot_interaction WHERE shot_id=?', (shot_id,))
    cur.execute('DELETE FROM shot_outfit_binding WHERE shot_id=?', (shot_id,))
    cur.execute('DELETE FROM shot_participant WHERE shot_id=?', (shot_id,))
    for slot_no, character_id in enumerate(character_ids, start=1):
        cur.execute(
            'INSERT INTO shot_participant(shot_id, character_id, slot_no, scene_role)'
            " VALUES(?,?,?,'subject')",
            (shot_id, character_id, slot_no),
        )


def prune_missing_shots(cur, aid, desired_numbers):
    desired = set(desired_numbers)
    removed = 0
    for sid, shot_no, status in cur.execute('SELECT id, shot_no, status FROM shot WHERE act_id=?',
                                            (aid,)).fetchall():
        if shot_no in desired:
            continue
        if (status in ('approved', 'generated', 'locked') or
                cur.execute('SELECT 1 FROM generation WHERE shot_id=? LIMIT 1', (sid,)).fetchone()):
            raise ReseedConflict('Cannot remove shot %s from act %s: render/approval history exists. '
                                 'Increment revision instead.' % (shot_no, aid))
        cur.execute('DELETE FROM shot WHERE id=?', (sid,))
        removed += 1
    return removed


def resolve_act(con, act_no, project=None, revision=None):
    query = ('SELECT a.id FROM act a JOIN project p ON p.id=a.project_id '
             'WHERE a.act_no=?')
    params = [act_no]
    if project is not None:
        query += ' AND p.title=?'
        params.append(project)
    if revision is not None:
        query += ' AND a.revision=?'
        params.append(revision)
    rows = con.execute(query, params).fetchall()
    if len(rows) != 1:
        raise ValueError('Expected exactly one act (act=%s, project=%r, revision=%r), got %s. '
                         'Specify --project and --revision.' % (act_no, project, revision, len(rows)))
    return rows[0][0]


def clear_findings_for_act(con, source, act_id):
    return con.execute('DELETE FROM shot_finding WHERE source=? '
                       'AND shot_id IN (SELECT id FROM shot WHERE act_id=?)', (source, act_id))

def record_finding(cur, shot_id, rule_id, source, severity=0.5, axis=None,
                   value_tag_id=None, evidence=None):
    cur.execute('INSERT INTO shot_finding(shot_id, rule_id, source, axis, value_tag_id,'
                ' severity, evidence_json) VALUES(?,?,?,?,?,?,?)'
                ' ON CONFLICT(shot_id, rule_id, source) DO UPDATE SET'
                ' axis=excluded.axis, value_tag_id=excluded.value_tag_id,'
                ' severity=excluded.severity, evidence_json=excluded.evidence_json,'
                " status='open'",
                (shot_id, rule_id, source, axis, value_tag_id, severity,
                 json.dumps(evidence or {}, ensure_ascii=False)))
