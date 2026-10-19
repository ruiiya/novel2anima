"""Conservative, deterministic narrative checks for 1-person or 2-person stories.

No invented catalog tag IDs. Legacy plans are accepted with warnings; strict errors
are raised only for broken explicit scene semantics (actor, state, prop, reaction).
Python 3.9+ stdlib only.
"""
from dataclasses import dataclass, asdict
from typing import Optional
import json

STANCE = {
    'standing': 'standing', 'standing_up': 'standing', 'sitting': 'sitting',
    'sitting_on_chair': 'sitting', 'sitting_on_desk': 'sitting',
    'kneeling': 'kneeling', 'squatting': 'crouching', 'crouching': 'crouching',
    'lying': 'lying', 'lying_on_back': 'lying', 'lying_on_stomach': 'lying',
}
POSE_BRIDGE = {
    ('sitting', 'standing'): 'stand_up', ('crouching', 'standing'): 'stand_up',
    ('kneeling', 'standing'): 'stand_up', ('lying', 'standing'): 'get_up',
    ('standing', 'sitting'): 'sit_down', ('standing', 'crouching'): 'crouch',
    ('standing', 'kneeling'): 'kneel', ('standing', 'lying'): 'lie_down',
    ('lying', 'sitting'): 'sit_up', ('sitting', 'lying'): 'lie_down',
    ('lying', 'kneeling'): 'get_up', ('lying', 'crouching'): 'get_up',
}
CUTS = {'time_cut', 'scene_cut', 'montage', 'offscreen_transition'}
PURPOSES = {'setup', 'action', 'interaction', 'reaction', 'result', 'transition',
            'establishing', 'hold', 'reaction_hold', 'quiet_pause', 'montage'}
NO_ACTION_OK = {'establishing', 'hold', 'reaction_hold', 'quiet_pause', 'montage', 'setup'}

@dataclass(frozen=True)
class Issue:
    level: str
    code: str
    shot: int
    detail: str
    suggestion: str = ''

    def to_dict(self):
        return asdict(self)


def _refs(xs):
    if not xs:
        return []
    out = []
    for x in xs:
        if isinstance(x, dict):
            out.append(str(x.get('name') or '').strip())
        else:
            out.append(str(x).rpartition(':')[0] if str(x).rpartition(':')[2].isdigit() else str(x))
    return [x for x in out if x]


def _codes(shot):
    p = shot.get('participants') or []
    return [x.get('code') if isinstance(x, dict) else x for x in p]


def _pose(shot, code):
    cp = shot.get('character_poses') or {}
    if code in cp:
        poses = _refs(cp[code])
    else:
        participants = shot.get('participants') or []
        d = next((x for x in participants if isinstance(x, dict) and x.get('code') == code), None)
        # Never pretend a pooled pose applies to BOTH people. Missing role-specific
        # data is unknown (and can be flagged), not a fabricated shared state.
        if len(participants) > 1 and not (d and d.get('pose')):
            return None
        poses = _refs((d or {}).get('pose') or shot.get('pose'))
    poses = [STANCE[x] for x in poses if x in STANCE]
    return poses[0] if poses else None


def _primary(shot):
    seq = shot.get('sequence') or {}
    return seq.get('primaryAction') or seq.get('action') or ''


