"""V4 storyboard persistence, coverage, continuity and sealed prompt selection.

The agent authors visual content. This module only validates and saves data;
it never calls an LLM, evaluates content categories or renders images.
"""
from __future__ import annotations

import json
import re
from n2m_db import js, sha, uid

PURPOSES = {'ESTABLISHING', 'ACTION', 'REACTION', 'DETAIL', 'TRANSITION', 'CLIMAX', 'AFTERMATH'}
TRANSITIONS = {'CONTINUOUS', 'CAMERA_CUT', 'TIME_CUT', 'LOCATION_CUT', 'BRANCH'}
COVERAGE = {'VISUALIZED', 'CONTEXT_ONLY', 'UNRESOLVED', 'UNSUPPORTED_CONTENT'}
BIBLES = {'locations': ('story_locations', 'location_key'),
          'props': ('story_props', 'prop_key'),
          'styles': ('visual_style_profiles', 'style_key')}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def one(con, sql, args, label):
    row = con.execute(sql, args).fetchone()
    require(row is not None, f'{label} not found')
    return row


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def key(value):
    require(isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9_-]+', value),
            f'Invalid stable key: {value!r}')
    return value


def current_plan(con, story_id):
    story = one(con, 'SELECT * FROM stories WHERE id=?', (story_id,), 'Story')
    plan = one(con, '''SELECT * FROM story_revisions WHERE story_id=?
                     ORDER BY revision DESC LIMIT 1''', (story_id,), 'Story plan')
    require(json.loads(plan['plan_json']).get('approval', {}).get('status') == 'APPROVED',
            'WAITING_FOR_STORY_APPROVAL')
    return story, plan


def story_events(con, story_id):
    return {r['id']: r for r in con.execute('''SELECT e.* FROM story_events e
        JOIN beats b ON b.id=e.beat_id JOIN acts a ON a.id=b.act_id WHERE a.story_id=?''', (story_id,))}


def cast_at(con, story_id, revision):
    return {r['role_key']: dict(r) for r in con.execute('''SELECT r.role_key,r.id AS role_id,
        r.role_description,r.role_spec_json,c.id AS casting_id,c.character_id,c.outfit_id
        FROM story_roles r LEFT JOIN story_castings c ON c.story_role_id=r.id
        AND c.from_revision<=? AND (c.until_revision IS NULL OR c.until_revision>=?)
        WHERE r.story_id=?''', (revision, revision, story_id))}


