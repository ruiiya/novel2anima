"""Conservative, deterministic narrative checks for 1-person or 2-person stories.

No invented catalog tag IDs. Legacy plans are accepted with warnings; strict errors
are raised only for broken explicit scene semantics (actor, state, prop, reaction).
Python 3.9+ stdlib only.
"""
from dataclasses import dataclass, asdict
from typing import Optional
import json
import re

from tag_roles import BODY_STATE_TAGS

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

# Semantic sets used by the compiler gate. These are intentionally small and
# deterministic; catalog role rows are noisy and must not be the only source.
NUDE_STATE = {'nude', 'completely_nude', 'topless', 'bottomless'}
FULL_NUDITY = {'nude', 'completely_nude'}
BODY_STATE_IN_OUTFIT = NUDE_STATE | set(BODY_STATE_TAGS)
CLOTHING_HINTS = {
    'school_uniform', 'idol_clothes', 'maid', 'maid_outfit',
    'apron', 'white_apron', 'black_dress', 'white_shirt', 'black_blazer',
    'black_skirt', 'black_pleated_skirt', 'black_thighhighs', 'thighhighs',
    'bikini', 'white_bikini', 'micro_bikini', 'string_bikini', 'side-tie_bikini',
    'shirt', 'skirt', 'dress', 'blazer', 'gym_uniform', 'buruma', 'blue_buruma',
    'white_buruma', 'purple_buruma', 'black_buruma', 'pink_buruma', 'panties',
    'bra', 'loafers', 'sneakers', 'black_boots', 'boots',
}
FLOOR_ACTIONS = {
    'sitting', 'sitting_on_ground', 'sitting_on_desk', 'kneeling', 'crouching',
    'lying', 'lying_on_back', 'missionary', 'prone_bone', 'mating_press',
    'cowgirl_position', 'reverse_cowgirl_position', 'upright_straddle',
    'doggystyle', 'spooning', 'full_nelson', 'lotus_position', 'fellatio',
    'deepthroat', 'cunnilingus', 'tribadism', 'sex', 'vaginal',
}
NONSTANDING_ACTIONS = FLOOR_ACTIONS
SENSITIVE_ACTIONS = {
    'fingering', 'masturbation', 'spread_pussy', 'presenting', 'presenting_pussy',
    'clitoral_stimulation', 'object_insertion', 'vibrator', 'dildo', 'sex',
    'vaginal', 'missionary', 'cowgirl_position', 'reverse_cowgirl_position',
    'prone_bone', 'mating_press', 'standing_sex', 'fellatio', 'deepthroat',
    'cunnilingus',
}
LOOKING_ACTIONS = {'looking_around', 'looking_back', 'looking_at_viewer', 'looking_down',
                   'looking_up', 'looking_away', 'looking_to_the_side'}
PROP_WORDS = {'door', 'earpiece', 'gun', 'rifle', 'knife', 'microphone', 'baton',
              'vibrator', 'dildo', 'rope', 'leash'}
FILLER_WORDS = {'slowly', 'harder'}
SPATIAL_CONFLICT_PAIRS = {frozenset(('stage', 'backstage')),
                          frozenset(('indoors', 'outdoors'))}

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
                     purpose)
        repeats = repeats + 1 if signature == previous_signature and signature[0] else 1
        if repeats >= 4 and purpose not in {'hold', 'reaction_hold', 'quiet_pause'}:
            issues.append(Issue('WARN', 'NO_STORY_PROGRESS', n,
                                'Four consecutive shots repeat the same action, expression, and purpose'))
        previous_signature = signature
    for who, evt, _ in awaiting:
        issues.append(Issue('ERROR', 'MISSING_REQUIRED_REACTION', len(timeline),
                            f'{who} did not react to {evt} before story ended'))
    return issues


def _names(shot, group):
    return set(_refs(shot.get(group) or []))


def _tag_ids(shot):
    out = set()
    for group in ('identity', 'outfit', 'body_state', 'action', 'expression',
                  'pose', 'motion', 'camera', 'cast', 'props'):
        for item in shot.get(group) or []:
            if isinstance(item, dict) and item.get('tagId') is not None:
                out.add(item['tagId'])
    return out


