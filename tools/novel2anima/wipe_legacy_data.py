#!/usr/bin/env python3
"""Drop all legacy story/layout data and keep a clean StoryAura catalog.

Keeps: characters with id `character:storyaura_danbooru_csv:*`, their tags,
aliases, traits, outfits, catalog links, universes, catalog tags and generic
catalog metadata.

Drops: every story, story revision, role/casting, act/beat/event, shot,
participant/interaction, prompt, continuity snapshot, QA report, storyboard,
seal, story source, legacy V2 layout/export row, and every character that is
not StoryAura (`character:curated:*`, `character:original:*`).

Immutable tables block DELETE with triggers, so this script saves those
triggers, drops them for the wipe, then recreates them unchanged. Schema and
future guards stay in place.

Dry-run by default. `--apply` backs up the DB first.

Examples:
  python tools/novel2anima/wipe_legacy_data.py
  python tools/novel2anima/wipe_legacy_data.py --apply --vacuum
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
DEFAULT_DB = ROOT / 'database' / 'data' / 'novel2anima.db'
BACKUP_DIR = ROOT / 'database' / 'data' / 'backups'
KEEP_PREFIX = 'character:storyaura_danbooru_csv:'

# Children before parents; every table below is story/layout scoped.
WIPE_ORDER = (
    'shot_layout_items',
    'layout_exports',
    'shot_layouts',
    'storyboard_seals',
    'shot_dependencies',
    'event_shot_mappings',
    'storyboard_shots',
    'story_locations',
    'story_props',
    'visual_style_profiles',
    'storyboards',
    'qa_reports',
    'shot_prompts',
    'continuity_snapshots',
    'shot_interactions',
    'shot_participants',
    'shots',
    'story_events',
    'beats',
    'acts',
    'story_castings',
    'story_roles',
    'story_sources',
    'story_revisions',
    'stories',
)
COUNT_TABLE = ('characters', 'stories', 'story_revisions', 'storyboards', 'shots',
               'shot_prompts', 'qa_reports', 'continuity_snapshots', 'shot_layouts')


def sql_literal(value: str) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def count(con, sql, params=()):
    return con.execute(sql, params).fetchone()[0]


def table_counts(con):
    out = {}
    for table in COUNT_TABLE:
        out[table] = count(con, f'SELECT count(*) FROM {table}')
    out['non_storyaura_characters'] = count(
        con, 'SELECT count(*) FROM characters WHERE id NOT LIKE ?', (KEEP_PREFIX + '%',))
    return out


def fk_table_counts(con):
    out = {}
    for row in con.execute('PRAGMA foreign_key_check'):
        out[row[0]] = out.get(row[0], 0) + 1
    return out


def make_backup(con, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    target = path
    suffix = 1
    while target.exists():
        target = path.with_name(f'{path.stem}-{suffix}{path.suffix}')
        suffix += 1
    dst = sqlite3.connect(target)
    try:
        con.backup(dst)
    finally:
        dst.close()
    return target


def save_triggers(con):
    marks = ','.join(sql_literal(t) for t in WIPE_ORDER)
    return [(row['name'], row['sql']) for row in con.execute(
        f"SELECT name, sql FROM sqlite_master WHERE type='trigger' "
        f"AND tbl_name IN ({marks}) ORDER BY name")]


def wipe(con, triggers, all_characters=False):
    deleted = {}
    for name, _ in triggers:
        con.execute(f'DROP TRIGGER IF EXISTS "{name}"')
    for table in WIPE_ORDER:
        deleted[table] = con.execute(f'DELETE FROM {table}').rowcount
    if all_characters:
        deleted['catalog_captions'] = con.execute(
            '''DELETE FROM catalog_captions
               WHERE entity_kind='outfit' AND entity_id IN
                 (SELECT id FROM outfits WHERE character_id IS NOT NULL)''').rowcount
        deleted['outfits'] = con.execute(
            'DELETE FROM outfits WHERE character_id IS NOT NULL').rowcount
        deleted['catalog_entity_links'] = con.execute(
            "DELETE FROM catalog_entity_links WHERE left_entity_kind='character'").rowcount
        deleted['characters'] = con.execute('DELETE FROM characters').rowcount
        deleted['universes'] = con.execute('DELETE FROM universes').rowcount
    else:
        deleted['catalog_captions'] = con.execute(
            '''DELETE FROM catalog_captions
               WHERE entity_kind='outfit' AND entity_id IN
                 (SELECT id FROM outfits WHERE character_id IS NOT NULL
                  AND character_id NOT LIKE ?)''', (KEEP_PREFIX + '%',)).rowcount
        deleted['outfits'] = con.execute(
            '''DELETE FROM outfits WHERE character_id IS NOT NULL
               AND character_id NOT LIKE ?''', (KEEP_PREFIX + '%',)).rowcount
        deleted['catalog_entity_links'] = con.execute(
            '''DELETE FROM catalog_entity_links WHERE left_entity_kind='character'
               AND left_entity_id NOT LIKE ?''', (KEEP_PREFIX + '%',)).rowcount
        deleted['characters'] = con.execute(
            'DELETE FROM characters WHERE id NOT LIKE ?', (KEEP_PREFIX + '%',)).rowcount
        deleted['universes'] = con.execute(
            '''DELETE FROM universes WHERE id NOT IN
               (SELECT DISTINCT universe_id FROM characters WHERE universe_id IS NOT NULL)'''
        ).rowcount
    for name, sql in triggers:
        con.execute(sql)
    return deleted


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--db', type=Path, default=DEFAULT_DB,
                        help=f'SQLite database (default: {DEFAULT_DB})')
    parser.add_argument('--apply', action='store_true',
                        help='actually wipe; without it the script only reports')
    parser.add_argument('--all-characters', action='store_true',
                        help='drop every character, outfit and universe (StoryAura reset)')
    parser.add_argument('--backup', type=Path,
                        help='backup path (default: database/data/backups/novel2anima.pre-wipe-<UTC>.db)')
    parser.add_argument('--no-backup', action='store_true',
                        help='skip the backup; only use on a disposable copy')
    parser.add_argument('--vacuum', action='store_true',
                        help='VACUUM after commit to reclaim file space')
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    if not args.db.exists():
        raise SystemExit(f'DB not found: {args.db}')
    started = time.perf_counter()
    con = sqlite3.connect(args.db)
    con.row_factory = sqlite3.Row
    con.isolation_level = None
    con.execute('PRAGMA foreign_keys = ON')
    con.execute('PRAGMA busy_timeout = 5000')
    con.execute('PRAGMA wal_checkpoint(PASSIVE)')

    triggers = save_triggers(con)
    summary = {
        'status': 'DRY_RUN',
        'db': str(args.db),
        'all_characters': args.all_characters,
        'before': table_counts(con),
        'guarded_triggers': [name for name, _ in triggers],
        'fk_before': fk_table_counts(con),
    }
    if not args.apply:
        summary['elapsed_seconds'] = round(time.perf_counter() - started, 2)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        con.close()
        return 0

    if not args.no_backup:
        backup_path = args.backup or (BACKUP_DIR / (
            'novel2anima.pre-wipe-' +
            datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '.db'))
        summary['backup'] = str(make_backup(con, backup_path))

    try:
        con.execute('BEGIN IMMEDIATE')
        deleted = wipe(con, triggers, all_characters=args.all_characters)
        fk_after = fk_table_counts(con)
        if fk_after:
            raise RuntimeError(f'foreign key violations after wipe: {fk_after}')
        con.execute('COMMIT')
    except Exception:
        con.execute('ROLLBACK')
        con.close()
        raise

    summary.update({
        'status': 'OK',
        'deleted': deleted,
        'after': table_counts(con),
        'fk_after': fk_after,
    })
    if args.vacuum:
        con.execute('VACUUM')
        con.execute('PRAGMA wal_checkpoint(TRUNCATE)')
        summary['vacuumed'] = True
    summary['elapsed_seconds'] = round(time.perf_counter() - started, 2)
    con.close()
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (sqlite3.Error, OSError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        sys.exit(2)
