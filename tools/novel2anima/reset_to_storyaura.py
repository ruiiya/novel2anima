#!/usr/bin/env python3
"""Reset the catalog to StoryAura CSV only.

Wipe: every character, character outfit, universe, story/board/shot/prompt/QA/
continuity/layout row. Keep: schema, triggers, catalog tags/relations,
generic outfits, poses, vocabulary, provenance/import history.

Then import, in order:
  1. danbooru_character_tags_corrected.csv  (character rows + aliases + links)
  2. danbooru_character_appearance_corrected.csv  (appearance + outfit tags)

Dry-run by default. `--apply` backs up the DB, wipes, imports and verifies.

Examples:
  python tools/novel2anima/reset_to_storyaura.py
  python tools/novel2anima/reset_to_storyaura.py --apply --vacuum
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'database' / 'src'))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from n2m_db import apply_migrations, connect  # noqa: E402
from catalog_imports import (  # noqa: E402
    import_storyaura_appearance, import_storyaura_characters)
from wipe_legacy_data import (  # noqa: E402
    make_backup, save_triggers, table_counts, fk_table_counts, wipe)

DEFAULT_DB = ROOT / 'database' / 'data' / 'novel2anima.db'
BACKUP_DIR = ROOT / 'database' / 'data' / 'backups'
IMPORT_DIR = ROOT / 'database' / 'imports' / 'storyaura-danbooru-csv'
TAGS_CSV = IMPORT_DIR / 'danbooru_character_tags_corrected.csv'
APPEARANCE_CSV = IMPORT_DIR / 'danbooru_character_appearance_corrected.csv'
SOURCE_REVISION = '2026-10-29-corrected'


def count(con, sql, params=()):
    return con.execute(sql, params).fetchone()[0]


def role_counts(con):
    return {row['tag_role']: row['n'] for row in con.execute(
        'SELECT tag_role, count(*) AS n FROM character_tags GROUP BY tag_role')}


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--db', type=Path, default=DEFAULT_DB,
                        help=f'SQLite database (default: {DEFAULT_DB})')
    parser.add_argument('--apply', action='store_true',
                        help='actually reset; without it the script only reports')
    parser.add_argument('--backup', type=Path,
                        help='backup path (default: database/data/backups/novel2anima.pre-reset-<UTC>.db)')
    parser.add_argument('--no-backup', action='store_true',
                        help='skip the backup; only use on a disposable copy')
    parser.add_argument('--vacuum', action='store_true',
                        help='VACUUM after the imports')
    parser.add_argument('--source-revision', default=SOURCE_REVISION,
                        help=f'provenance revision (default: {SOURCE_REVISION})')
    parser.add_argument('--tags-csv', type=Path, default=TAGS_CSV)
    parser.add_argument('--appearance-csv', type=Path, default=APPEARANCE_CSV)
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    if not args.db.exists():
        raise SystemExit(f'DB not found: {args.db}')
    for path in (args.tags_csv, args.appearance_csv):
        if not path.exists():
            raise SystemExit(f'CSV not found: {path}')

    started = time.perf_counter()
    con = connect(args.db)
    apply_migrations(con)
    triggers = save_triggers(con)
    summary = {
        'status': 'DRY_RUN',
        'db': str(args.db),
        'before': table_counts(con),
        'fk_before': fk_table_counts(con),
        'expected': {
            'characters': import_storyaura_characters(
                con, args.tags_csv, source_revision=args.source_revision, dry_run=True),
            'appearance': import_storyaura_appearance(
                con, args.appearance_csv, source_revision=args.source_revision, dry_run=True),
        },
    }
    if not args.apply:
        summary['elapsed_seconds'] = round(time.perf_counter() - started, 2)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        con.close()
        return 0

    if not args.no_backup:
        backup_path = args.backup or (BACKUP_DIR / (
            'novel2anima.pre-reset-' +
            datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '.db'))
        summary['backup'] = str(make_backup(con, backup_path))

    con.isolation_level = None
    try:
        con.execute('BEGIN IMMEDIATE')
        deleted = wipe(con, triggers, all_characters=True)
        con.execute('COMMIT')
    except Exception:
        con.execute('ROLLBACK')
        con.close()
        raise
    finally:
        con.close()

    con = connect(args.db)
    try:
        summary['import_characters'] = import_storyaura_characters(
            con, args.tags_csv, source_revision=args.source_revision)
        summary['import_appearance'] = import_storyaura_appearance(
            con, args.appearance_csv, source_revision=args.source_revision)
        con.execute('''DELETE FROM universes WHERE id NOT IN
            (SELECT DISTINCT universe_id FROM characters WHERE universe_id IS NOT NULL)''')
        con.commit()
        summary['deleted'] = deleted
        summary['after'] = table_counts(con)
        summary['after']['universes'] = count(con, 'SELECT count(*) FROM universes')
        summary['after']['character_roles'] = role_counts(con)
        summary['after']['characters_by_prefix'] = {
            row['prefix']: row['n'] for row in con.execute(
                '''SELECT CASE WHEN id LIKE 'character:storyaura_danbooru_csv:%'
                           THEN 'storyaura_danbooru_csv' ELSE 'other' END prefix,
                          count(*) n FROM characters GROUP BY prefix''')}
        summary['fk_after'] = fk_table_counts(con)
        summary['status'] = 'OK'
        if args.vacuum:
            con.execute('VACUUM')
            con.execute('PRAGMA wal_checkpoint(TRUNCATE)')
            summary['vacuumed'] = True
    finally:
        con.close()
    summary['elapsed_seconds'] = round(time.perf_counter() - started, 2)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (sqlite3.Error, OSError, ValueError, FileNotFoundError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        sys.exit(2)