def _phase_row(contract, shot_no):
    for row in contract or []:
        try:
            if int(row.get('start', 0)) <= shot_no <= int(row.get('end', 0)):
                return row
        except (TypeError, ValueError):
            continue
    return None


def validate_shot_semantics(shots, cast=None, phase_contract=None, blocked_ids=None):
    """Cross-field checks that tag-level QA cannot see.

    The function is deliberately conservative and catalog-independent: callers
    pass the same shot_spec_json shape used by seed_plan and check_prompts.
    """
    blocked_ids = set(blocked_ids or ())
    issues = []
    timeline = sorted(shots, key=lambda s: int(s.get('n', s.get('shot_no', 0))))
    for shot in timeline:
        n = int(shot.get('n', shot.get('shot_no', 0)))
        outfit = _names(shot, 'outfit')
        body = _names(shot, 'body_state')
        actions = _names(shot, 'action')
        expression = _names(shot, 'expression')
        pose = _names(shot, 'pose')
        props = _names(shot, 'props')
        all_names = set()
        for group in ('identity', 'outfit', 'body_state', 'action', 'expression',
                      'pose', 'motion', 'camera', 'cast', 'props'):
            all_names |= _names(shot, group)
        gaze = set((shot.get('character_gaze') or {}).values())
        gaze |= set(shot.get('gaze') or [])

        if blocked_ids and (_tag_ids(shot) & blocked_ids):
            issues.append(Issue('ERROR', 'CONTENT_SAFETY_BLOCK', n,
                                'blocked content tag present in shot'))

        invalid_outfit = outfit & BODY_STATE_IN_OUTFIT
        if invalid_outfit:
            issues.append(Issue('ERROR', 'TAG_ROLE_INVALID', n,
                                'body/anatomy tags in outfit: %s' % ', '.join(sorted(invalid_outfit))))

        nude = (outfit | body) & NUDE_STATE
        if (outfit | body) & FULL_NUDITY and (outfit & CLOTHING_HINTS):
            issues.append(Issue('ERROR', 'WARDROBE_STATE_CONFLICT', n,
                                'nude state with clothing: %s' % ', '.join(sorted(nude | (outfit & CLOTHING_HINTS)))))

        stances = {STANCE[x] for x in pose if x in STANCE}
        if len(stances) > 1:
            issues.append(Issue('ERROR', 'POSE_CONFLICT', n,
                                'multiple stances in one shot: %s' % ', '.join(sorted(stances))))
        if stances == {'standing'} and actions & NONSTANDING_ACTIONS:
            issues.append(Issue('ERROR', 'POSE_ACTION_CONFLICT', n,
                                'standing pose with action requiring another posture: %s'
                                % ', '.join(sorted(actions & NONSTANDING_ACTIONS))))

        if 'closed_eyes' in expression and (actions & LOOKING_ACTIONS or gaze):
            issues.append(Issue('ERROR', 'EYE_GAZE_CONFLICT', n,
                                'closed_eyes with a looking action/gaze target'))

        background = str(shot.get('background') or '')
        scene_tags = set()
        scene = shot.get('scene') or {}
        if isinstance(scene, dict):
            scene_tags |= set(scene.get('tags') or [])
        scene_tags |= {x.strip() for x in re.split(r'[,;]', background) if x.strip()}
        for pair in SPATIAL_CONFLICT_PAIRS:
            if pair <= scene_tags:
                issues.append(Issue('WARN', 'SPATIAL_CONFLICT', n,
                                    'incompatible scene areas: %s' % ' + '.join(sorted(pair))))

        caption = str(shot.get('caption') or '').lower()
        if any(re.search(r'\b%s\b' % re.escape(word), caption) for word in FILLER_WORDS):
            issues.append(Issue('WARN', 'CAPTION_TEMPLATE_FILLER', n,
                                'caption contains template adverb'))
        if 'during the ' in caption or re.search(r'\bact\b.{0,24}\bends?\b', caption):
            issues.append(Issue('WARN', 'CAPTION_META_LEAK', n,
                                'caption contains phase/meta text'))
        for prop in sorted(PROP_WORDS):
            implied = any(prop in name for name in all_names)
            if re.search(r'\b%s\b' % re.escape(prop), caption) and not (prop in props or implied):
                issues.append(Issue('ERROR', 'PROP_NOT_BOUND', n,
                                    'caption mentions unbound prop: %s' % prop))

        phase = _phase_row(phase_contract, n)
        if phase:
            phase_id = phase.get('id')
            if phase_id and shot.get('phase') and phase_id != shot.get('phase'):
                issues.append(Issue('ERROR', 'PHASE_CONTRACT_MISMATCH', n,
                                    'phase=%s but contract says %s' % (shot.get('phase'), phase_id)))
            if phase.get('allow_sensitive') is False and actions & SENSITIVE_ACTIONS:
                issues.append(Issue('ERROR', 'PHASE_EVENT_OUT_OF_BOUNDS', n,
                                    'sensitive action outside allowed phase: %s'
                                    % ', '.join(sorted(actions & SENSITIVE_ACTIONS))))
            wardrobe = phase.get('wardrobe')
            if wardrobe == 'dressed' and nude:
                issues.append(Issue('ERROR', 'PHASE_EVENT_OUT_OF_BOUNDS', n,
                                    'nude state during dressed phase'))
            if wardrobe == 'undress' and (outfit | body) & FULL_NUDITY:
                issues.append(Issue('ERROR', 'PHASE_EVENT_OUT_OF_BOUNDS', n,
                                    'full nudity during undress phase'))
            if wardrobe == 'nude' and outfit & CLOTHING_HINTS:
                issues.append(Issue('ERROR', 'WARDROBE_STATE_CONFLICT', n,
                                    'clothing remains in nude phase: %s'
                                    % ', '.join(sorted(outfit & CLOTHING_HINTS))))
    return issues


