# novel2anima P0P1 upgrade
# -*- coding: utf-8 -*-
"""Read-only reseed audit against a private SQLite clone and temporary prompt files.

Previous implementation reseeded the live DB and ignored QA exit codes.
This implementation never touches live DB, plan JSONs or prompt files.
"""
import argparse
import contextlib
import glob
import hashlib
import json
import os
import pathlib
import sqlite3
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
ETL = ROOT / 'etl'
DEFAULT_DB = ROOT / 'db/novel_anima.db'


def checksum(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def call(args):
    p = subprocess.run([sys.executable, str(ETL / args[0])] + [str(x) for x in args[1:]],
                       cwd=str(ROOT), capture_output=True, text=True, encoding='utf-8', errors='replace')
    if p.returncode:
        raise RuntimeError('%s exited %s: %s' % (args[0], p.returncode,
                            (p.stdout + '\n' + p.stderr)[-1000:]))
    return p


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--db', default=str(DEFAULT_DB))
    ap.add_argument('--plan-dir', default=str(ROOT / 'data/plans'))
    ap.add_argument('--no-llm-replay', action='store_true')
    args = ap.parse_args(argv)
    source_db = pathlib.Path(args.db).resolve()
    if not source_db.is_file():
        ap.error('database does not exist: %s' % source_db)
    plans = sorted(pathlib.Path(args.plan_dir).glob('*.json'))
    if not plans:
        print('no plan files found', file=sys.stderr)
        return 2
    originals = {}
    for src in plans:
        d = json.loads(src.read_text(encoding='utf-8-sig'))
        if d.get('shots') and d.get('prompt_file'):
            pf = pathlib.Path(d['prompt_file'])
            if not pf.is_absolute():
                pf = ROOT / pf
            if pf.exists():
                originals[str(pf)] = checksum(pf)
    with tempfile.TemporaryDirectory(prefix='novel2anima_reseed_') as td:
        tmp = pathlib.Path(td)
        cloned = tmp / 'audit.db'
        with contextlib.closing(sqlite3.connect(str(source_db))) as db_from, \
             contextlib.closing(sqlite3.connect(str(cloned))) as db_to:
            db_from.backup(db_to)
        with contextlib.closing(sqlite3.connect(str(cloned))) as con:
            migration = ROOT / 'sql/migrations/002_shot_state.sql'
            con.executescript(migration.read_text(encoding='utf-8'))
            con.commit()
        plan_dir = tmp / 'plans'
        plan_dir.mkdir()
        expected_prompts = {}
        skipped = []
        with contextlib.closing(sqlite3.connect(str(cloned))) as con:
            for src in plans:
                d = json.loads(src.read_text(encoding='utf-8-sig'))
                ac = d.get('act') or {}
                pj = d.get('project') or {}
                if not d.get('shots') or not ac.get('act_no') or not pj.get('title'):
                    continue
                seeded = con.execute('SELECT 1 FROM act a JOIN project p ON p.id=a.project_id '
                                     'WHERE p.title=? AND a.act_no=? AND a.revision=?',
                                     (pj['title'], ac['act_no'], ac.get('revision', 1))).fetchone()
                if not seeded:
                    skipped.append(src.name)
                    continue
                out = tmp / 'prompts' / (src.stem + '.txt')
                out.parent.mkdir(exist_ok=True)
                d['prompt_file'] = str(out)
                new_plan = plan_dir / src.name
                new_plan.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding='utf-8')
                current_pf = pathlib.Path(json.loads(src.read_text(encoding='utf-8-sig'))['prompt_file'])
                if not current_pf.is_absolute():
                    current_pf = ROOT / current_pf
                if current_pf.is_file():
                    expected_prompts[str(out)] = checksum(current_pf)
        if not list(plan_dir.glob('*.json')):
            print('nothing seeded to verify; pending: %s' % skipped)
            return 0
        for plan in sorted(plan_dir.glob('*.json')):
            call(['seed_plan.py', plan, '--db', cloned])
            call(['check_story.py', '--plan', plan])
        call(['qa_shots.py', '--apply', '--db', cloned])
        if not args.no_llm_replay and list((ROOT / 'data/reviews').glob('act*_llm.json')):
            call(['llm_review.py', '--replay', '--db', cloned])
        call(['check_prompts.py', '--db', cloned, '--plan-dir', plan_dir, '--examples', 3])
        with contextlib.closing(sqlite3.connect(str(cloned))) as con:
            fk = con.execute('PRAGMA foreign_key_check').fetchall()
        if fk:
            raise RuntimeError('FK violations in clone: %s' % fk[:5])
        drift = [k for k, digest in expected_prompts.items()
                 if not pathlib.Path(k).exists() or checksum(pathlib.Path(k)) != digest]
        if drift:
            raise RuntimeError('Prompt byte drift: %s' % drift[:10])
    changed = [p for p, digest in originals.items() if checksum(pathlib.Path(p)) != digest]
    if changed:
        raise RuntimeError('Original prompt files unexpectedly changed: %s' % changed)
    print('PASS: reseed idempotent, QA passes, FK clean, original files untouched; skipped %d' % len(skipped))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (RuntimeError, OSError, sqlite3.Error, ValueError) as exc:
        print('FAIL:', exc, file=sys.stderr)
        raise SystemExit(1)
