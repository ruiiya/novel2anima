"""Read-only story continuity gate; works with plan JSON or runtime DB.

Usage: python etl/check_story.py --plan data/plans/a.json
       python etl/check_story.py --db db/novel_anima.db --act 1 --project 'My Project' --revision 1
"""
import argparse
import json
import pathlib
import sqlite3
import sys
import story_logic
import story_db


def main(argv=None):
    ap = argparse.ArgumentParser()
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument('--plan')
    src.add_argument('--act', type=int)
    ap.add_argument('--db', default='db/novel_anima.db')
    ap.add_argument('--project')
    ap.add_argument('--revision', type=int)
    ap.add_argument('--strict-warnings', action='store_true')
    ap.add_argument('--json-out')
    ap.add_argument('--plan-dir', default='data/plans')
    args = ap.parse_args(argv)
    try:
        if args.plan:
            plan = json.loads(pathlib.Path(args.plan).read_text(encoding='utf-8-sig'))
            issues = story_logic.validate_plan(plan)
        else:
            con = sqlite3.connect(args.db)
            try:
                aid = story_db.resolve_act(con, args.act, args.project, args.revision)
                specs = [(n, json.loads(s)) for n, s in con.execute(
                    'SELECT shot_no, shot_spec_json FROM shot WHERE act_id=? ORDER BY shot_no', (aid,))]
                meta = con.execute('SELECT p.title, a.act_no, a.revision FROM act a'
                                   ' JOIN project p ON p.id=a.project_id WHERE a.id=?', (aid,)).fetchone()
                contract = None
                for path in pathlib.Path(args.plan_dir).glob('*.json'):
                    try:
                        d = json.loads(path.read_text(encoding='utf-8-sig'))
                    except (OSError, ValueError):
                        continue
                    ac = d.get('act') or {}
                    if (d.get('shots') and (d.get('project') or {}).get('title') == meta[0]
                            and ac.get('act_no') == meta[1] and ac.get('revision', 1) == meta[2]):
                        contract = ac.get('phase_contract')
                        break
                issues = story_logic.validate_specs(specs, phase_contract=contract)
            finally:
                con.close()
    except (ValueError, OSError, sqlite3.Error, KeyError) as exc:
        print('STORY_CHECK_FAILED: %s' % exc, file=sys.stderr)
        return 2
    d = story_logic.report(issues)
    if args.json_out:
        pathlib.Path(args.json_out).write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding='utf-8')
    for x in issues:
        print('%-5s shot %-4d %-30s %s%s' % (x.level, x.shot, x.code, x.detail,
                                              (' | ' + x.suggestion) if x.suggestion else ''))
    print('story QA: %d errors, %d warnings' % (d['errors'], d['warnings']))
    return int(bool(d['errors'] or (args.strict_warnings and d['warnings'])))


if __name__ == '__main__':
    sys.exit(main())