def scene_line(shot, plan):
    """Compiled background line. One precedence order for compiler and QA.

    `scene.location` stays a logical place name; only render/background sources
    feed the prompt line.
    """
    shot = shot or {}
    plan = plan or {}
    scene = shot.get('scene') or plan.get('scene') or {}
    render = shot.get('render_style') or plan.get('render_style') or {}
    if not isinstance(scene, dict):
        scene = {}
    if not isinstance(render, dict):
        render = {}
    return (render.get('background_style')
            or shot.get('background_line')
            or scene.get('background_line')
            or plan.get('background_line')
            or (plan.get('style_json') or {}).get('background')
            or 'plain background')

def validate_phase_contract(shots, contract):
    """Contract must be ordered, contiguous, gap-free and cover every shot."""
    issues = []
    if not contract:
        return issues
    rows = []
    for row in contract:
        try:
            start, end = int(row.get('start', 0)), int(row.get('end', 0))
        except (TypeError, ValueError):
            issues.append(Issue('ERROR', 'PHASE_CONTRACT_INVALID', 0,
                                'unreadable range: %r' % (row,)))
            continue
        if start < 1 or end < start:
            issues.append(Issue('ERROR', 'PHASE_CONTRACT_INVALID', 0,
                                '%s: bad range %d..%d' % (row.get('id'), start, end)))
            continue
        rows.append((start, end, row.get('id'), row.get('wardrobe')))
    rows.sort()
    if rows:
        if rows[0][0] != 1:
            issues.append(Issue('ERROR', 'PHASE_CONTRACT_GAP', 0,
                                'contract starts at shot %d, expected 1' % rows[0][0]))
        for (s1, e1, id1, _w1), (s2, e2, id2, _w2) in zip(rows, rows[1:]):
            if s2 <= e1:
                issues.append(Issue('ERROR', 'PHASE_CONTRACT_OVERLAP', 0,
                                    '%s %d..%d overlaps %s %d..%d' % (id1, s1, e1, id2, s2, e2)))
            elif s2 != e1 + 1:
                issues.append(Issue('ERROR', 'PHASE_CONTRACT_GAP', 0,
                                    'gap between %s (ends %d) and %s (starts %d)'
                                    % (id1, e1, id2, s2)))
        covered = set()
        for start, end, _id, _w in rows:
            covered.update(range(start, end + 1))
        nums = sorted(int(x.get('n', x.get('shot_no', 0))) for x in shots)
        missing = [n for n in nums if n not in covered]
        extra = [n for n in sorted(covered) if n > (nums[-1] if nums else 0)]
        if missing:
            issues.append(Issue('ERROR', 'PHASE_CONTRACT_GAP', missing[0],
                                'shots outside every phase: %s' % missing[:8]))
        if extra:
            issues.append(Issue('ERROR', 'PHASE_CONTRACT_GAP', 0,
                                'contract covers shots past the end: %s' % extra[:8]))
    return issues

