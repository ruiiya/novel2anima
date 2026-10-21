"""Conservative, deterministic narrative checks for 1-person or 2-person stories.

No invented catalog tag IDs. Legacy plans are accepted with warnings; strict errors
are raised only for broken explicit scene semantics (actor, state, prop, reaction).
Python 3.9+ stdlib only.
"""
from dataclasses import dataclass, asdict
from typing import Optional
import collections
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
# Footwear, collars and event wristbands are accessories, not a second outfit.
# A nude phase may keep them on; a blazer/shirt may not.
NUDE_ACCESSORIES = {'black_boots', 'boots', 'barefoot', 'black_collar',
                    'orange_wristband', 'white_wristband', 'black_leash'}
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
# Interaction direction contract. `sequence` is the source of truth for the
# main directed event; ownership comes from `character_actions`, never from
# gender, tag order, caption pronouns or frame position.
DIRECTIONAL_ACTIONS = {
    'groping', 'spanking', 'fingering', 'handjob', 'footjob', 'sex', 'vaginal',
    'missionary', 'cowgirl_position', 'reverse_cowgirl_position', 'doggystyle',
    'standing_sex', 'paizuri', 'fellatio', 'deepthroat', 'cunnilingus',
    'headpat', 'head_pat',
}
# Verified semantic aliases (one physical act, different tag spellings).
ALIAS_GROUPS = [
    {'kiss', 'kissing'},
    {'headpat', 'head_pat'},
    {'hug', 'hugging', 'embrace'},
    {'pose', 'posing'},
    {'talk', 'talking'},
    {'undress', 'undressed', 'undressing'},
    {'missionary', 'on_top'},
    {'kneeling', 'kneel'},
]
ALIAS_INDEX = {name: i for i, group in enumerate(ALIAS_GROUPS) for name in group}
# One-direction composite clause per action tag. seed_plan renders it next to
# the caption; QA compares prompts against `shot_spec_json.interaction`.
DIRECTED_CLAUSE_TEMPLATES = {
    'headpat': 'pats {t} on the head',
    'groping': 'gropes {t}',
    'sex': 'has sex with {t}',
}
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


def actions_equal(a, b):
    """Alias-aware equality for action tokens (exact or verified group)."""
    a, b = str(a or '').strip().lower(), str(b or '').strip().lower()
    if not a or not b:
        return False
    if a == b:
        return True
    ia, ib = ALIAS_INDEX.get(a), ALIAS_INDEX.get(b)
    return ia is not None and ia == ib


def character_action_refs(shot, code):
    """Scoped action names of ONE participant. `character_actions[code]` wins;
    compiled specs may carry the same data as participants[].action. Never
    falls back to the pooled/global action line."""
    out = set(_refs((shot.get('character_actions') or {}).get(code)))
    if not out:
        for p in (shot.get('participants') or []):
            if isinstance(p, dict) and p.get('code') == code and p.get('action'):
                out |= set(_refs(p['action']))
    return out


def character_target(shot, code):
    for src in (shot.get('character_targets') or {},):
        if src.get(code):
            return src[code]
    for p in (shot.get('participants') or []):
        if isinstance(p, dict) and p.get('code') == code and p.get('target'):
            return p['target']
    return None