def _validate_plan(con, story_id, obj, story, plan):
    require(obj.get('story_revision') == story['current_revision'], 'STALE_STORY_REVISION')
    require(obj.get('approval', {}).get('status') == 'APPROVED', 'WAITING_FOR_STORYBOARD_APPROVAL')
    require(nonempty(obj['approval'].get('evidence')), 'Storyboard approval evidence required')
    visual = obj['visual_bible']
    casts = cast_at(con, story_id, story['current_revision'])
    characters = visual['characters']
    require(isinstance(characters, dict), 'characters must be an object')
    for role, spec in characters.items():
        require(role in casts and isinstance(spec, dict), f'Unknown role or invalid bible: {role}')
        require(nonempty(spec.get('description')) and nonempty(spec.get('provenance')),
                f'Visual description and provenance required: {role}')
        require(spec.get('character_id') == casts[role]['character_id'] and
                spec.get('outfit_id') == casts[role]['outfit_id'], f'CASTING_MISMATCH: {role}')
        if story['cast_mode'] == 'NON_BLIND':
            require(casts[role]['character_id'] is not None, f'NON_BLIND_UNBOUND: {role}')
    for group in BIBLES:
        require(isinstance(visual[group], dict), f'{group} must be an object')
        for k, spec in visual[group].items():
            key(k)
            require(isinstance(spec, dict) and nonempty(spec.get('description')) and
                    nonempty(spec.get('provenance')), f'Invalid {group} entry: {k}')
    shots = obj['shots']
    require(isinstance(shots, list), 'Storyboard shots must be a list')
    events = story_events(con, story_id)
    require(events, 'Storyboard requires materialized Story Events')
    by_key, branch_tail, contexts = {}, {}, {}
    for index, s in enumerate(shots, 1):
        k = key(s['shot_key'])
        branch = key(s['branch_key'])
        require(k not in by_key and type(s['shot_order']) is int and s['shot_order'] == index,
                'Shot keys must be unique and order contiguous from 1')
        one(con, '''SELECT b.id FROM beats b JOIN acts a ON a.id=b.act_id
                    WHERE b.id=? AND a.story_id=?''', (s['beat_id'], story_id), 'Beat in story')
        require(s['purpose'] in PURPOSES and nonempty(s.get('focus')) and
                nonempty(s.get('camera')) and nonempty(s.get('visual_moment')), f'Invalid shot direction: {k}')
        roles = s['role_keys']
        require(isinstance(roles, list) and len(roles) == len(set(roles)) and
                all(r in characters for r in roles), f'Invalid participants: {k}')
        require(s['location_key'] in visual['locations'] and s['style_key'] in visual['styles'],
                f'Unknown location/style: {k}')
        props = s.get('prop_keys', [])
        require(isinstance(props, list) and len(props) == len(set(props)) and
                all(p in visual['props'] for p in props), f'Unknown/duplicate prop: {k}')
        prev, transition = s.get('previous_shot_key'), s.get('transition')
        if index == 1:
            require(prev is None and transition == 'START', 'First shot must START')
        else:
            require(prev in by_key and transition in TRANSITIONS, f'Invalid predecessor: {k}')
            if branch in branch_tail:
                require(prev == branch_tail[branch] and transition != 'BRANCH',
                        f'BRANCH_PREDECESSOR_MISMATCH: {k}')
            else:
                require(transition == 'BRANCH' and by_key[prev]['branch_key'] != branch,
                        f'New branch must fork explicitly: {k}')
            if by_key[prev]['location_key'] != s['location_key']:
                require(transition in ('LOCATION_CUT', 'TIME_CUT', 'BRANCH'),
                        f'LOCATION_CHANGE_WITHOUT_CUT: {k}')
        by_key[k], branch_tail[branch] = s, k
        # Hash only this slot's visual dependencies so unrelated repairs can reuse shots.
        # Predecessor state is checked separately during sealing.
        direction = {a: b for a, b in s.items() if a != 'shot_order'}
        contexts[k] = {'direction': direction, 'story_plan_id': plan['id'],
                       'characters': {r: {'bible': characters[r], 'casting': casts[r]} for r in roles},
                       'location': visual['locations'][s['location_key']],
                       'style': visual['styles'][s['style_key']],
                       'props': {p: visual['props'][p] for p in props}}
    coverage = obj['coverage']
    require(isinstance(coverage, list), 'coverage must be a list')
    seen, mapped = {}, set()
    for row in coverage:
        event, status, shot = row['event_id'], row['status'], row.get('shot_key')
        require(event in events and status in COVERAGE and nonempty(row.get('evidence')),
                'Invalid coverage entry')
        if status == 'VISUALIZED':
            require(shot in by_key and by_key[shot]['beat_id'] == events[event]['beat_id'],
                    'Coverage must refer to a shot in the same event beat')
            mapped.add(shot)
        else:
            require(shot is None, 'Non-visual coverage cannot reference a shot')
        previous = seen.setdefault(event, [])
        require(not previous or (status == 'VISUALIZED' and
                all(v[0] == status and v[1] != shot for v in previous)),
                'Duplicate or contradictory event coverage')
        previous.append((status, shot))
    require(set(seen) == set(events), 'SOURCE_COVERAGE_MISSING: every materialized Event needs coverage')
    require(mapped == set(by_key), 'Every storyboard shot must map to a source Event')
    for k, ctx in contexts.items():
        ctx['events'] = [dict(events[row['event_id']]) for row in coverage if row.get('shot_key') == k]
    return contexts


