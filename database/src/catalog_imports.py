#!/usr/bin/env python3
"""Metadata-only catalog importers for Novel2Anima V1.4+.

The importers never download images. They preserve raw source metadata in
source_records, keep namespace boundaries, and mark unverified/derived data
explicitly. They are intentionally conservative: a tag, core tag, or generic
outfit is not promoted to canon identity, age, or an original outfit.
"""
from __future__ import annotations

import csv
import gzip
import json
from itertools import chain
from pathlib import Path

from n2m_db import (begin_import, finish_import, js, seed, sha, slugify,
                    track_source_record)

# Source-specific category labels. The raw integer is always preserved; this
# table only gives it a namespace-local meaning. Do not apply Danbooru's enum
# to e621 rows.
TAXONOMY = {
    'danbooru': {
        0: 'general',
        1: 'artist',
        3: 'copyright',
        4: 'character',
        5: 'meta',
    },
    'e621': {
        0: 'general',
        1: 'artist',
        2: 'invalid',
        3: 'copyright',
        4: 'character',
        5: 'species',
        6: 'invalid',
        7: 'meta',
        8: 'lore',
    },
}

def _count(con, table):
    return con.execute(f'SELECT count(*) FROM {table}').fetchone()[0]


def _as_int(value):
    if value is None or value == '':
        return None
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _load_json(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


def _open_text(path: Path):
    """Plain or gzip-compressed UTF-8 CSV/JSON text handle."""
    opener = gzip.open if str(path).lower().endswith('.gz') else open
    return opener(path, 'rt', encoding='utf-8-sig', newline='')


def _iter_csv(path: Path, columns):
    """Yield value lists ordered as ``columns`` from a plain or .gz CSV.

    A header row is honored when it names ``name`` and ``category``; the
    headerless ``name,category,post_count,aliases`` layout used by the
    DraconicDragon CSVs keeps working. Missing columns yield ''.
    """
    with _open_text(path) as handle:
        reader = csv.reader(handle)
        first = next(reader, None)
        if first is None:
            return
        index = {name: i for i, name in enumerate(first)}
        has_header = ('name' in index and 'category' in index) or \
            'antecedent_name' in index
        source = reader if has_header else chain([first], reader)
        for raw in source:
            if not raw:
                continue
            if has_header:
                yield [raw[index[c]] if c in index and index[c] < len(raw) else ''
                       for c in columns]
            else:
                yield (raw + [''] * len(columns))[:len(columns)]


def _iter_items(data, keys=('items', 'data', 'poses', 'outfits', 'portraits')):
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in keys:
            value = data.get(key)
            if isinstance(value, list):
                return value
        results = data.get('results')
        if isinstance(results, dict):
            for key in keys:
                value = results.get(key)
                if isinstance(value, list):
                    return value
    raise ValueError('JSON must be an array or contain an items/data array')


def _batch_record(con, source_id, path: Path, entity_kind, run_id,
                  source_revision=None, extra=None):
    file_sha = sha(path.read_bytes())
    payload = {
        'file': path.name,
        'sha256': file_sha,
        'bytes': path.stat().st_size,
        'source_revision': source_revision,
    }
    if extra:
        payload.update(extra)
    record_id = track_source_record(
        con, source_id, f'file/{path.name}', entity_kind, payload, run_id)
    return record_id, file_sha


def _insert_caption(con, source_record_id, entity_kind, entity_id, lang,
                    text, origin='SOURCE', review='UNREVIEWED'):
    if not text:
        return None
    caption_id = f'caption:{sha(f"{entity_kind}|{entity_id}|{lang}|{text}")[:18]}'
    con.execute('''INSERT INTO catalog_captions
        (id,entity_kind,entity_id,lang,text,origin,review,source_record_id)
        VALUES(?,?,?,?,?,?,?,?)
        ON CONFLICT(id) DO UPDATE SET
          text=excluded.text, origin=excluded.origin, review=excluded.review,
          source_record_id=excluded.source_record_id''',
        (caption_id, entity_kind, entity_id, lang, text, origin, review,
         source_record_id))
    return caption_id


def _ok_details(source_id, path, details, run_id):
    out = {'source_id': source_id, 'file': path.name, 'import_run_id': run_id}
    out.update(details)
    return out


def import_tags_csv(con, path: Path, namespace: str, limit=None,
                    with_aliases=True, source_revision=None, dry_run=False,
                    from_character_core_tags=False):
    """Import a tag archive CSV (plain or .gz): name,category,post_count,aliases.

    Accepts both the headerless DraconicDragon layout and a headered dump such as
    id,name,category,post_count,... (aliases then come from a relations file).
    V2 uses ``from_character_core_tags`` so only tags actually attached to an
    imported character are brought in, plus their aliases.
    """
    if namespace not in TAXONOMY:
        raise ValueError('namespace must be danbooru or e621')
    selected = None
    if from_character_core_tags:
        selected = {r[0] for r in con.execute('''
            SELECT DISTINCT t.name FROM character_tags ct
            JOIN catalog_tags t ON t.id=ct.tag_id
            WHERE t.namespace='danbooru' ''')}
        if not selected:
            raise ValueError('No character core tags found; import DeepGHS first')
    counts = {'rows': 0, 'aliases': 0, 'invalid_category': 0}
    categories = {}

    def rows():
        for name, cat_raw, post_raw, aliases_raw in _iter_csv(
                path, ('name', 'category', 'post_count', 'aliases')):
            name = name.strip()
            if not name:
                continue
            if selected is not None and name not in selected:
                continue
            if limit is not None and counts['rows'] >= limit:
                return
            cat = _as_int(cat_raw)
            post_count = _as_int(post_raw)
            aliases = _split_list(aliases_raw)
            counts['rows'] += 1
            counts['aliases'] += len(aliases)
            if cat is None:
                counts['invalid_category'] += 1
            else:
                categories[cat] = categories.get(cat, 0) + 1
            yield name, cat, post_count, aliases

    def filter_info():
        return {
            'from_character_core_tags': from_character_core_tags,
            'selected_names': len(selected) if selected is not None else None,
            'matched_rows': counts['rows'],
        }

    if dry_run:
        for _ in rows():
            pass
        return {'status': 'DRY_RUN', 'source_id': 'dbr_e621_lists',
                'file': path.name, 'namespace': namespace, **counts,
                'categories': categories, **filter_info()}

    seed(con)
    run_id = begin_import(con, 'dbr_e621_lists', {
        'file': path.name, 'namespace': namespace,
        'source_revision': source_revision, 'mode': 'csv-tags',
        **filter_info()})
    before_tags = _count(con, 'catalog_tags')
    before_relations = _count(con, 'catalog_tag_relations')
    try:
        with con:
            batch_id, file_sha = _batch_record(
                con, 'dbr_e621_lists', path, 'tag_archive', run_id,
                source_revision, {'namespace': namespace})
            tag_sql = '''INSERT INTO catalog_tags
                (id,namespace,name,original_name,category,post_count,deprecated,source_record_id)
                VALUES(?,?,?,?,?,?,0,?)
                ON CONFLICT(namespace,name) DO UPDATE SET
                  original_name=excluded.original_name, category=excluded.category,
                  post_count=excluded.post_count, deprecated=excluded.deprecated,
                  source_record_id=excluded.source_record_id'''
            alias_sql = '''INSERT INTO catalog_tag_relations
                (namespace,antecedent,consequent,relation_type,status,source_record_id)
                VALUES(?,?,?,'ALIAS','archive_unspecified',?)
                ON CONFLICT(namespace,antecedent,consequent,relation_type) DO UPDATE SET
                  status=excluded.status, source_record_id=excluded.source_record_id'''
            tag_batch = []
            alias_batch = []
            for name, cat, post_count, aliases in rows():
                tag_id = f'tag:{namespace}:{sha(name)[:18]}'
                tag_batch.append((tag_id, namespace, name, name, cat,
                                  post_count, batch_id))
                if with_aliases:
                    for alias in aliases:
                        alias_batch.append((namespace, alias, name, batch_id))
                if len(tag_batch) >= 5000:
                    con.executemany(tag_sql, tag_batch)
                    tag_batch.clear()
                if len(alias_batch) >= 10000:
                    con.executemany(alias_sql, alias_batch)
                    alias_batch.clear()
            if tag_batch:
                con.executemany(tag_sql, tag_batch)
            if alias_batch:
                con.executemany(alias_sql, alias_batch)
            taxonomy_sql = '''INSERT INTO catalog_tag_taxonomy
                (namespace,category,label,source_record_id) VALUES(?,?,?,?)
                ON CONFLICT(namespace,category) DO UPDATE SET
                  label=excluded.label, source_record_id=excluded.source_record_id'''
            con.executemany(taxonomy_sql, [
                (namespace, cat, TAXONOMY[namespace].get(cat, f'category_{cat}'), batch_id)
                for cat in sorted(categories)])
        after_tags = _count(con, 'catalog_tags')
        after_relations = _count(con, 'catalog_tag_relations')
        details = _ok_details('dbr_e621_lists', path, {
            'namespace': namespace, 'sha256': file_sha,
            'rows_processed': counts['rows'], 'aliases_processed': counts['aliases'],
            'new_tags': after_tags - before_tags,
            'existing_or_updated': counts['rows'] - (after_tags - before_tags),
            'new_alias_relations': after_relations - before_relations,
            'invalid_category_rows': counts['invalid_category'],
            'categories': categories, 'with_aliases': with_aliases,
            'limit': limit, 'source_revision': source_revision,
            **filter_info(),
            'note': 'Aliases are tag relations, not character aliases; CSV archive does not expose per-alias status, so status=archive_unspecified.'}, run_id)
        finish_import(con, run_id, after_tags - before_tags,
                      counts['rows'] - (after_tags - before_tags),
                      details=details)
        return details
    except Exception as exc:
        con.rollback()
        finish_import(con, run_id, 0, 0, errors=1,
                      details={'file': path.name, 'namespace': namespace,
                               'error': str(exc)})
        raise


def import_tag_relations_json(con, path: Path, namespace: str, kind: str,
                              source_revision=None, dry_run=False):
    """Import alias/implication rows from JSON or a plain/.gz CSV export.

    JSON accepts a list, or a dict containing tag_aliases/aliases or
    tag_implications/implications. CSV needs antecedent_name, consequent_name
    and optional status columns (header honored). API field names are
    normalized, but unknown rows are skipped rather than guessed.
    """
    if namespace not in TAXONOMY:
        raise ValueError('namespace must be danbooru or e621')
    normalized = []
    if str(path).lower().endswith('.json'):
        data = _load_json(path)
        if isinstance(data, list):
            entries = data
        elif isinstance(data, dict):
            keys = (('tag_aliases', 'aliases') if kind == 'alias'
                    else ('tag_implications', 'implications'))
            entries = next((data[k] for k in keys if isinstance(data.get(k), list)), None)
            if entries is None and isinstance(data.get('results'), list):
                entries = data['results']
        else:
            entries = None
        if not isinstance(entries, list):
            raise ValueError('Unsupported relations JSON shape')
        for item in entries:
            if not isinstance(item, dict):
                continue
            antecedent = (item.get('antecedent_name') or item.get('antecedent')
                          or item.get('alias_name') or item.get('name'))
            consequent = (item.get('consequent_name') or item.get('consequent')
                          or item.get('tag_name') or item.get('target'))
            if not antecedent or not consequent:
                continue
            normalized.append((str(antecedent), str(consequent),
                               str(item.get('status') or 'active')))
    else:
        for antecedent, consequent, status in _iter_csv(
                path, ('antecedent_name', 'consequent_name', 'status')):
            antecedent, consequent = antecedent.strip(), consequent.strip()
            if antecedent and consequent:
                normalized.append((antecedent, consequent,
                                   status.strip() or 'active'))
    if dry_run:
        return {'status': 'DRY_RUN', 'source_id': 'dbr_e621_lists',
                'file': path.name, 'namespace': namespace, 'kind': kind,
                'relations': len(normalized)}

    seed(con)
    source_id = 'danbooru' if namespace == 'danbooru' else 'dbr_e621_lists'
    run_id = begin_import(con, source_id, {'file': path.name, 'namespace': namespace,
                                           'kind': kind, 'source_revision': source_revision})
    before = _count(con, 'catalog_tag_relations')
    relation_type = 'ALIAS' if kind == 'alias' else 'IMPLIES'
    try:
        with con:
            batch_id, file_sha = _batch_record(
                con, source_id, path, 'tag_relations', run_id,
                source_revision, {'namespace': namespace, 'kind': kind})
            con.executemany('''INSERT OR IGNORE INTO catalog_tag_relations
                (namespace,antecedent,consequent,relation_type,status,source_record_id)
                VALUES(?,?,?,?,?,?)''',
                [(namespace, a, c, relation_type, status, batch_id)
                 for a, c, status in normalized])
        after = _count(con, 'catalog_tag_relations')
        details = _ok_details(source_id, path, {
            'namespace': namespace, 'kind': kind, 'sha256': file_sha,
            'relations_processed': len(normalized),
            'new_relations': after - before,
            'source_revision': source_revision,
            'note': 'Raw relation export; aliases are not character aliases.'}, run_id)
        finish_import(con, run_id, after - before,
                      len(normalized) - (after - before), details=details)
        return details
    except Exception as exc:
        con.rollback()
        finish_import(con, run_id, 0, 0, errors=1,
                      details={'file': path.name, 'namespace': namespace,
                               'kind': kind, 'error': str(exc)})
        raise


def import_pose_gallery(con, path: Path, limit=None, source_revision=None,
                        dry_run=False):
    """Import ai-pose-gallery metadata, grouping multi-angle views by pose.

    A pose identity is (体系/system, 姿势编号/pose_code). The five angle images
    become one pose_reference plus five pose_reference_views. A single image or
    angle is never promoted to an independent pose.
    """
    items = [item for item in _iter_items(_load_json(path)) if isinstance(item, dict)]
    if limit is not None:
        items = items[:limit]
    groups = {}
    for item in items:
        system = str(item.get('体系') or '')
        code = str(item.get('姿势编号') or item.get('id') or sha(js(item))[:18])
        key = f'{system}|{code}' if system else code
        groups.setdefault(key, []).append(item)
    if dry_run:
        return {'status': 'DRY_RUN', 'source_id': 'ai_pose_gallery',
                'file': path.name, 'items': len(items),
                'pose_groups': len(groups)}
    seed(con)
    run_id = begin_import(con, 'ai_pose_gallery', {
        'file': path.name, 'source_revision': source_revision, 'mode': 'pose-json'})
    before_poses = _count(con, 'pose_references')
    before_views = _count(con, 'pose_reference_views')
    before_captions = _count(con, 'catalog_captions')
    try:
        with con:
            batch_id, file_sha = _batch_record(
                con, 'ai_pose_gallery', path, 'pose_gallery_file', run_id,
                source_revision, {'item_count': len(items), 'pose_groups': len(groups)})
            for group_key, views in groups.items():
                first = views[0]
                system = str(first.get('体系') or '')
                pose_code = str(first.get('姿势编号') or first.get('id')
                                or sha(js(first))[:18])
                ext_key = group_key
                pose_id = f'pose:ai_pose_gallery:{sha(ext_key)[:18]}'
                caption = str(first.get('姿势名称') or first.get('标题') or pose_code)
                pending = f'[ZH SOURCE / UNREVIEWED] {caption}'
                category = first.get('分类') or system
                source_url = None
                group_record = track_source_record(
                    con, 'ai_pose_gallery', f'pose/{ext_key}', 'pose_gallery_item',
                    {'system': system, 'pose_code': pose_code,
                     'pose_name': caption, 'views': views,
                     'source_file_sha256': file_sha,
                     'source_revision': source_revision}, run_id)
                con.execute('''INSERT INTO pose_references
                    (id,vocabulary_id,skeleton_format,skeleton_json,caption_en,
                     source_record_id,provenance_note,external_key,caption_lang,
                     caption_origin,caption_review,category,pose_code,source_url)
                    VALUES(?,NULL,'metadata_only',NULL,?,?,?,?, 'zh','SOURCE',
                           'UNREVIEWED',?,?,?)
                    ON CONFLICT(id) DO UPDATE SET
                      caption_en=excluded.caption_en,
                      source_record_id=excluded.source_record_id,
                      provenance_note=excluded.provenance_note,
                      external_key=excluded.external_key,
                      caption_lang=excluded.caption_lang,
                      caption_origin=excluded.caption_origin,
                      caption_review=excluded.caption_review,
                      category=excluded.category, pose_code=excluded.pose_code,
                      source_url=excluded.source_url''',
                    (pose_id, pending, group_record,
                     'AI Pose Gallery JSON metadata only; images not downloaded; caption pending review.',
                     ext_key, category, pose_code, source_url))
                for view in views:
                    view_key = str(view.get('id') or sha(js(view))[:18])
                    angle = str(view.get('角度') or 'unspecified')
                    view_record = track_source_record(
                        con, 'ai_pose_gallery', f'pose_view/{view_key}',
                        'pose_gallery_view',
                        {'item': {k: v for k, v in view.items()
                                  if k not in ('缩略图', '原图')},
                         'pose_group': ext_key,
                         'source_file_sha256': file_sha,
                         'source_revision': source_revision}, run_id)
                    view_id = f'view:{sha(f"{pose_id}|{angle}")[:18]}'
                    con.execute('''INSERT INTO pose_reference_views
                        (id,pose_reference_id,view_name,asset_id,depth_asset_id,annotation_json)
                        VALUES(?,?,?,NULL,NULL,?)
                        ON CONFLICT(id) DO UPDATE SET
                          view_name=excluded.view_name, asset_id=NULL,
                          annotation_json=excluded.annotation_json''',
                        (view_id, pose_id, angle,
                         js({'angle': angle, 'category': category,
                             'pose_code': pose_code,
                             'source_file_sha256': file_sha})))
                _insert_caption(con, group_record, 'pose_reference', pose_id, 'zh',
                                caption, origin='SOURCE', review='UNREVIEWED')
        details = _ok_details('ai_pose_gallery', path, {
            'sha256': file_sha, 'items_processed': len(items),
            'pose_groups': len(groups),
            'new_poses': _count(con, 'pose_references') - before_poses,
            'new_views': _count(con, 'pose_reference_views') - before_views,
            'new_captions': _count(con, 'catalog_captions') - before_captions,
            'source_revision': source_revision,
            'note': 'Multi-angle views are grouped under one pose; no skeleton, no image references; captions are source-language and UNREVIEWED.'}, run_id)
        finish_import(con, run_id, details['new_poses'] + details['new_views'],
                      (len(groups) + len(items)) - (details['new_poses'] + details['new_views']),
                      details=details)
        return details
    except Exception as exc:
        con.rollback()
        finish_import(con, run_id, 0, 0, errors=1,
                      details={'file': path.name, 'error': str(exc)})
        raise


def _item_name(item):
    return str(item.get('服装名称') or item.get('日文名称')
               or item.get('jp') or item.get('name') or item.get('id') or 'unnamed')


def _item_keywords(item):
    keywords = item.get('关键词')
    if isinstance(keywords, str) and keywords.strip():
        return keywords.strip()
    tags = item.get('标签')
    if isinstance(tags, list):
        return ', '.join(str(t) for t in tags if str(t).strip())
    raw_tags = item.get('tags')
    if isinstance(raw_tags, str):
        return raw_tags.strip()
    return ''


SOURCE_ID_STORYAURA = 'storyaura_danbooru_csv'


def _split_list(value):
    """Split a comma-separated source cell into stripped non-empty items."""
    if not value:
        return []
    return [v.strip() for v in str(value).split(',') if v.strip()]


def _read_csv_rows(path: Path, required: tuple):
    with path.open(encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames or []
        missing = [c for c in required if c not in fields]
        if missing:
            raise ValueError(f'{path.name}: missing columns {missing}; has {fields}')
        for row in reader:
            yield row


def _resolve_universe(con, copyright_tag):
    """Map a Danbooru copyright tag to a universe row (idempotent)."""
    if not copyright_tag:
        return None
    tag = copyright_tag.strip()
    if not tag:
        return None
    slug = slugify(tag)
    universe_id = f'universe:{slug}'
    con.execute('INSERT OR IGNORE INTO universes(id,slug,display_name) VALUES(?,?,?)',
                (universe_id, slug, tag.replace('_', ' ')))
    return universe_id


def _resolve_storyaura_character(con, tag, universe_id, identity_extra, counts):
    """Find or create the character row for a Danbooru character tag.

    Convergence rule: the same character tag under the same copyright is the
    same identity, so an existing (universe_id, slug) row is reused even when
    another source created it. A slug collision with a DIFFERENT danbooru tag
    is disambiguated with a short hash suffix instead of merging. No age or
    outfit inference: identity_review stays UNVERIFIED.
    """
    slug = slugify(tag)
    if universe_id:
        row = con.execute('SELECT id,identity_json FROM characters WHERE universe_id=? AND slug=?',
                          (universe_id, slug)).fetchone()
    else:
        row = con.execute('SELECT id,identity_json FROM characters WHERE universe_id IS NULL AND slug=?',
                          (slug,)).fetchone()
    if row is not None:
        ident = json.loads(row['identity_json'] or '{}')
        known_tag = ident.get('danbooru_tag')
        if known_tag is not None and known_tag != tag:
            # slugify collapsed two distinct Danbooru tags; do not merge.
            slug = f'{slug}_{sha(tag)[:6]}'
            row = None
        elif known_tag is None:
            # Row came from another importer without the tag marker; add it so
            # downstream resolution (e.g. appearance tags) can find this row.
            ident.update({'danbooru_tag': tag})
            ident.update({k: v for k, v in identity_extra.items()
                          if k not in ident})
            con.execute('UPDATE characters SET identity_json=?, updated_at=datetime(?) '
                        'WHERE id=?', (js(ident), 'now', row['id']))
        if row is not None:
            counts['existing'] += 1
            return row['id'], slug
    char_id = f'character:{SOURCE_ID_STORYAURA}:{sha(tag)[:18]}'
    ident = {'danbooru_tag': tag}
    ident.update(identity_extra)
    counts['new'] += con.execute('''INSERT OR IGNORE INTO characters
        (id,universe_id,slug,display_name,age_status,identity_json)
        VALUES(?,?,?,?,?,?)''',
        (char_id, universe_id, slug, tag.replace('_', ' '), 'UNKNOWN', js(ident))).rowcount
    return char_id, slug


def import_storyaura_characters(con, path: Path, limit=None, source_revision=None,
                                dry_run=False):
    """Import StoryAura danbooru_character_tags(_corrected).csv rows.

    Each row is one Danbooru character tag: its copyright (universe), aliases,
    parent tag (implication), post count and base_character (variant family).
    Variant characters stay separate rows; base_character becomes a
    CANDIDATE VARIANT_OF link, never a merge. Nothing is promoted to verified
    identity, age or canon outfit.
    """
    required = ('character_tag', 'other_names', 'copyright', 'parent_tag',
                'post_count', 'base_character')
    rows = []
    stats = {'rows': 0, 'aliases': 0, 'universes': set(), 'parents': 0,
             'base_links': 0, 'no_universe_skipped': 0}
    for row in _read_csv_rows(path, required):
        tag = (row.get('character_tag') or '').strip()
        if not tag:
            continue
        if not (row.get('copyright') or '').strip():
            # Scope decision: characters without a Danbooru copyright (no
            # universe) are not imported at all, not even universe-less rows.
            stats['no_universe_skipped'] += 1
            continue
        if limit is not None and stats['rows'] >= limit:
            break
        stats['rows'] += 1
        alias_count = len(_split_list(row.get('other_names')))
        stats['aliases'] += alias_count
        if (row.get('copyright') or '').strip():
            stats['universes'].add(row['copyright'].strip())
        else:
            stats['empty_universe'] += 1
        if (row.get('parent_tag') or '').strip():
            stats['parents'] += 1
        if (row.get('base_character') or '').strip():
            stats['base_links'] += 1
        rows.append(row)
    if dry_run:
        return {'status': 'DRY_RUN', 'source_id': SOURCE_ID_STORYAURA,
                'file': path.name, 'rows': stats['rows'],
                'aliases': stats['aliases'],
                'distinct_universes': len(stats['universes']),
                'rows_without_universe_skipped': stats['no_universe_skipped'],
                'rows_with_parent': stats['parents'],
                'rows_with_base_character': stats['base_links'],
                'limit': limit}
    seed(con)
    run_id = begin_import(con, SOURCE_ID_STORYAURA, {
        'file': path.name, 'source_revision': source_revision,
        'mode': 'storyaura-character-tags', 'rows': stats['rows']})
    before_chars = _count(con, 'characters')
    before_universes = _count(con, 'universes')
    before_aliases = _count(con, 'character_aliases')
    before_tags = _count(con, 'catalog_tags')
    before_relations = _count(con, 'catalog_tag_relations')
    before_links = _count(con, 'catalog_entity_links')
    counts = {'new': 0, 'existing': 0, 'alias_rows': 0, 'alias_self': 0,
              'tag_rows': 0, 'parent_rows': 0, 'base_rows': 0, 'own_tag_links': 0}
    try:
        with con:
            for row in rows:
                tag = row['character_tag'].strip()
                copyright_tag = (row.get('copyright') or '').strip()
                parent_tag = (row.get('parent_tag') or '').strip()
                base_character = (row.get('base_character') or '').strip()
                post_count = _as_int(row.get('post_count'))
                payload = {'character_tag': tag, 'other_names': row.get('other_names'),
                           'copyright': copyright_tag, 'parent_tag': parent_tag,
                           'post_count': post_count, 'base_character': base_character,
                           'source_revision': source_revision}
                record_id = track_source_record(
                    con, SOURCE_ID_STORYAURA, f'character_tag/{tag}',
                    'character_tag_row', payload, run_id)
                universe_id = _resolve_universe(con, copyright_tag)
                identity_extra = {'post_count': post_count,
                                  'danbooru_copyright': copyright_tag or None,
                                  'danbooru_parent_tag': parent_tag or None,
                                  'danbooru_base_character': base_character or None}
                char_id, _slug = _resolve_storyaura_character(
                    con, tag, universe_id, identity_extra, counts)
                display_name = tag.replace('_', ' ')
                # Character's own Danbooru tag: provenance + tag taxonomy only.
                con.execute('''INSERT INTO catalog_tags
                    (id,namespace,name,original_name,category,post_count,source_record_id)
                    VALUES(?,?,?,?,4,?,?)
                    ON CONFLICT(namespace,name) DO UPDATE SET
                      original_name=excluded.original_name, category=excluded.category,
                      post_count=excluded.post_count, source_record_id=excluded.source_record_id''',
                    (f'tag:danbooru:{sha(tag)[:18]}', 'danbooru', tag, tag,
                     post_count, record_id))
                counts['own_tag_links'] += con.execute(
                    '''INSERT OR IGNORE INTO catalog_entity_links
                    (id,left_entity_kind,left_entity_id,right_source,right_external_key,
                     relation,confidence,source_record_id)
                    VALUES(?,?,?,?,?,'DANBOORU_TAG','CANDIDATE',?)''',
                    (f'elink:{sha(f"character|{char_id}|danbooru|{tag}|DANBOORU_TAG")[:18]}',
                     'character', char_id, 'danbooru', tag, record_id)).rowcount
                if parent_tag:
                    counts['parent_rows'] += con.execute(
                        '''INSERT OR IGNORE INTO catalog_tag_relations
                        (namespace,antecedent,consequent,relation_type,status,source_record_id)
                        VALUES(?,?,?,'IMPLIES','active',?)''',
                        ('danbooru', tag, parent_tag, record_id)).rowcount
                if base_character:
                    counts['base_rows'] += con.execute(
                        '''INSERT OR IGNORE INTO catalog_entity_links
                        (id,left_entity_kind,left_entity_id,right_source,right_external_key,
                         relation,confidence,source_record_id)
                        VALUES(?,?,?,?,?,'VARIANT_OF','CANDIDATE',?)''',
                        (f'elink:{sha(f"character|{char_id}|danbooru|{base_character}|VARIANT_OF")[:18]}',
                         'character', char_id, 'danbooru', base_character, record_id)).rowcount
                for alias in _split_list(row.get('other_names')):
                    if alias == display_name or alias == tag:
                        counts['alias_self'] += 1
                        continue
                    counts['alias_rows'] += con.execute(
                        '''INSERT OR IGNORE INTO character_aliases
                        (id,character_id,name,language,source_record_id)
                        VALUES(?,?,?,'und',?)''',
                        (f'alias:{sha(f"{char_id}|{alias}|und")[:18]}',
                         char_id, alias, record_id)).rowcount
        details = {'sha256': sha(path.read_bytes()), 'rows_processed': stats['rows'],
                   'new_characters': _count(con, 'characters') - before_chars,
                   'existing_characters_reused': counts['existing'],
                   'new_universes': _count(con, 'universes') - before_universes,
                   'new_aliases': _count(con, 'character_aliases') - before_aliases,
                   'alias_self_deduped': counts['alias_self'],
                   'new_catalog_tags': _count(con, 'catalog_tags') - before_tags,
                   'new_implies_relations': _count(con, 'catalog_tag_relations') - before_relations,
                   'new_entity_links': _count(con, 'catalog_entity_links') - before_links,
                   'rows_without_universe_skipped': stats['no_universe_skipped'],
                   'rows_with_parent': stats['parents'],
                   'rows_with_base_character': stats['base_links'],
                   'source_revision': source_revision,
                   'note': ('Characters are Danbooru tag identities: UNVERIFIED, age UNKNOWN. '
                            'Rows without a Danbooru copyright are skipped entirely (scope '
                            'decision 2026-11-18: no universe-less characters). '
                            'Aliases come from other_names (language und). parent_tag is a tag '
                            'IMPLIES relation, base_character is a CANDIDATE VARIANT_OF link; '
                            'variants are never merged.')}
        finish_import(con, run_id, counts['new'], counts['existing'], details=details)
        return details
    except Exception as exc:
        con.rollback()
        finish_import(con, run_id, 0, 0, errors=1,
                      details={'file': path.name, 'error': str(exc)})
        raise


def import_storyaura_appearance(con, path: Path, limit=None, source_revision=None,
                                dry_run=False):
    """Import StoryAura danbooru_character_appearance(_corrected).csv rows.

    looks/outfit columns are statistical and CL-tagger derived tags: they are
    attached as APPEARANCE_CANDIDATE / OUTFIT_CANDIDATE character tags and are
    never promoted to VERIFIED appearance or a canon outfit. Rows are matched
    to characters in strict order: (1) DANBOORU_TAG entity link, (2) the
    identity_json danbooru_tag marker, (3) slug + universe fallback for
    manually added characters — the appearance 'series' must slugify to the
    character's universe and the slug must resolve to exactly one character
    in that universe; fallback matches also write the DANBOORU_TAG entity
    link so later runs resolve via the link. Unmatched rows are skipped,
    never guessed.
    """
    required = ('name', 'series', 'looks', 'outfit', 'alias', 'base_character')
    rows = []
    stats = {'rows': 0, 'looks_tags': 0, 'outfit_tags': 0}
    for row in _read_csv_rows(path, required):
        name = (row.get('name') or '').strip()
        if not name:
            continue
        if limit is not None and stats['rows'] >= limit:
            break
        stats['rows'] += 1
        stats['looks_tags'] += len(_split_list(row.get('looks')))
        stats['outfit_tags'] += len(_split_list(row.get('outfit')))
        rows.append(row)
    if dry_run:
        return {'status': 'DRY_RUN', 'source_id': SOURCE_ID_STORYAURA,
                'file': path.name, 'rows': stats['rows'],
                'looks_tags': stats['looks_tags'],
                'outfit_tags': stats['outfit_tags'], 'limit': limit}
    seed(con)
    tag_map = {}
    for crow in con.execute('''SELECT l.right_external_key AS tag,
                                      l.left_entity_id AS cid
        FROM catalog_entity_links l WHERE l.left_entity_kind='character'
        AND l.right_source='danbooru' AND l.relation='DANBOORU_TAG' '''):
        tag_map.setdefault(crow['tag'], crow['cid'])
    for crow in con.execute('SELECT id,identity_json FROM characters'):
        try:
            ident = json.loads(crow['identity_json'] or '{}')
        except ValueError:
            continue
        tag = ident.get('danbooru_tag')
        if tag:
            tag_map.setdefault(tag, crow['id'])
    # Slug + universe index for the manually-added-character fallback.
    slug_map = {}
    for crow in con.execute('SELECT id,universe_id,slug FROM characters '
                            'WHERE universe_id IS NOT NULL'):
        slug_map.setdefault((crow['universe_id'], crow['slug']), []).append(crow['id'])
    run_id = begin_import(con, SOURCE_ID_STORYAURA, {
        'file': path.name, 'source_revision': source_revision,
        'mode': 'storyaura-appearance', 'rows': stats['rows'],
        'character_index_size': len(tag_map)})
    before_ctags = _count(con, 'character_tags')
    before_tags = _count(con, 'catalog_tags')
    before_links = _count(con, 'catalog_entity_links')
    matched = unmatched = tag_rows = tag_conflicts = new_tags = 0
    fallback_matches = 0
    try:
        with con:
            for row in rows:
                name = row['name'].strip()
                tag = name.replace(' ', '_')
                char_id = tag_map.get(tag)
                via_fallback = False
                if char_id is None:
                    # Strict fallback for manually added characters: the
                    # appearance 'series' must slugify to the character's
                    # universe and the slug must be unambiguous there. Both
                    # the raw tag (spaces -> underscores, brackets kept —
                    # import-character-list stores the raw tag as slug) and
                    # its slugified form are tried.
                    series_slug = slugify((row.get('series') or '').strip())
                    universe_key = f'universe:{series_slug}'
                    candidates = []
                    for key in (tag, slugify(tag)):
                        candidates = slug_map.get((universe_key, key), [])
                        if candidates:
                            break
                    if len(candidates) == 1:
                        char_id = candidates[0]
                        via_fallback = True
                        con.execute(
                            '''INSERT OR IGNORE INTO catalog_entity_links
                            (id,left_entity_kind,left_entity_id,right_source,
                             right_external_key,relation,confidence,
                             source_record_id)
                            VALUES(?,?,?,?,?,'DANBOORU_TAG','CANDIDATE',NULL)''',
                            (f'elink:{sha(f"character|{char_id}|danbooru|{tag}|DANBOORU_TAG")[:18]}',
                             'character', char_id, 'danbooru', tag))
                        tag_map.setdefault(tag, char_id)
                        fallback_matches += 1
                if char_id is None:
                    unmatched += 1
                    continue
                matched += 1
                payload = {'name': name, 'series': row.get('series'),
                           'looks': row.get('looks'), 'outfit': row.get('outfit'),
                           'base_character': row.get('base_character'),
                           'source_revision': source_revision}
                record_id = track_source_record(
                    con, SOURCE_ID_STORYAURA, f'character_appearance/{tag}',
                    'character_appearance_row', payload, run_id)
                seen = set()
                for role, column in (('APPEARANCE_CANDIDATE', 'looks'),
                                     ('OUTFIT_CANDIDATE', 'outfit')):
                    for raw in _split_list(row.get(column)):
                        # Appearance cells use spaces instead of underscores.
                        tag_name = raw.replace(' ', '_')
                        if tag_name in seen:
                            continue
                        seen.add(tag_name)
                        tid = tag_map.get(f'tagcache:{tag_name}')
                        if tid is None:
                            con.execute('''INSERT INTO catalog_tags
                                (id,namespace,name,original_name,source_record_id)
                                VALUES(?,?,?,?,?)
                                ON CONFLICT(namespace,name) DO UPDATE SET
                                  original_name=excluded.original_name,
                                  source_record_id=excluded.source_record_id''',
                                (f'tag:danbooru:{sha(tag_name)[:18]}', 'danbooru',
                                 tag_name, tag_name, record_id))
                            tid = con.execute(
                                'SELECT id FROM catalog_tags WHERE namespace=? AND name=?',
                                ('danbooru', tag_name)).fetchone()['id']
                            tag_map[f'tagcache:{tag_name}'] = tid
                            new_tags += 1
                        changed = con.execute(
                            '''INSERT OR IGNORE INTO character_tags
                            (character_id,tag_id,source_record_id,tag_role)
                            VALUES(?,?,?,?)''',
                            (char_id, tid, record_id, role)).rowcount
                        if changed:
                            tag_rows += 1
                        else:
                            tag_conflicts += 1
        details = {'sha256': sha(path.read_bytes()), 'rows_processed': stats['rows'],
                   'rows_matched': matched, 'rows_unmatched': unmatched,
                   'slug_universe_fallback_matches': fallback_matches,
                   'new_character_tag_rows': _count(con, 'character_tags') - before_ctags,
                   'duplicate_pairs_ignored': tag_conflicts,
                   'new_catalog_tags': _count(con, 'catalog_tags') - before_tags,
                   'new_entity_links': _count(con, 'catalog_entity_links') - before_links,
                   'source_revision': source_revision,
                   'note': ('looks/outfit are statistical/CL-tagger derived CANDIDATE tags '
                            '(roles APPEARANCE_CANDIDATE/OUTFIT_CANDIDATE), not verified '
                            'appearance or canon outfits; appearance-file aliases are not '
                            'imported because the character tag file already carries the '
                            'extended alias set. Resolution order: DANBOORU_TAG link, '
                            'identity_json danbooru_tag, then strict slug+universe '
                            'fallback for manually added characters (which also writes '
                            'the DANBOORU_TAG link). Rows without a universe or absent '
                            'from the tag roster are skipped, not guessed.')}
        finish_import(con, run_id, matched, unmatched, details=details)
        return details
    except Exception as exc:
        con.rollback()
        finish_import(con, run_id, 0, 0, errors=1,
                      details={'file': path.name, 'error': str(exc)})
        raise


def import_generic_outfits(con, path: Path, source_id='ai_pose_gallery',
                           limit=None, source_revision=None, dry_run=False):
    """Import generic outfit metadata. Never creates a character or canon outfit."""
    items = _iter_items(_load_json(path), keys=('items', 'data', 'outfits'))
    if limit is not None:
        items = items[:limit]
    if dry_run:
        return {'status': 'DRY_RUN', 'source_id': source_id,
                'file': path.name, 'items': len(items)}
    seed(con)
    run_id = begin_import(con, source_id, {
        'file': path.name, 'source_revision': source_revision,
        'mode': 'generic-outfits'})
    before_outfits = _count(con, 'outfits')
    before_parts = _count(con, 'outfit_parts')
    before_captions = _count(con, 'catalog_captions')
    try:
        with con:
            batch_id, file_sha = _batch_record(
                con, source_id, path, 'outfit_gallery_file', run_id,
                source_revision, {'item_count': len(items)})
            for item in items:
                if not isinstance(item, dict):
                    continue
                ext_key = str(item.get('id') or item.get('服装名称')
                              or sha(js(item))[:18])
                name = _item_name(item)
                keywords = _item_keywords(item)
                item_id = track_source_record(
                    con, source_id, f'outfit/{ext_key}', 'outfit_gallery_item',
                    {'item': item, 'source_file_sha256': file_sha,
                     'source_revision': source_revision}, run_id)
                slug = slugify(f'{source_id}_{ext_key}')
                existing = con.execute(
                    'SELECT id FROM outfits WHERE character_id IS NULL AND slug=?',
                    (slug,)).fetchone()
                outfit_id = existing['id'] if existing else \
                    f'outfit:generic:{sha(f"{source_id}|{ext_key}")[:18]}'
                con.execute('''INSERT INTO outfits
                    (id,character_id,slug,name,outfit_kind,description,palette_json,
                     verification,source_record_id)
                    VALUES(?,NULL,?,?,'GENERIC',?,'[]','UNVERIFIED',?)
                    ON CONFLICT(id) DO UPDATE SET
                      name=excluded.name, description=excluded.description,
                      source_record_id=excluded.source_record_id''',
                    (outfit_id, slug, name, name, item_id))
                con.execute('''INSERT INTO outfit_parts
                    (id,outfit_id,slot,description,color_json,source_record_id)
                    VALUES(?,?,'full',?,'[]',?)
                    ON CONFLICT(outfit_id,slot) DO UPDATE SET
                      description=excluded.description,
                      source_record_id=excluded.source_record_id''',
                    (f'part:{sha(f"{outfit_id}|full")[:18]}', outfit_id, name, item_id))
                _insert_caption(con, item_id, 'outfit', outfit_id, 'zh', name,
                                origin='SOURCE', review='UNREVIEWED')
                if keywords:
                    _insert_caption(con, item_id, 'outfit', outfit_id, 'en',
                                    keywords, origin='SOURCE_KEYWORDS',
                                    review='UNREVIEWED')
        details = _ok_details(source_id, path, {
            'sha256': file_sha, 'items_processed': len(items),
            'new_outfits': _count(con, 'outfits') - before_outfits,
            'new_parts': _count(con, 'outfit_parts') - before_parts,
            'new_captions': _count(con, 'catalog_captions') - before_captions,
            'outfit_kind': 'GENERIC', 'verification': 'UNVERIFIED',
            'source_revision': source_revision,
            'note': 'Generic text metadata only; no character_id, no ORIGINAL outfit claim, no image references.'},
            run_id)
        finish_import(con, run_id, details['new_outfits'],
                      len(items) - details['new_outfits'], details=details)
        return details
    except Exception as exc:
        con.rollback()
        finish_import(con, run_id, 0, 0, errors=1,
                      details={'file': path.name, 'error': str(exc)})
        raise