def validate_interaction_roles(shot, actor=None, target=None, purpose=None):
    """One shared validator for interaction orientation (raw plan AND compiled
    spec). `sequence` declares actor -> primaryAction -> target; the declared
    scopes must agree or the data is blocked. Heuristics are forbidden: gender,
    1boy/1girl labels, caption pronouns and frame order may never rewrite roles
    - contradictions FAIL so the author fixes the source.

    Codes: INTERACTION_TARGET_REQUIRED, INTERACTION_TARGET_NOT_IN_SHOT,
    INTERACTION_ROLE_MISMATCH, INTERACTION_ACTOR_ACTION_MISSING,
    INTERACTION_PRIMARY_ACTION_MISMATCH (WARN twin: ..._SOFT when the primary
    action is claimed only by the target - legacy review case),
    INTERACTION_TARGET_MISMATCH.
    """
    seq = shot.get('sequence') or {}
    purpose = purpose or seq.get('purpose') or shot.get('purpose') or ''
    primary = str(seq.get('primaryAction') or seq.get('action') or '')
    actor, target = actor or seq.get('actor'), target or seq.get('target')
    codes = _codes(shot)
    issues = []
    strict = purpose == 'interaction'
    if not strict and not (primary in DIRECTIONAL_ACTIONS and len(codes) > 1):
        return issues
    n = int(shot.get('n', shot.get('shot_no', 0)))
    if strict:
        if not target:
            issues.append(Issue('ERROR', 'INTERACTION_TARGET_REQUIRED', n,
                                'purpose=interaction needs a sequence.target'))
        elif codes and target not in codes:
            issues.append(Issue('ERROR', 'INTERACTION_TARGET_NOT_IN_SHOT', n,
                                'target %r is not in shot participants' % target))
    if not (actor and target) or actor == target:
        return issues          # ACTOR_TARGET_MISMATCH is reported by validate()
    aown = character_action_refs(shot, actor)
    town = character_action_refs(shot, target)
    if not aown:
        if primary and primary in town:
            issues.append(Issue('ERROR', 'INTERACTION_ROLE_MISMATCH', n,
                                'primary action %r scoped only to target %s while '
                                'sequence actor is %s' % (primary, target, actor),
                                'Declare character_actions[%s]=[%s]' % (actor, primary)))
        elif strict and not town:
            issues.append(Issue('ERROR', 'INTERACTION_ACTOR_ACTION_MISSING', n,
                                'directed interaction has no scoped action for '
                                'actor %s' % actor,
                                'Declare character_actions[%s]' % actor))
    elif primary and not any(actions_equal(primary, x) for x in aown):
        if any(actions_equal(primary, x) for x in town):
            issues.append(Issue('WARN', 'INTERACTION_PRIMARY_ACTION_SOFT', n,
                                '%s owns %r but sequence primaryAction is %r '
                                '(claimed by target %s)' %
                                (actor, ', '.join(sorted(aown)), primary, target),
                                'Confirm who performs the primary action'))
        else:
            issues.append(Issue('ERROR', 'INTERACTION_PRIMARY_ACTION_MISMATCH', n,
                                'sequence primaryAction %r is not among the '
                                'scoped actions of actor %s' % (primary, actor),
                                'Align primaryAction with character_actions[%s]' % actor))
    declared = character_target(shot, actor)
    if declared and target and str(declared) != str(target):
        issues.append(Issue('ERROR', 'INTERACTION_TARGET_MISMATCH', n,
                            'character_targets[%s]=%r conflicts with '
                            'sequence.target=%r' % (actor, declared, target),
                            'Keep one source of truth: sequence.target'))
    return issues


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
        if not codes:
            level = 'ERROR' if seq else 'WARN'
            issues.append(Issue(level, 'CAST_SIZE_UNSUPPORTED', n,
                                'Shot has no participants'))
        elif len(codes) > 4:
            level = 'ERROR' if seq else 'WARN'
            issues.append(Issue(level, 'CAST_SIZE_UNSUPPORTED', n,
                                'Quality rules support up to four participants'))
        if actor and actor not in codes:
            issues.append(Issue('ERROR', 'ACTOR_MISMATCH', n, f'Actor {actor!r} not present'))
        if target and target not in (cast or set(codes)):
            issues.append(Issue('ERROR', 'TARGET_UNKNOWN', n, f'Target {target!r} not in cast'))
        if actor and target and actor == target and purpose == 'interaction':
            issues.append(Issue('ERROR', 'ACTOR_TARGET_MISMATCH', n, 'Interaction targets same actor'))
        if purpose and purpose not in PURPOSES:
            issues.append(Issue('WARN', 'UNKNOWN_PURPOSE', n, purpose))
        issues += validate_interaction_roles(shot, actor=actor, target=target, purpose=purpose)
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

        # Check posture per character. Pooling Hoshino's kneeling with a fan's
        # standing must not look like one body in two poses, and a fan's floor
        # action must not conflict with Hoshino's standing pose.
        role_states = []
        ca = shot.get('character_actions') or {}
        cp = shot.get('character_poses') or {}
        for participant in (shot.get('participants') or []):
            if not isinstance(participant, dict):
                continue
            code = participant.get('code')
            role_actions = set(_refs(ca.get(code))) | set(_refs(participant.get('action')))
            role_poses = set(_refs(cp.get(code))) | set(_refs(participant.get('pose')))
            if role_actions or role_poses:
                role_states.append((code, role_poses, role_actions))
        if role_states:
            for code, role_poses, role_actions in role_states:
                stances = {STANCE[x] for x in role_poses if x in STANCE}
                if len(stances) > 1:
                    issues.append(Issue('ERROR', 'POSE_CONFLICT', n,
                                        '%s has multiple stances: %s' %
                                        (code, ', '.join(sorted(stances)))))
                if stances == {'standing'} and role_actions & NONSTANDING_ACTIONS:
                    issues.append(Issue('ERROR', 'POSE_ACTION_CONFLICT', n,
                                        '%s: standing pose with action requiring another posture: %s'
                                        % (code, ', '.join(sorted(role_actions & NONSTANDING_ACTIONS)))))
        else:
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
            if wardrobe == 'nude' and (outfit & CLOTHING_HINTS) - NUDE_ACCESSORIES:
                issues.append(Issue('ERROR', 'WARDROBE_STATE_CONFLICT', n,
                                    'clothing remains in nude phase: %s'
                                    % ', '.join(sorted((outfit & CLOTHING_HINTS) - NUDE_ACCESSORIES))))
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
    caps = collections.defaultdict(list)
    for shot in timeline:
        cap = str(shot.get('caption') or '').strip().lower()
        if cap:
            caps[cap].append(int(shot.get('n', shot.get('shot_no', 0))))
    for cap, nums in caps.items():
        if len(nums) > 1:
            issues.append(Issue('WARN', 'REPEATED_CAPTION', nums[0],
                                'caption repeated on shots %s: %s'
                                % (nums[:8], cap[:60])))
    prev = None
    for shot in timeline:
        n = int(shot.get('n', shot.get('shot_no', 0)))
        cap = str(shot.get('caption') or '').lower()
        outfit = set(_names(shot, 'outfit'))
        if prev and outfit == prev and re.search(
                r'\b(?:pulls?|pulled|takes?|took|slips?|removes?|strips?|unties?)\b'
                r'.{0,20}\b(?:off|down)\b', cap):
            issues.append(Issue('WARN', 'UNDRESS_NOT_REFLECTED', n,
                                'caption removes clothing but outfit is unchanged'))
        prev = outfit
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
            # Pose-clone guard: a few shared distinctive pose sets are fine;
            # heavy reuse across acts is a template smell. Bare single-tag
            # stances (e.g. plain 'standing') are base postures, not signatures.
            tuples_a = {tuple(sorted(_refs(a.get('pose')))) for a in shots_a if len(_refs(a.get('pose'))) >= 2}
            tuples_b = {tuple(sorted(_refs(b.get('pose')))) for b in shots_b if len(_refs(b.get('pose'))) >= 2}
            shared_poses = tuples_a & tuples_b
            if len(shared_poses) > 4:
                issues.append(Issue('WARN', 'BATCH_POSE_CLONE', 0,
                                    '%s and %s share %d unique pose sets'
                                    % (name_a, name_b, len(shared_poses))))
    return issues