def save_storyboard(con, story_id, obj, expected_revision=None):
    # Serialize competing writers before reading revisions.
    con.execute('BEGIN IMMEDIATE')
    try:
        story, plan = current_plan(con, story_id)
        contexts = _validate_plan(con, story_id, obj, story, plan)
        prev = con.execute('SELECT * FROM storyboards WHERE story_id=? ORDER BY revision DESC LIMIT 1',
                           (story_id,)).fetchone()
        revision = prev['revision'] if prev else 0
        require(expected_revision is None or expected_revision == revision, 'STALE_STORYBOARD_REVISION')
        body = js(obj)
        if prev and prev['plan_json'] == body and prev['plan_id'] == plan['id'] and all(
                sha(js(contexts[r['shot_key']])) == r['context_sha256']
                for r in con.execute('SELECT shot_key,context_sha256 FROM storyboard_shots WHERE storyboard_id=?',
                                     (prev['id'],))):
            con.commit()
            return prev['id'], revision
        bid = uid('board')
        con.execute('''INSERT INTO storyboards(id,story_id,story_revision,plan_id,revision,plan_json,plan_sha256)
                       VALUES(?,?,?,?,?,?,?)''', (bid, story_id, story['current_revision'], plan['id'],
                                                   revision+1, body, sha(body)))
        for group, (table, column) in BIBLES.items():
            for k, spec in obj['visual_bible'][group].items():
                con.execute(f'INSERT INTO {table}(storyboard_id,{column},spec_json) VALUES(?,?,?)',
                            (bid, k, js(spec)))
        for s in obj['shots']:
            k = s['shot_key']
            con.execute('''INSERT INTO storyboard_shots
                (storyboard_id,shot_key,shot_order,beat_id,branch_key,purpose,context_sha256,spec_json)
                VALUES(?,?,?,?,?,?,?,?)''', (bid,k,s['shot_order'],s['beat_id'],s['branch_key'],
                                               s['purpose'],sha(js(contexts[k])),js(s)))
            if s.get('previous_shot_key'):
                con.execute('INSERT INTO shot_dependencies VALUES(?,?,?,?)',
                            (bid,k,s['previous_shot_key'],s['transition']))
        for r in obj['coverage']:
            con.execute('''INSERT INTO event_shot_mappings(storyboard_id,event_id,status,shot_key,evidence)
                           VALUES(?,?,?,?,?)''', (bid,r['event_id'],r['status'],r.get('shot_key'),r['evidence']))
        con.commit()
        return bid, revision+1
    except BaseException:
        con.rollback()
        raise


def get_storyboard(con, bid):
    board = one(con, 'SELECT * FROM storyboards WHERE id=?', (bid,), 'Storyboard')
    require(sha(board['plan_json']) == board['plan_sha256'], 'Storyboard hash mismatch')
    result = {'id': bid, 'revision': board['revision'], 'story_id': board['story_id'],
              'story_revision': board['story_revision'], 'plan': json.loads(board['plan_json']),
              'slots': [dict(r) for r in con.execute(
                  'SELECT * FROM storyboard_shots WHERE storyboard_id=? ORDER BY shot_order', (bid,))]}
    require([json.loads(r['spec_json']) for r in result['slots']] == result['plan']['shots'],
            'Storyboard shot projection mismatch')
    for group,(table,column) in BIBLES.items():
        actual = {r[column]:json.loads(r['spec_json']) for r in con.execute(
            f'SELECT {column},spec_json FROM {table} WHERE storyboard_id=?',(bid,))}
        require(actual == result['plan']['visual_bible'][group], f'{group} projection mismatch')
    projected = [dict(r) for r in con.execute(
        'SELECT event_id,status,shot_key,evidence FROM event_shot_mappings WHERE storyboard_id=?',(bid,))]
    expected = [{k:r.get(k) for k in ('event_id','status','shot_key','evidence')}
                for r in result['plan']['coverage']]
    require(sorted(map(js,projected)) == sorted(map(js,expected)), 'Coverage projection mismatch')
    deps = {r['shot_key']:(r['previous_shot_key'],r['transition']) for r in con.execute(
        'SELECT * FROM shot_dependencies WHERE storyboard_id=?',(bid,))}
    require(deps == {s['shot_key']:(s['previous_shot_key'],s['transition'])
                     for s in result['plan']['shots'] if s.get('previous_shot_key')},
            'Dependency projection mismatch')
    seal = con.execute('SELECT * FROM storyboard_seals WHERE storyboard_id=?', (bid,)).fetchone()
    if seal:
        require(sha(seal['seal_json']) == seal['seal_sha256'], 'Storyboard seal hash mismatch')
    result['seal'] = json.loads(seal['seal_json']) if seal else None
    return result


