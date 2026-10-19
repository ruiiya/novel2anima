"""Safe, idempotent shot reseeding; never discard generations silently."""
import json

class ReseedConflict(RuntimeError):
    pass


def upsert_shot(cur, aid, shot_no, char_id, pose_id, signature, spec, content_mode='nsfw'):
    encoded = json.dumps(spec, ensure_ascii=False)
    row = cur.execute('SELECT id, shot_spec_json, status FROM shot WHERE act_id=? AND shot_no=?',
                      (aid, shot_no)).fetchone()
    if row is None:
        cur.execute('INSERT INTO shot(act_id, shot_no, character_id, action_concept_id, '
                    'expression_concept_id, pose_concept_id, camera_concept_id, signature, '
                    'shot_spec_json, content_mode, status, created_at) '
                    "VALUES(?,?,?,NULL,NULL,?,NULL,?,?,?,'planned',CURRENT_TIMESTAMP)",
                    (aid, shot_no, char_id, pose_id, signature, encoded, content_mode))
        return 'created'
    sid, prior, status = row
    has_generation = cur.execute('SELECT 1 FROM generation WHERE shot_id=? LIMIT 1', (sid,)).fetchone()
    try:
        unchanged = json.loads(prior) == spec
    except (ValueError, TypeError):
        unchanged = False
    if unchanged:
        return 'unchanged'
    if has_generation or status in ('approved', 'generated', 'locked'):
        raise ReseedConflict('Shot %s of act %s has render history/status=%s and content changed; '
                             'increment act.revision to protect original image decisions' % (shot_no, aid, status))
    # Invalidate old findings for a changed unrendered shot; do not leave stale QA data.
    if cur.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='shot_state'").fetchone():
        cur.execute('DELETE FROM shot_state WHERE shot_id=?', (sid,))
    cur.execute('UPDATE shot SET character_id=?, pose_concept_id=?, signature=?, '
                'shot_spec_json=?, content_mode=? WHERE id=?',
                (char_id, pose_id, signature, encoded, content_mode, sid))
    return 'updated'


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
    return con.execute('DELETE FROM shot_state WHERE source=? '
                       'AND shot_id IN (SELECT id FROM shot WHERE act_id=?)', (source, act_id))
