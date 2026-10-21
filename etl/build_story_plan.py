"""Compile human/LLM-authored BEATS to a plan, without random action/expression mixing.

Input JSON uses regular seed_plan project/characters/act fields plus `beats[]`.
Each beat has {id, purpose, shots:[{action,expression,pose,caption,sequence,...}]}.
The number of shots is DERIVED from narrative needs, not a fixed quota.
Actual tag strings must still exist in SQLite; seed_plan performs resolution.

Interaction roles are never rewritten here: beats' `sequence.actor/target` and
`character_actions`/`character_targets` are copied as authored and then gated by
the shared story_logic interaction validator (INTERACTION_* codes). If the
audit contract says the roles are inverted, fix the beat source - do not swap
roles synthetically.
"""
import argparse
import json
import pathlib
import sys
import story_logic


def build(data):
    if not data.get('beats'):
        raise ValueError('Missing beats[]; cannot synthesize narrative from unrelated tag pools')
    plan = {k: v for k, v in data.items() if k != 'beats'}
    shots = []
    for beat in data['beats']:
        if not beat.get('shots'):
            raise ValueError('Beat %s has no shots: explicitly mark optional or remove it' % beat.get('id'))
        for item in beat['shots']:
            sh = dict(item)
            sh['n'] = len(shots) + 1
            sh.setdefault('beat', beat.get('description', beat.get('id', '')))
            sh.setdefault('phase', beat.get('id', ''))
            seq = dict(sh.get('sequence') or {})
            seq.setdefault('purpose', beat.get('purpose', 'action'))
            seq.setdefault('eventId', '%s:%d' % (beat.get('id', 'beat'), len(shots)+1))
            sh['sequence'] = seq
            shots.append(sh)
    plan['shots'] = shots
    issues = story_logic.validate_plan(plan)
    errors = [x for x in issues if x.level == 'ERROR']
    if errors:
        raise ValueError('\n'.join('%s shot %s: %s' % (x.code, x.shot, x.detail) for x in errors))
    return plan, issues


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--input', required=True)
    ap.add_argument('--output', required=True)
    args = ap.parse_args()
    data = json.loads(pathlib.Path(args.input).read_text(encoding='utf-8-sig'))
    try:
        plan, issues = build(data)
    except (ValueError, KeyError) as exc:
        print('BUILD_STORY_FAILED:', exc, file=sys.stderr)
        return 1
    out = pathlib.Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Wrote %d narrative-derived shots, %d warnings: %s' % (len(plan['shots']), len(issues), out))
    return 0


if __name__ == '__main__':
    sys.exit(main())