EXPOSURE_LEVELS = {'L0', 'L1', 'L2'}
# Direct exposure = clearly unobstructed; partial = slips/peeks only.
DIRECT_EXPOSURE_TAGS = {'exposed_breasts', 'pussy'}
PARTIAL_EXPOSURE_TAGS = {'nipple_slip', 'sideboob', 'underboob', 'pussy_peek'}
# State tags that may only appear with full nudity plans; accepted never here.
COVERED_STATE_TAGS = {'bottomless', 'topless'}
# Benign body tags that do not count as exposure.
SECURE_BODY_TAGS = {'cleavage', 'bare_shoulders', 'navel', 'covered_navel',
                    'midriff', 'collarbone', 'stomach', 'shoulders'}
EXPOSURE_TAG_LEVEL = {
    'exposed_breasts': 'L2', 'pussy': 'L2',
    'nipple_slip': 'L1', 'sideboob': 'L1', 'underboob': 'L1', 'pussy_peek': 'L1',
}


def validate_exposure_contract(shots, contract):
    """Optional per-act exposure ratio contract (authoring-time gate).

    Layout (added by act_tools/generators/gen_six_sessions.py):
        {"levels": {"L0": 8, "L1": 20, "L2": 32},
         "l0_windows": [[1, 12], [52, 60]],
         "peak": [46, 55],
         "peak_min_l2": 8}
    Shots declare `exposure_level`. L2 requires a direct exposure tag, L1 a
    partial tag, L0 none of them; all levels must match the declared counts.
    Legacy plans without the contract are unaffected.
    """
    issues = []
    if not contract:
        return issues
    levels = contract.get('levels') or {}
    if not levels:
        issues.append(Issue('ERROR', 'EXPOSURE_CONTRACT_INVALID', 0,
                            'missing levels map'))
        return issues
    timeline = sorted(shots, key=lambda s: int(s.get('n', s.get('shot_no', 0))))
    counts = collections.Counter()
    direct = DIRECT_EXPOSURE_TAGS | COVERED_STATE_TAGS
    for shot in timeline:
        n = int(shot.get('n', shot.get('shot_no', 0)))
        level = shot.get('exposure_level')
        if level not in EXPOSURE_LEVELS:
            issues.append(Issue('ERROR', 'MISSING_EXPOSURE_LEVEL', n,
                                'exposure_level must be one of L0/L1/L2'))
            continue
        counts[level] += 1
        body = _names(shot, 'body_state') | _names(shot, 'outfit')
        found = {t for t in body if t in EXPOSURE_TAG_LEVEL}
        bad = found & direct
        if level == 'L0' and bad:
            issues.append(Issue('ERROR', 'EXPOSURE_LEVEL_TAG_MISMATCH', n,
                                'L0 shot carries exposure tags: %s' % ', '.join(sorted(bad))))
        if level == 'L1' and bad:
            issues.append(Issue('ERROR', 'EXPOSURE_LEVEL_TAG_MISMATCH', n,
                                'L1 shot carries direct exposure tags: %s' % ', '.join(sorted(bad))))
        if level == 'L1' and not (found & PARTIAL_EXPOSURE_TAGS):
            issues.append(Issue('ERROR', 'EXPOSURE_LEVEL_TAG_MISMATCH', n,
                                'L1 shot needs a partial tag (nipple_slip/sideboob/underboob/pussy_peek)'))
        if level == 'L2' and not (found & DIRECT_EXPOSURE_TAGS):
            issues.append(Issue('ERROR', 'EXPOSURE_LEVEL_TAG_MISMATCH', n,
                                'L2 shot needs exposed_breasts or pussy'))
        if 'pussy' in body and 'pubic_hair' not in body:
            issues.append(Issue('ERROR', 'PUBIC_HAIR_REQUIRED', n,
                                'pussy tag requires pubic_hair'))
    for level in ('L0', 'L1', 'L2'):
        want = int(levels.get(level, 0))
        if counts.get(level, 0) != want:
            issues.append(Issue('ERROR', 'EXPOSURE_RATIO_MISMATCH', 0,
                                '%s declared %d but plan has %d'
                                % (level, want, counts.get(level, 0))))
    windows = contract.get('l0_windows') or []
    for shot in timeline:
        n = int(shot.get('n', shot.get('shot_no', 0)))
        if shot.get('exposure_level') == 'L0' and not any(
                int(a) <= n <= int(b) for a, b in windows):
            issues.append(Issue('ERROR', 'EXPOSURE_L0_OUT_OF_WINDOW', n,
                                'L0 shot outside quiet windows'))
    peak = contract.get('peak')
    if peak and len(peak) >= 2:
        a, b = int(peak[0]), int(peak[1])
        run = best = 0
        for shot in timeline:
            n = int(shot.get('n', shot.get('shot_no', 0)))
            if not a <= n <= b:
                continue
            if shot.get('exposure_level') == 'L2':
                run += 1
                best = max(best, run)
            else:
                run = 0
                issues.append(Issue('ERROR', 'EXPOSURE_PEAK_NOT_L2', n,
                                    'peak window shot is not L2'))
        required = int(contract.get('peak_min_l2', 8))
        if best < required:
            issues.append(Issue('ERROR', 'EXPOSURE_PEAK_RUN', a,
                                'longest L2 run in peak is %d, need %d' % (best, required)))
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
    issues += validate_exposure_contract(shots, (plan.get('act') or {}).get('exposure_contract'))
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
