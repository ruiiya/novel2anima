#!/usr/bin/env python3
"""Metadata-only catalog importers for Novel2Anima V1.4+.

The importers never download images. They preserve raw source metadata in
source_records, keep namespace boundaries, and mark unverified/derived data
explicitly. They are intentionally conservative: a tag, core tag, or generic
outfit is not promoted to canon identity, age, or an original outfit.
"""
from __future__ import annotations

import csv
import json
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
    """Import selected DraconicDragon CSV rows: name,category,post_count,aliases.

    V2 uses ``from_character_core_tags`` so only tags actually attached to an
    imported character are brought in, plus their aliases. It does not import
    the whole archive or the e621 namespace by default.
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
    rows = []
    with path.open(encoding='utf-8-sig', newline='') as handle:
        reader = csv.reader(handle)
        for raw in reader:
            if not raw or not raw[0].strip():
                continue
            name = raw[0].strip()
            if selected is not None and name not in selected:
                continue
            if limit is not None and counts['rows'] >= limit:
                break
            cat = _as_int(raw[1]) if len(raw) > 1 else None
            post_count = _as_int(raw[2]) if len(raw) > 2 else None
            aliases_raw = raw[3] if len(raw) > 3 else ''
            aliases = [a.strip() for a in aliases_raw.split(',') if a.strip()]
            counts['rows'] += 1
            counts['aliases'] += len(aliases)
            if cat is None:
                counts['invalid_category'] += 1
            else:
                categories[cat] = categories.get(cat, 0) + 1
            rows.append((name, cat, post_count, aliases))
    filter_info = {
        'from_character_core_tags': from_character_core_tags,
        'selected_names': len(selected) if selected is not None else None,
        'matched_rows': counts['rows'],
    }
    if dry_run:
        return {'status': 'DRY_RUN', 'source_id': 'dbr_e621_lists',
                'file': path.name, 'namespace': namespace, **counts,
                'categories': categories, **filter_info}

    seed(con)
    run_id = begin_import(con, 'dbr_e621_lists', {
        'file': path.name, 'namespace': namespace,
        'source_revision': source_revision, 'mode': 'csv-tags',
        **filter_info})
    before_tags = _count(con, 'catalog_tags')
    before_relations = _count(con, 'catalog_tag_relations')
    try:
        with con:
            batch_id, file_sha = _batch_record(
                con, 'dbr_e621_lists', path, 'tag_archive', run_id,
                source_revision, {'namespace': namespace,
                                  'row_count': counts['rows'],
                                  'alias_count': counts['aliases']})
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
            for name, cat, post_count, aliases in rows:
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
            **filter_info,
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
    """Import a Danbooru/e621 alias or implication JSON export.

    Accepts a list, or a dict containing tag_aliases/aliases or
    tag_implications/implications. API field names are normalized, but unknown
    rows are skipped rather than guessed.
    """
    if namespace not in TAXONOMY:
        raise ValueError('namespace must be danbooru or e621')
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
    normalized = []
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
