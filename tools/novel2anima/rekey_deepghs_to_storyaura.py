#!/usr/bin/env python3
"""Re-key DeepGHS characters to StoryAura character IDs.

DeepGHS rows already carry the StoryAura appearance/outfit tags, but they keep
the `character:deepghs:` id. The StoryAura CSV roster has no duplicate row for
those tags, so this migration renames the existing rows to the id the StoryAura
importer uses: `character:storyaura_danbooru_csv:<sha256(tag)[:18]>`.

All live foreign keys are moved in one deferred transaction:
character_aliases, character_traits, character_tags, outfits, story_castings,
catalog_entity_links, then characters.id. Immutable history (shots,
story_revisions, storyboards, story_sources) is intentionally not rewritten:
those tables are append-only/sealed and keep the old id as historical text.

Dry-run by default. `--apply` backs up the DB first.

Examples:
  python tools/novel2anima/rekey_deepghs_to_storyaura.py
  python tools/novel2anima/rekey_deepghs_to_storyaura.py --apply
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = ROOT / 'database' / 'data' / 'novel2anima.db'
BACKUP_DIR = ROOT / 'database' / 'data' / 'backups'
OLD_PREFIX = 'character:deepghs:'
NEW_PREFIX = 'character:storyaura_danbooru_csv:'
CHILD_TABLES = (
    ('character_aliases', 'character_id'),
    ('character_traits', 'character_id'),
    ('character_tags', 'character_id'),
    ('outfits', 'character_id'),
    ('story_castings', 'character_id'),
)
IMMUTABLE_TEXT = (
    ('shots', 'shot_spec_json'),
    ('story_revisions', 'plan_json'),
    ('storyboards', 'plan_json'),
    ('story_sources', 'raw_text'),
)


def digest(value: str) -> str:
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


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


def count(con, sql, params=()):
    return con.execute(sql, params).fetchone()[0]


def load_mapping(con):
    mapping = []
    for row in con.execute(
            '''SELECT id, slug, display_name, universe_id, identity_json FROM characters
               WHERE id LIKE ? ORDER BY id''', (OLD_PREFIX + '%',)):
        identity = json.loads(row['identity_json'] or '{}')
        tag = identity.get('danbooru_tag')
        if tag:
            key = tag
            key_source = 'danbooru_tag'
        else:
            # No Danbooru tag: hash the old id so a same-slug character in
            # another universe (e.g. grayfia_lucifuge under touhou) cannot
            # collide with this row.
            key = f'fallback|{row["universe_id"]}|{row["slug"]}|{row["id"]}'
            key_source = 'fallback'
        mapping.append({
            'old_id': row['id'],
            'new_id': NEW_PREFIX + digest(key)[:18],
            'slug': row['slug'],
            'display_name': row['display_name'],
            'universe_id': row['universe_id'],
            'tag': tag,
            'key': key,
            'key_source': key_source,
        })
    return mapping


def collision_check(con, mapping):
    seen = {}
    for item in mapping:
        new_id = item['new_id']
        if new_id in seen:
            raise SystemExit(f'new id collision inside mapping: {new_id} '
                             f'({seen[new_id]} / {item["old_id"]})')
        seen[new_id] = item['old_id']
        exists = con.execute('SELECT 1 FROM characters WHERE id=?', (new_id,)).fetchone()
        if exists:
            raise SystemExit(f'new id already exists: {new_id} (from {item["old_id"]})')


def dependent_counts(con):
    counts = {}
    for table, column in CHILD_TABLES:
        counts[table] = count(
            con, f'SELECT count(*) FROM {table} WHERE {column} LIKE ?', (OLD_PREFIX + '%',))
    counts['catalog_entity_links'] = count(
        con, "SELECT count(*) FROM catalog_entity_links "
             "WHERE left_entity_kind='character' AND left_entity_id LIKE ?",
        (OLD_PREFIX + '%',))
    counts['characters'] = count(
        con, 'SELECT count(*) FROM characters WHERE id LIKE ?', (OLD_PREFIX + '%',))
    return counts


def immutable_refs(con):
    refs = {}
    for table, column in IMMUTABLE_TEXT:
        refs[f'{table}.{column}'] = count(
            con, f"SELECT count(*) FROM {table} WHERE instr({column}, ?)>0", (OLD_PREFIX,))
    return refs


def apply_mapping(con, mapping):
    con.execute('DROP TABLE IF EXISTS temp.rekey')
    con.execute('CREATE TEMP TABLE rekey(old_id TEXT PRIMARY KEY, new_id TEXT UNIQUE)')
    con.executemany('INSERT INTO rekey(old_id, new_id) VALUES(?,?)',
                    [(m['old_id'], m['new_id']) for m in mapping])
    updated = {}
    for table, column in CHILD_TABLES:
        updated[table] = con.execute(
            f'''UPDATE {table} SET {column} = (SELECT new_id FROM rekey WHERE old_id = {column})
                WHERE {column} IN (SELECT old_id FROM rekey)''').rowcount
    updated['catalog_entity_links'] = con.execute(
        '''UPDATE catalog_entity_links
           SET left_entity_id = (SELECT new_id FROM rekey WHERE old_id = left_entity_id)
           WHERE left_entity_kind='character' AND left_entity_id IN (SELECT old_id FROM rekey)'''
    ).rowcount
    updated['characters'] = con.execute(
        '''UPDATE characters SET id = (SELECT new_id FROM rekey WHERE old_id = id)
           WHERE id IN (SELECT old_id FROM rekey)''').rowcount
    return updated


def fk_table_counts(con):
    counts = {}
    for row in con.execute('PRAGMA foreign_key_check'):
        counts[row[0]] = counts.get(row[0], 0) + 1
    return counts


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--db', type=Path, default=DEFAULT_DB,
                        help=f'SQLite database (default: {DEFAULT_DB})')
    parser.add_argument('--apply', action='store_true',
                        help='actually rewrite ids; without it the script only reports')
    parser.add_argument('--backup', type=Path,
                        help='backup path (default: database/data/backups/novel2anima.pre-rekey-<UTC>.db)')
    parser.add_argument('--no-backup', action='store_true',
                        help='skip the backup; only use on a disposable copy')
    parser.add_argument('--sample', type=int, default=10,
                        help='how many mappings to print (default: 10)')
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

    mapping = load_mapping(con)
    collision_check(con, mapping)
    summary = {
        'status': 'DRY_RUN',
        'db': str(args.db),
        'characters': len(mapping),
        'missing_danbooru_tag': sum(1 for m in mapping if not m['tag']),
        'dependents': dependent_counts(con),
        'immutable_refs_kept': immutable_refs(con),
        'sample': mapping[:int(args.sample)],
    }
    if not args.apply:
        summary['elapsed_seconds'] = round(time.perf_counter() - started, 2)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        con.close()
        return 0

    if not args.no_backup:
        backup_path = args.backup or (BACKUP_DIR / (
            'novel2anima.pre-rekey-' +
            datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '.db'))
        summary['backup'] = str(make_backup(con, backup_path))

    fk_before = fk_table_counts(con)
    try:
        con.execute('BEGIN IMMEDIATE')
        con.execute('PRAGMA defer_foreign_keys = ON')
        updated = apply_mapping(con, mapping)
        fk_after = fk_table_counts(con)
        new_violations = {table: n for table, n in fk_after.items()
                          if n > fk_before.get(table, 0)}
        if new_violations:
            raise RuntimeError(f'new foreign key violations: {new_violations}')
        con.execute('COMMIT')
    except Exception:
        con.execute('ROLLBACK')
        con.close()
        raise

    summary.update({
        'status': 'OK',
        'updated_rows': updated,
        'after': {
            'deepghs': count(con, 'SELECT count(*) FROM characters WHERE id LIKE ?',
                             (OLD_PREFIX + '%',)),
            'storyaura': count(con, 'SELECT count(*) FROM characters WHERE id LIKE ?',
                               (NEW_PREFIX + '%',)),
            'characters_total': count(con, 'SELECT count(*) FROM characters'),
        },
        'foreign_key_violations_before': fk_before,
        'foreign_key_violations_after': fk_after,
    })
    summary['elapsed_seconds'] = round(time.perf_counter() - started, 2)
    con.close()
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (sqlite3.Error, OSError, json.JSONDecodeError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        sys.exit(2)