def apply_delta(before, delta):
    """V4 uses explicit top-level set/remove; nested values are replaced atomically."""
    require(isinstance(before, dict) and isinstance(delta, dict) and
            set(delta) == {'set', 'remove'}, 'Continuity requires set/remove delta')
    values, removed = delta['set'], delta['remove']
    require(isinstance(values, dict) and isinstance(removed, list) and
            all(isinstance(k, str) for k in removed) and len(removed) == len(set(removed)) and
            not set(values).intersection(removed), 'Invalid continuity delta')
    require(all(k in before for k in removed), 'Cannot remove unknown state key')
    return {**{k:v for k,v in before.items() if k not in removed}, **values}


def latest_qa(con, prompt_id):
    return one(con, '''SELECT * FROM qa_reports WHERE subject_kind='PROMPT' AND subject_id=?
                    ORDER BY rowid DESC LIMIT 1''', (prompt_id,), 'Prompt QA')


def require_prompt_qa(qa, shot_id):
    decision = json.loads(qa['report_json']).get('policy_decision', {})
    require(qa['verdict'] == 'PASS' and nonempty(qa['policy_ref']) and
            decision.get('scope') == 'PROMPT_DERIVATION' and decision.get('decision') == 'PASS' and
            decision.get('shot_id') == shot_id and nonempty(decision.get('policy_version')) and
            nonempty(decision.get('evidence')), f'PROMPT_QA_REQUIRED: {shot_id}')


def compare_storyboards(con, old_id, new_id):
    """Find the minimal direct changes and descendants whose state needs rechecking."""
    old,new = get_storyboard(con,old_id),get_storyboard(con,new_id)
    require(old['story_id'] == new['story_id'], 'Cannot compare different stories')
    a = {r['shot_key']:r for r in old['slots']}
    b = {r['shot_key']:r for r in new['slots']}
    added,removed = set(b)-set(a),set(a)-set(b)
    changed = {k for k in a.keys() & b.keys() if a[k]['context_sha256'] != b[k]['context_sha256']}
    affected = added | changed
    # All predecessors precede descendants; propagate only on that dependency graph.
    for r in new['slots']:
        if json.loads(r['spec_json']).get('previous_shot_key') in affected:
            affected.add(r['shot_key'])
    return {'added':sorted(added),'removed':sorted(removed),'changed':sorted(changed),
            'recheck_descendants':sorted(affected-added-changed),
            'candidate_reuse':sorted(set(b)-affected),
            'order_changed': [r['shot_key'] for r in old['slots']] != [r['shot_key'] for r in new['slots']]}


def _snapshots(con, shot_id):
    return {r['role_key']: {k: json.loads(r[k+'_json']) for k in ('before','delta','after')}
            for r in con.execute('''SELECT c.*,r.role_key FROM continuity_snapshots c
                LEFT JOIN story_roles r ON r.id=c.story_role_id WHERE c.shot_id=?''', (shot_id,))}