def validate(shots, cast=None):
    """Return Issue list. No implicit mutation or forced shot count.

    Optional `sequence` contract per shot:
      {purpose, actor, target, primaryAction, poseBefore, poseAfter,
       object, holderBefore, holderAfter, cut, eventId, reactionRequired,
       reactionTo, supportActions, visualEvidence}
    """
    cast = set(cast or [])
    issues = []
    previous_pose = {}
    prop_holder = {}
    awaiting = []   # (target, event_id, deadline)
    previous_signature = None
    repeats = 0
    seen_n = set()
    legacy_purpose_warned = False
    timeline = sorted(shots, key=lambda s: int(s.get('n', s.get('shot_no', 0))))
    for i, shot in enumerate(timeline):
        n = int(shot.get('n', shot.get('shot_no', i + 1)))
        if n in seen_n:
            issues.append(Issue('ERROR', 'DUPLICATE_SHOT_NO', n, 'Duplicate shot number'))
        seen_n.add(n)
        codes = _codes(shot)
        seq = shot.get('sequence') or {}
        purpose = seq.get('purpose') or shot.get('purpose') or ''
        actor = seq.get('actor')
        target = seq.get('target')
        if cast and (set(codes) - cast):
            issues.append(Issue('ERROR', 'UNKNOWN_PARTICIPANT', n, str(sorted(set(codes) - cast))))
        if len(set(codes)) != len(codes):
            issues.append(Issue('ERROR', 'DUPLICATE_PARTICIPANT', n, str(codes)))
        if not codes or len(codes) > 2:
            level = 'ERROR' if seq else 'WARN'
            issues.append(Issue(level, 'CAST_SIZE_UNSUPPORTED', n,
                                'Quality rules are optimized for solo/duo; other casts require manual review'))
        if actor and actor not in codes:
            issues.append(Issue('ERROR', 'ACTOR_MISMATCH', n, f'Actor {actor!r} not present'))
        if target and target not in (cast or set(codes)):
            issues.append(Issue('ERROR', 'TARGET_UNKNOWN', n, f'Target {target!r} not in cast'))
        if actor and target and actor == target and purpose == 'interaction':
            issues.append(Issue('ERROR', 'ACTOR_TARGET_MISMATCH', n, 'Interaction targets same actor'))
        if purpose and purpose not in PURPOSES:
            issues.append(Issue('WARN', 'UNKNOWN_PURPOSE', n, purpose))
        if purpose and purpose not in NO_ACTION_OK and not (_primary(shot) or _refs(shot.get('action'))):
            issues.append(Issue('ERROR', 'ACTION_REQUIRED', n, f'{purpose} shot needs a primary action'))
        if not purpose and not legacy_purpose_warned:
            issues.append(Issue('WARN', 'MISSING_SHOT_PURPOSE', n,
                                'Legacy/unstructured story: add purpose to increase QA coverage'))
            legacy_purpose_warned = True
        if len(codes) == 2 and not (shot.get('character_actions') or
                                     any(isinstance(p, dict) and p.get('action') for p in (shot.get('participants') or []))):
            if not any(i.code == 'UNSCOPED_DUO_ACTION' for i in issues):
                issues.append(Issue('WARN', 'UNSCOPED_DUO_ACTION', n,
                                    'Specify character_actions so the prompt assigns gestures to the correct person'))
        if purpose == 'interaction' and target and 'reactionRequired' not in seq:
            issues.append(Issue('WARN', 'REACTION_POLICY_MISSING', n,
                                'Declare reactionRequired=true/false so silence is intentional'))
        cut = seq.get('cut') or shot.get('cut') or ''
        boundary = cut in CUTS
        for code in codes:
            here = _pose(shot, code)
            prior = previous_pose.get(code)
            if here and prior and here != prior and not boundary:
                action_names = set(_refs(shot.get('action'))) | set(_refs((shot.get('character_actions') or {}).get(code)))
                action_names |= set(seq.get('supportActions') or [])
                if _primary(shot):
                    action_names.add(_primary(shot))
                bridge = POSE_BRIDGE.get((prior, here), 'change_posture')
                cues = {bridge, 'standing_up', 'sitting_down', 'getting_up', 'sitting', 'crouching', 'kneeling', 'lying_down'}
                if not (action_names & cues) and not seq.get('poseBefore'):
                    level = 'ERROR' if seq and seq.get('actor') == code and purpose not in {'montage', 'setup'} else 'WARN'
                    issues.append(Issue(level, 'POSE_BRIDGE_MISSING', n,
                                        f'{code}: {prior} -> {here} without visible transition/cut',
                                        f'Add {bridge}, mark valid cut, or show transition in caption'))
            explicit_pre = seq.get('poseBefore') if seq.get('actor') == code else None
            explicit_after = seq.get('poseAfter') if seq.get('actor') == code else None
            if explicit_pre and prior and prior != explicit_pre and not boundary:
                issues.append(Issue('ERROR', 'PRECONDITION_POSE', n,
                                    f'{code}: expected {explicit_pre}, previous {prior}',
                                    'Insert bridge action or mark intentional cut'))
            if explicit_after and here and explicit_after != here:
                issues.append(Issue('ERROR', 'POSE_EFFECT_MISMATCH', n,
                                    f'{code}: poseAfter={explicit_after} but frame pose={here}'))
            if explicit_after or here:
                previous_pose[code] = explicit_after or here
        prop = seq.get('object')
        if prop:
            before = seq.get('holderBefore')
            after = seq.get('holderAfter')
            known = prop_holder.get(prop)
            if before is not None and known is not None and before != known and not boundary:
                issues.append(Issue('ERROR', 'PROP_OWNERSHIP_JUMP', n,
                                    f'{prop}: expected holder {known}, declared {before}'))
            if after is not None:
                if before is not None and after != before and not (_primary(shot) or seq.get('supportActions')) and not boundary:
                    issues.append(Issue('ERROR', 'PROP_TRANSFER_WITHOUT_ACTION', n, prop))
                prop_holder[prop] = after
            elif before is not None:
                prop_holder[prop] = before
        event_id = seq.get('eventId') or f'shot:{n}'
        reaction_to = seq.get('reactionTo')
        awaiting = [(who, evt, dl) for (who, evt, dl) in awaiting if not (
            (reaction_to == evt and who in codes) or (purpose in {'reaction', 'reaction_hold'} and target == who and reaction_to is None))]
        missed = [(who, evt, dl) for who, evt, dl in awaiting if i >= dl]
        for who, evt, _ in missed:
            issues.append(Issue('ERROR', 'MISSING_REQUIRED_REACTION', n,
                                f'{who} did not react to {evt}',
                                'Add reaction or set reactionRequired=false if silence is intentional'))
        awaiting = [x for x in awaiting if i < x[2]]
        if seq.get('reactionRequired') and target:
            if target not in codes or not ((shot.get('reactions') or {}).get(target)):
                awaiting.append((target, event_id, i + 2))
        signature = (tuple(_refs(shot.get('action'))), tuple(sorted(_refs(shot.get('expression')))),
                     purpose, seq.get('eventId'))
        repeats = repeats + 1 if signature == previous_signature and signature[0] else 1
        if repeats >= 4 and purpose not in {'hold', 'reaction_hold', 'quiet_pause'}:
            issues.append(Issue('WARN', 'NO_STORY_PROGRESS', n,
                                'Four consecutive shots repeat the same action, expression, and purpose'))
        previous_signature = signature
    for who, evt, _ in awaiting:
        issues.append(Issue('ERROR', 'MISSING_REQUIRED_REACTION', len(timeline),
                            f'{who} did not react to {evt} before story ended'))
    return issues


def validate_plan(plan):
    cast = [c['code'] for c in plan.get('characters', [plan['character']] if plan.get('character') else [])]
    return validate(plan.get('shots') or [], cast)


def validate_specs(specs):
    shots = []
    for n, spec in specs:
        d = dict(spec)
        d['n'] = n
        shots.append(d)
    return validate(shots)


def report(issues):
    return {'errors': sum(x.level == 'ERROR' for x in issues),
            'warnings': sum(x.level == 'WARN' for x in issues),
            'findings': [x.to_dict() for x in issues]}