def validate_act_level(shots):
    """Act-level progression checks. Kept separate so synthetic unit tests can
    call it without needing a catalog or a DB."""
    issues = []
    timeline = sorted(shots, key=lambda s: int(s.get('n', s.get('shot_no', 0))))
    if len(timeline) < 5:
        return issues
    stances = []
    action_sets = []
    floor_actions = set()
    for shot in timeline:
        n = int(shot.get('n', shot.get('shot_no', 0)))
        pose = _names(shot, 'pose')
        actions = _names(shot, 'action')
        local = {STANCE[x] for x in pose if x in STANCE}
        if local:
            stances.append(next(iter(local)) if len(local) == 1 else 'mixed')
        action_sets.append(tuple(sorted(actions)))
        if actions & NONSTANDING_ACTIONS:
            floor_actions.add(n)
    detected = [x for x in stances if x != 'mixed']
    if (detected and len(set(detected)) == 1 and detected[0] == 'standing'
            and floor_actions and len(detected) >= max(3, len(timeline) // 2)):
        issues.append(Issue('ERROR', 'POSE_STUCK_DEFAULT', timeline[0].get('n', 1),
                            'act uses floor/sex actions but every pose is standing'))
    unique = len(set(action_sets))
    if len(action_sets) >= 10 and unique < max(6, int(len(action_sets) * 0.5)):
        issues.append(Issue('WARN', 'LOW_EVENT_PROGRESS', timeline[0].get('n', 1),
                            '%d unique action sets in %d shots' % (unique, len(action_sets))))
    return issues


def validate_batch_plans(plans):
    """Flag near-identical action sequences between plans in one batch."""
    issues = []
    entries = sorted(plans.items() if isinstance(plans, dict) else enumerate(plans))
    for i, (name_a, plan_a) in enumerate(entries):
        shots_a = plan_a.get('shots') or []
        for name_b, plan_b in entries[i + 1:]:
            shots_b = plan_b.get('shots') or []
            if not shots_a or not shots_b:
                continue
            same = sum(tuple(sorted(_refs(a.get('action')))) == tuple(sorted(_refs(b.get('action'))))
                       for a, b in zip(shots_a, shots_b))
            ratio = same / float(min(len(shots_a), len(shots_b)))
            if same >= 10 and ratio >= 0.30:
                issues.append(Issue('WARN', 'BATCH_TEMPLATE_CLONE', 0,
                                    '%s and %s share %d/%d action shots'
                                    % (name_a, name_b, same, min(len(shots_a), len(shots_b)))))
    return issues


def validate_plan(plan, phase_contract=None):
    chars = plan.get('characters', [plan['character']] if plan.get('character') else [])
    cast = [c['code'] for c in chars]
    shots = plan.get('shots') or []
    pc = phase_contract if phase_contract is not None else (plan.get('act') or {}).get('phase_contract')
    issues = validate(shots, cast)
    issues += validate_phase_contract(shots, pc)
    issues += validate_shot_semantics(shots, cast=cast, phase_contract=pc)
    issues += validate_act_level(shots)
    content = str((plan.get('project') or {}).get('content_profile', '')).lower()
    if content in ('nsfw', 'explicit'):
        missing = [c.get('code') for c in chars
                   if c.get('adult') is not True
                   and (c.get('identity_json') or {}).get('adult') is not True]
        if missing:
            issues.append(Issue('ERROR', 'CONTENT_SAFETY_BLOCK', 0,
                                'NSFW plan requires explicit adult=true: %s' % ', '.join(map(str, missing))))
    return issues


def validate_specs(specs, phase_contract=None, blocked_ids=None):
    shots = []
    for n, spec in specs:
        d = dict(spec)
        d['n'] = n
        shots.append(d)
    return (validate(shots)
            + validate_phase_contract(shots, phase_contract)
            + validate_shot_semantics(shots, phase_contract=phase_contract, blocked_ids=blocked_ids)
            + validate_act_level(shots))


def report(issues):
    return {'errors': sum(x.level == 'ERROR' for x in issues),
            'warnings': sum(x.level == 'WARN' for x in issues),
            'findings': [x.to_dict() for x in issues]}