def _state_digest(states):
    return sha(js([{'role_key': k, **v} for k,v in sorted(states.items(), key=lambda kv: kv[0] or '')]))


def _bindings(con, board, bindings):
    plan = board['plan']
    require(isinstance(bindings, dict) and set(bindings) == {r['shot_key'] for r in board['slots']},
            'Bindings must cover every slot exactly')
    blocked = [r for r in plan['coverage'] if r['status'] in ('UNRESOLVED','UNSUPPORTED_CONTENT')]
    require(not blocked, 'SOURCE_COVERAGE_BLOCKED: unresolved or unsupported events remain')
    require(board['slots'], 'No visual shots to seal')
    history, result = {}, []
    for slot in board['slots']:
        k = slot['shot_key']
        s = json.loads(slot['spec_json'])
        binding = bindings[k]
        shot = one(con, 'SELECT * FROM shots WHERE id=?', (binding['shot_id'],), 'Shot')
        require(shot['shot_key'] == k and shot['beat_id'] == slot['beat_id'], f'SHOT_BINDING_MISMATCH: {k}')
        spec = json.loads(shot['shot_spec_json'])
        require(spec.get('visual_context_sha256') == slot['context_sha256'], f'STALE_VISUAL_CONTEXT: {k}')
        require(spec.get('camera') == s['camera'] and spec.get('focus') == s['focus'] and
                spec.get('location_key') == s['location_key'], f'SHOT_DIRECTION_MISMATCH: {k}')
        roles = {r['role_key'] for r in con.execute('''SELECT r.role_key FROM shot_participants p
            JOIN story_roles r ON r.id=p.story_role_id WHERE p.shot_id=?''', (shot['id'],))}
        require(roles == set(s['role_keys']), f'PARTICIPANT_MISMATCH: {k}')
        mapped_events = {r['event_id'] for r in plan['coverage'] if r.get('shot_key') == k}
        require(shot['source_event_id'] is None or shot['source_event_id'] in mapped_events,
                f'SOURCE_EVENT_MISMATCH: {k}')
        for interaction in spec.get('interactions', []):
            event_id = interaction.get('event_id')
            require(event_id in mapped_events, f'INTERACTION_EVENT_REQUIRED: {k}')
            event = one(con, '''SELECT e.*,a.role_key AS actor_key,t.role_key AS target_key
                FROM story_events e LEFT JOIN story_roles a ON a.id=e.actor_role_id
                LEFT JOIN story_roles t ON t.id=e.target_role_id WHERE e.id=?''',(event_id,), 'Interaction Event')
            require(interaction.get('actor_role_key') == event['actor_key'] and
                    interaction.get('target_role_key') == event['target_key'],
                    f'ACTOR_TARGET_MISMATCH: {k}')
        prompt = one(con, 'SELECT * FROM shot_prompts WHERE id=? AND shot_id=?',
                     (binding['prompt_id'],shot['id']), 'Prompt for shot')
        require(sha(shot['shot_spec_json']) == prompt['shot_spec_sha256'] and
                sha(prompt['prompt_text']) == prompt['prompt_sha256'], f'PROMPT_HASH_MISMATCH: {k}')
        qa = latest_qa(con, prompt['id'])
        require_prompt_qa(qa,shot['id'])
        states = _snapshots(con, shot['id'])
        require(set(states) == roles | {None}, f'CONTINUITY_SNAPSHOTS_MISSING: {k}')
        inherited = dict(history.get(s.get('previous_shot_key'), {}))
        for role, state in states.items():
            require(apply_delta(state['before'],state['delta']) == state['after'],
                    f'CONTINUITY_DELTA_MISMATCH: {k}/{role}')
            if role in inherited:
                require(state['before'] == inherited[role], f'CONTINUITY_BREAK: {k}/{role}')
            inherited[role] = state['after']
        # Scene state is world-space; camera/screen placement lives in ShotSpec, not here.
        require(states[None]['after'].get('location_key') == s['location_key'],
                f'SCENE_LOCATION_MISMATCH: {k}')
        history[k] = inherited
        result.append({'shot_key': k,'shot_order': slot['shot_order'],'branch_key': slot['branch_key'],
                       'purpose': slot['purpose'],'shot_id':shot['id'],'prompt_id':prompt['id'],
                       'qa_id':qa['id'],'continuity_sha256':_state_digest(states),
                       'context_sha256':slot['context_sha256']})
    return result


