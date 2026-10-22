"""Identify missing bridge actions without hallucinating catalog tag IDs or adding arbitrary shots.

Usage: python -m novel2anima.story.action_planner --plan data/plans/example.json [--json-out review.json]
"""
import argparse
import json
import pathlib
from novel2anima.story import logic as story_logic


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--plan', required=True)
    p.add_argument('--json-out')
    args = p.parse_args()
    plan = json.loads(pathlib.Path(args.plan).read_text(encoding='utf-8-sig'))
    issues = story_logic.validate_plan(plan)
    actionable = [i.to_dict() for i in issues if i.code in (
        'POSE_BRIDGE_MISSING', 'PRECONDITION_POSE', 'MISSING_REQUIRED_REACTION',
        'PROP_TRANSFER_WITHOUT_ACTION', 'PROP_OWNERSHIP_JUMP', 'ACTION_REQUIRED',
        'NO_STORY_PROGRESS', 'MISSING_SHOT_PURPOSE',
        'INTERACTION_ROLE_MISMATCH', 'INTERACTION_ACTOR_ACTION_MISSING',
        'INTERACTION_TARGET_REQUIRED', 'INTERACTION_TARGET_NOT_IN_SHOT',
        'INTERACTION_TARGET_MISMATCH', 'INTERACTION_PRIMARY_ACTION_MISMATCH',
        'INTERACTION_PROMPT_DIRECTION_MISMATCH')]
    for i in actionable:
        print('shot %s: %s: %s' % (i['shot'], i['code'], i['suggestion'] or i['detail']))
    if args.json_out:
        pathlib.Path(args.json_out).write_text(json.dumps(actionable, indent=2, ensure_ascii=False), encoding='utf-8')
    return int(any(x['level'] == 'ERROR' for x in actionable))

if __name__ == '__main__':
    raise SystemExit(main())
