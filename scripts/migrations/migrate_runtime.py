"""Apply the idempotent QA/continuity migration to an EXISTING catalog DB.
Creates a SQLite backup by default, never rebuilds or deletes tables.
"""
import argparse
import pathlib
import sqlite3
import sys
from datetime import datetime


def main():
    root = pathlib.Path(__file__).resolve().parents[2]
    ap = argparse.ArgumentParser()
    ap.add_argument('--db', default=str(root / 'db/novel_anima.db'))
    ap.add_argument('--skip-backup', action='store_true')
    args = ap.parse_args()
    path = pathlib.Path(args.db)
    if not path.is_file():
        ap.error('database missing: ' + str(path))
    sql = (root / 'sql/migrations/002_shot_state.sql').read_text(encoding='utf-8')
    with sqlite3.connect(str(path)) as con:
        con.execute('PRAGMA foreign_keys=ON')
        if not args.skip_backup:
            backup = path.with_name(path.name + '.before_story_upgrade_' + datetime.now().strftime('%Y%m%d_%H%M%S') + '.sqlite')
            with sqlite3.connect(str(backup)) as dest:
                con.backup(dest)
            print('Backup:', backup)
        con.executescript(sql)
        con.commit()
        tables = {x[0] for x in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        missing = {'shot_state','act_continuity'} - tables
        if missing:
            raise RuntimeError('migration incomplete: ' + repr(missing))
        errors = con.execute('PRAGMA foreign_key_check').fetchall()
        if errors:
            raise RuntimeError('foreign keys invalid: %r' % errors[:8])
    print('PASS: runtime QA schema applied, FK valid')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, sqlite3.Error, RuntimeError) as exc:
        print('MIGRATION_FAILED:', exc, file=sys.stderr)
        sys.exit(1)