def seal_storyboard(con, bid, obj):
    con.execute('BEGIN IMMEDIATE')
    try:
        board = get_storyboard(con, bid)
        story, plan = current_plan(con, board['story_id'])
        slots = _validate_plan(con,board['story_id'],board['plan'],story,plan)
        require(all(sha(js(slots[r['shot_key']])) == r['context_sha256'] for r in board['slots']),
                'STALE_VISUAL_CONTEXT')
        bindings = _bindings(con, board, obj['bindings'])
        # A semantic sequence audit is explicitly supplied by the agent; not inferred from syntax.
        review = obj['sequence_qa']
        require(review.get('verdict') == 'PASS' and nonempty(review.get('evidence')),
                'SEQUENCE_QA_REQUIRED')
        seal = {'bindings':bindings,'sequence_qa':review,'plan_sha256':sha(js(board['plan']))}
        body = js(seal)
        existing = con.execute('SELECT * FROM storyboard_seals WHERE storyboard_id=?',(bid,)).fetchone()
        if existing:
            require(existing['seal_json'] == body, 'SEALED_STORYBOARD_IMMUTABLE: create new revision')
        else:
            con.execute('INSERT INTO storyboard_seals(storyboard_id,seal_json,seal_sha256) VALUES(?,?,?)',
                        (bid,body,sha(body)))
        con.commit()
        return seal
    except BaseException:
        con.rollback()
        raise


def sealed_selection(con, story_id, board_id=None):
    """Return pinned sequence; legacy stories without any storyboard return None."""
    if board_id is None:
        row = con.execute('SELECT id FROM storyboards WHERE story_id=? ORDER BY revision DESC LIMIT 1',
                          (story_id,)).fetchone()
        if row is None:
            return None
        board_id = row['id']
        current = one(con,'SELECT current_revision FROM stories WHERE id=?',(story_id,),'Story')
        board = get_storyboard(con,board_id)
        require(board['story_revision'] == current['current_revision'], 'STALE_STORYBOARD: create new revision')
        story, plan = current_plan(con,story_id)
        contexts = _validate_plan(con,story_id,board['plan'],story,plan)
        require(all(sha(js(contexts[r['shot_key']])) == r['context_sha256'] for r in board['slots']),
                'STALE_VISUAL_CONTEXT')
    else:
        board = get_storyboard(con,board_id)
    require(board['story_id'] == story_id, 'Storyboard belongs to another story')
    seal = one(con,'SELECT * FROM storyboard_seals WHERE storyboard_id=?',(board_id,),'Storyboard seal')
    require(sha(seal['seal_json']) == seal['seal_sha256'], 'Storyboard seal hash mismatch')
    stored = json.loads(seal['seal_json'])
    require(stored['plan_sha256'] == sha(js(board['plan'])), 'Storyboard plan hash mismatch')
    for b in stored['bindings']:
        require(_state_digest(_snapshots(con,b['shot_id'])) == b['continuity_sha256'],
                'Sealed continuity changed')
        qa = latest_qa(con,b['prompt_id'])
        require(qa['verdict'] == 'PASS', 'Sealed prompt QA no longer PASS')
        require_prompt_qa(qa,b['shot_id'])
    return board_id, stored['bindings']
