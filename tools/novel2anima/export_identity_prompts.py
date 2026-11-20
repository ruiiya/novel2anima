#!/usr/bin/env python3
"""Export identity + outfit prompts per catalog character (read-only SQLite).

Two tag groups only:
  APPEARANCE_CANDIDATE  identity anchors
  OUTFIT_CANDIDATE      outfit tags

The prompt is the identity packet (character, series, identity anchors) plus
outfit tags, following docs/novel2anima/ANIMA_TAG_PROMPT.md. Outfit tags are
CANDIDATE (statistical), never canon; keep that in mind when rendering.
By default only characters with at least one identity anchor or outfit tag are
exported; `--include-empty` keeps characters with neither.

Examples (run from the project root):
  python tools/novel2anima/export_identity_prompts.py
  python tools/novel2anima/export_identity_prompts.py --format txt
  python tools/novel2anima/export_identity_prompts.py --universe "blue archive"
  python tools/novel2anima/export_identity_prompts.py --character asuna_blue_archive
  python tools/novel2anima/export_identity_prompts.py --out - --limit 5
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
import time
from itertools import groupby
from operator import itemgetter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = ROOT / 'database' / 'data' / 'novel2anima.db'
DEFAULT_OUT = ROOT / 'exports' / 'identity_prompts.jsonl'

IDENTITY_ROLE = 'APPEARANCE_CANDIDATE'
OUTFIT_ROLE = 'OUTFIT_CANDIDATE'
ROLES = (IDENTITY_ROLE, OUTFIT_ROLE)
DEFAULT_QUALITY = 'masterpiece, best quality, score_7'

# Tags that describe framing/focus rather than the character's visual identity.
COMPOSITION_TAGS = {
    'solo', 'solo focus', '1girl', '1boy', '1other',
    'male focus', 'female focus', 'multiple girls', 'multiple boys',
    'male', 'female',
}
SUBJECT_BY_TAG = (
    ('1girl', '1girl'),
    ('1boy', '1boy'),
    ('1other', '1other'),
)
SUBJECT_BY_GENDER_TAG = (
    ('male focus', '1boy'),
    ('male', '1boy'),
    ('mature male', '1boy'),
    ('female focus', '1girl'),
    ('female', '1girl'),
)
FEMALE_CODED_TAGS = {
    'breasts', 'large breasts', 'medium breasts', 'small breasts', 'flat chest',
}

# Conservative auto-safety: only clear nudity/intimacy tags move the label.
EXPLICIT_TAGS = {
    'sex', 'anal', 'oral', 'fellatio', 'paizuri', 'creampie', 'orgasm',
    'penis', 'huge penis', 'erection', 'pussy', 'spread pussy', 'vagina', 'anus',
    'cum', 'cum in pussy', 'cum on body', 'ahegao', 'fingering', 'masturbation',
    'penetration', 'cunnilingus', 'handjob', 'deepthroat', 'girl on top',
}
NSFW_TAGS = {
    'nude', 'naked', 'completely nude', 'topless', 'bottomless',
    'nipples', 'puffy nipples', 'pubic hair', 'underboob',
    'bikini top lift', 'bikini bottom pull', 'spread legs',
}

SHORT_HAIR = {'short hair', 'bob cut'}
LONG_HAIR = {'long hair', 'very long hair', 'absurdly long hair'}
SMALL_BUST = {'flat chest', 'small breasts'}
LARGE_BUST = {'large breasts', 'huge breasts', 'gigantic breasts'}
MEDIUM_BUST = {'medium breasts'}
EYE_COLOR_TAGS = {
    'aqua eyes', 'black eyes', 'blue eyes', 'brown eyes', 'green eyes', 'grey eyes',
    'orange eyes', 'pink eyes', 'purple eyes', 'red eyes', 'yellow eyes', 'white eyes',
    'multicolored eyes',
}
HETEROCHROMIA_TAGS = {'heterochromia', 'mismatched pupils', 'multicolored eyes'}

SCORE_RE = re.compile(r'^score_[0-9]+$')
# Underscore is a word separator everywhere except genuine emoticons such as
# `>_<` or `^_^`. Parentheses are word separators too, so the `_(` between a
# `)` and a `(` in a variant character tag must become a space.
EMOTICON_UNDERSCORE_RE = re.compile(
    r'(?<=[^0-9a-z()\[\]{}])_(?=[^0-9a-z()\[\]{}])')


def normalize_tag(value: str) -> str:
    """Turn a Danbooru tag into an Anima tag: lowercase, spaces, no stray commas.

    `score_7` is the one tag that keeps its underscore; emoticon tags such as
    `>_<` keep theirs because the underscore is not a word separator there.
    """
    text = str(value or '').strip().lower()
    if SCORE_RE.fullmatch(text):
        return text
    text = EMOTICON_UNDERSCORE_RE.sub('\x00', text)
    text = text.replace('_', ' ')
    text = text.replace('\x00', '_')
    text = re.sub(r'\s+', ' ', text)
    return text.strip(' ,')


def parse_tags(value: str):
    return [normalize_tag(tag) for tag in value.split(',') if tag.strip()]


def resolve_character_tag(identity, display_name):
    raw = identity.get('danbooru_tag') or display_name
    return normalize_tag(raw), ('danbooru_tag' if identity.get('danbooru_tag') else 'display_name')


def resolve_series_tag(identity, universe_slug, universe_name):
    raw = identity.get('danbooru_copyright')
    series = normalize_tag(raw) if raw else normalize_tag(universe_name or '')
    if not series:
        return None
    # Danbooru "original (...)" copyrights are not a franchise tag and add nothing
    # to identity; the character tag already carries the artist qualifier.
    if re.match(r'^original(?:\b|\s|\()', series):
        return None
    if not raw and universe_slug and universe_slug.lower().startswith('original'):
        return None
    return series


def infer_subject(tags):
    tag_set = set(tags)
    for tag, subject in SUBJECT_BY_TAG:
        if tag in tag_set:
            return subject, f'tag:{tag}'
    for tag, subject in SUBJECT_BY_GENDER_TAG:
        if tag in tag_set:
            return subject, f'tag:{tag}'
    if tag_set & FEMALE_CODED_TAGS:
        return '1girl', 'inferred:bust_tags'
    return None, None


def auto_safety(tags):
    tag_set = set(tags)
    for tag in sorted(EXPLICIT_TAGS & tag_set):
        return 'explicit', f'tag:{tag}'
    for tag in sorted(NSFW_TAGS & tag_set):
        return 'nsfw', f'tag:{tag}'
    return 'safe', 'default'


def identity_conflicts(tags):
    tag_set = set(tags)
    findings = []
    if tag_set & SHORT_HAIR and tag_set & {
            'medium hair', 'long hair', 'very long hair', 'absurdly long hair'}:
        findings.append('HAIR_LENGTH_CONFLICT')
    if 'medium hair' in tag_set and tag_set & LONG_HAIR:
        findings.append('HAIR_LENGTH_CONFLICT')
    if len(tag_set & (SMALL_BUST | LARGE_BUST | MEDIUM_BUST)) > 1:
        findings.append('BUST_SIZE_CONFLICT')
    if len(tag_set & EYE_COLOR_TAGS) > 1 and not tag_set & HETEROCHROMIA_TAGS:
        findings.append('EYE_COLOR_CONFLICT')
    return sorted(set(findings))


def build_prompt(mode, quality_prefix, safety, subject, identity_tags):
    parts = []
    if mode == 'anima':
        parts.extend(quality_prefix)
        parts.append(safety)
        if subject:
            parts.append(subject)
        parts.append('solo')
    parts.extend(identity_tags)
    return ', '.join(dict.fromkeys(p for p in parts if p))


def sql_filters(characters, universe):
    clauses, params = [], []
    for value in characters:
        clauses.append('(lower(c.id)=lower(?) OR lower(c.slug)=lower(?) '
                       'OR lower(c.display_name)=lower(?))')
        params.extend([value, value, value])
    if universe:
        clauses.append('(lower(u.id)=lower(?) OR lower(u.slug)=lower(?) '
                       'OR lower(u.display_name)=lower(?))')
        params.extend([universe, universe, universe])
    return (' AND ' + ' AND '.join(clauses)) if clauses else '', params


def records(con, args):
    roles = ROLES
    role_slots = ','.join('?' for _ in roles)
    role_case = ' '.join(
        f"WHEN '{role}' THEN {index}" for index, role in enumerate(roles))
    where, where_params = sql_filters(args.character, args.universe)
    query = f'''
        SELECT c.id, c.slug, c.display_name, c.identity_json, c.age_status,
               c.identity_review, c.universe_id,
               u.slug AS universe_slug, u.display_name AS universe_name,
               ct.tag_role, t.name AS tag_name
        FROM characters c
        LEFT JOIN universes u ON u.id = c.universe_id
        LEFT JOIN character_tags ct ON ct.character_id = c.id
             AND ct.tag_role IN ({role_slots})
        LEFT JOIN catalog_tags t ON t.id = ct.tag_id
        WHERE 1=1{where}
        ORDER BY c.id, CASE ct.tag_role {role_case} ELSE 99 END, ct.rowid, t.name
    '''
    cursor = con.execute(query, [*roles, *where_params])
    rows = (row for row in cursor if row['id'] is not None)
    for _, group in groupby(rows, key=itemgetter('id')):
        group = list(group)
        head = group[0]
        identity = json.loads(head['identity_json'] or '{}')
        character_tag, tag_source = resolve_character_tag(identity, head['display_name'])
        series_tag = resolve_series_tag(
            identity, head['universe_slug'], head['universe_name'])

        tags_by_role = {role: [] for role in roles}
        for row in group:
            if row['tag_name']:
                tags_by_role[row['tag_role']].append(normalize_tag(row['tag_name']))
        for role in roles:
            tags_by_role[role] = list(dict.fromkeys(tags_by_role[role]))

        all_tags = [tag for role in roles for tag in tags_by_role[role]]
        subject, subject_source = infer_subject(all_tags)
        if args.subject:
            subject, subject_source = args.subject, 'explicit'

        safety = args.safety
        safety_source = 'explicit'
        if safety == 'auto':
            safety, safety_source = auto_safety(all_tags)

        seen = {character_tag}
        if series_tag:
            seen.add(series_tag)
        identity_anchors = []
        for tag in tags_by_role[IDENTITY_ROLE]:
            if not tag or tag in seen or tag in COMPOSITION_TAGS:
                continue
            seen.add(tag)
            identity_anchors.append(tag)
        outfit_tags = []
        for tag in tags_by_role[OUTFIT_ROLE]:
            if not tag or tag in seen or tag in COMPOSITION_TAGS:
                continue
            seen.add(tag)
            outfit_tags.append(tag)

        identity_tags = [character_tag]
        if series_tag:
            identity_tags.append(series_tag)
        identity_tags.extend(identity_anchors)
        prompt_tags = identity_tags + outfit_tags

        warnings = []
        if not identity_anchors:
            warnings.append('NO_IDENTITY_ANCHORS')
        if not outfit_tags:
            warnings.append('NO_OUTFIT_TAGS')
        if not series_tag:
            warnings.append('SERIES_TAG_MISSING')
        if not subject:
            warnings.append('SUBJECT_UNKNOWN')
        if head['identity_review'] not in ('REVIEWED', 'VERIFIED'):
            warnings.append('IDENTITY_NOT_REVIEWED')
        warnings.extend(identity_conflicts(identity_anchors))

        yield {
            'character_id': head['id'],
            'slug': head['slug'],
            'display_name': head['display_name'],
            'universe_id': head['universe_id'],
            'universe': head['universe_name'],
            'identity_review': head['identity_review'],
            'age_status': head['age_status'],
            'identity_tag': character_tag,
            'identity_tag_source': tag_source,
            'series_tag': series_tag,
            'subject': subject,
            'subject_source': subject_source,
            'safety': safety,
            'safety_source': safety_source,
            'identity_tags': identity_tags,
            'identity_anchors': identity_anchors,
            'outfit_tags': outfit_tags,
            'tag_counts': {'identity': len(identity_anchors), 'outfit': len(outfit_tags)},
            'warnings': warnings,
            'prompt': build_prompt(args.mode, args.quality, safety, subject, prompt_tags),
        }


def write_record(stream, fmt, record):
    if fmt == 'jsonl':
        stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True,
                                separators=(',', ':')) + '\n')
    elif fmt == 'tsv':
        fields = (record['character_id'], record['slug'], record['display_name'],
                  record['universe'] or '', record['subject'] or '',
                  record['safety'], record['identity_tag'],
                  record['series_tag'] or '', record['prompt'])
        stream.write('\t'.join(str(f).replace('\t', ' ').replace('\n', ' ')
                               for f in fields) + '\n')
    else:
        stream.write(record['prompt'] + '\n')


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--db', type=Path, default=DEFAULT_DB,
                        help=f'SQLite database (default: {DEFAULT_DB})')
    parser.add_argument('--out', default=str(DEFAULT_OUT),
                        help=f'output path, or - for stdout (default: {DEFAULT_OUT})')
    parser.add_argument('--format', choices=('jsonl', 'txt', 'tsv'), default='jsonl',
                        help='jsonl keeps metadata; txt is one prompt per line (default: jsonl)')
    parser.add_argument('--mode', choices=('anima', 'packet'), default='anima',
                        help='anima = quality+safety+subject+identity+outfit; packet = tags only')
    parser.add_argument('--character', action='append', default=[], metavar='ID|SLUG|NAME',
                        help='exact character id, slug or display name (repeatable)')
    parser.add_argument('--universe', metavar='SLUG|NAME',
                        help='exact universe id, slug or display name')
    parser.add_argument('--limit', type=int, help='stop after N characters')
    parser.add_argument('--require-identity', action='store_true',
                        help='skip characters with no identity anchors')
    parser.add_argument('--require-outfit', action='store_true',
                        help='skip characters with no outfit tags')
    parser.add_argument('--include-empty', action='store_true',
                        help='also export characters with neither identity nor outfit tags')
    parser.add_argument('--quality', type=parse_tags, default=parse_tags(DEFAULT_QUALITY),
                        help=f'quality prefix (default: {DEFAULT_QUALITY})')
    parser.add_argument('--no-quality', action='store_true', help='drop the quality prefix')
    parser.add_argument('--safety', choices=('auto', 'safe', 'sensitive', 'nsfw', 'explicit'),
                        default='auto', help='safety tag, auto reads clear nudity tags')
    parser.add_argument('--subject', choices=('1girl', '1boy', '1other'),
                        help='override subject count (default: infer from tags)')
    parser.add_argument('--progress', action='store_true',
                        help='print progress to stderr every 25000 characters')
    args = parser.parse_args(argv)
    if args.no_quality:
        args.quality = []
    if args.limit is not None and args.limit < 1:
        parser.error('--limit must be >= 1')
    return args


def main(argv=None):
    args = parse_args(argv)
    if not args.db.exists():
        raise SystemExit(f'DB not found: {args.db}')
    if args.out == '-':
        stream, close = sys.stdout, False
    else:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        stream, close = out.open('w', encoding='utf-8', newline='\n'), True

    started = time.perf_counter()
    scanned = skipped = with_identity = with_outfit = 0
    try:
        con = sqlite3.connect(args.db)
        con.row_factory = sqlite3.Row
        con.execute('PRAGMA query_only = ON')
        if args.format == 'tsv':
            stream.write('character_id\tslug\tdisplay_name\tuniverse\tsubject\t'
                         'safety\tidentity_tag\tseries_tag\tprompt\n')
        for record in records(con, args):
            if not args.include_empty and not (record['identity_anchors'] or record['outfit_tags']):
                skipped += 1
                continue
            if args.require_identity and not record['identity_anchors']:
                skipped += 1
                continue
            if args.require_outfit and not record['outfit_tags']:
                skipped += 1
                continue
            write_record(stream, args.format, record)
            scanned += 1
            with_identity += bool(record['identity_anchors'])
            with_outfit += bool(record['outfit_tags'])
            if args.progress and scanned % 25000 == 0:
                print(f'... {scanned} characters', file=sys.stderr)
            if args.limit is not None and scanned >= args.limit:
                break
        con.close()
    finally:
        if close:
            stream.close()

    summary = {
        'status': 'OK',
        'db': str(args.db),
        'out': args.out,
        'format': args.format,
        'mode': args.mode,
        'characters': scanned,
        'skipped': skipped,
        'with_identity': with_identity,
        'with_outfit': with_outfit,
        'elapsed_seconds': round(time.perf_counter() - started, 2),
    }
    print(json.dumps(summary, ensure_ascii=False), file=sys.stderr if args.out == '-' else sys.stdout)
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (sqlite3.Error, OSError, json.JSONDecodeError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        sys.exit(2)
