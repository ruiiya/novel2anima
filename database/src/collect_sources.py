#!/usr/bin/env python3
"""Metadata-only source collector for Novel2Anima.

Fetches files declared in database/collect/source_manifest.json into
database/imports, with SHA256 metadata, idempotent skips, history snapshots on
change, and a JSONL run log. It refuses image suffixes and never crawls a site.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = PROJECT_ROOT / 'database' / 'collect' / 'source_manifest.json'
IMPORTS_DIR = Path('database') / 'imports'
USER_AGENT = 'novel2anima-collector/1.0 (+local metadata collector)'
IMAGE_SUFFIXES = {'.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp', '.tif', '.tiff', '.avif'}


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_manifest(path: Path):
    data = json.loads(path.read_text(encoding='utf-8'))
    sources = data.get('sources')
    if not isinstance(sources, list):
        raise ValueError('Manifest must contain a sources array')
    return data


def iter_files(manifest, source_filter=None, group_filter=None):
    found_source = False
    found_group = False
    for source in manifest['sources']:
        source_id = source.get('id')
        if source_filter and source_id != source_filter:
            continue
        if source.get('enabled') is False:
            continue
        found_source = True
        if source.get('download_images'):
            raise ValueError(f'{source_id}: download_images=true is not allowed; collector is metadata-only')
        for field in ('consumer_skill', 'target_fields', 'used_in_step'):
            if not source.get(field):
                raise ValueError(f'{source_id}: enabled source missing {field}; V2 requires a consumer contract')
        groups = source.get('groups') or {}
        for key, entry in groups.items():
            if group_filter and key != group_filter:
                continue
            if entry.get('enabled') is False:
                continue
            found_group = True
            yield source_id, key, entry, source
        files = source.get('files') or {}
        for key, entry in files.items():
            if group_filter and key != group_filter:
                continue
            if entry.get('enabled') is False:
                continue
            found_group = True
            yield source_id, key, entry, source
    if source_filter and not found_source:
        raise ValueError(f'Unknown source: {source_filter}')
    if group_filter and not found_group:
        raise ValueError(f'Unknown group/file key: {group_filter}')


def safe_dest(imports_root: Path, value: str) -> Path:
    rel = PurePosixPath(str(value).replace('\\', '/'))
    if rel.is_absolute() or '..' in rel.parts:
        raise ValueError(f'Unsafe destination: {value}')
    if rel.suffix.lower() in IMAGE_SUFFIXES:
        raise ValueError(f'Refusing image destination in metadata collector: {value}')
    return imports_root.joinpath(*rel.parts)


def meta_path(dest: Path) -> Path:
    return dest.with_name(dest.name + '.meta.json')


def read_meta(dest: Path):
    path = meta_path(dest)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def write_meta(dest: Path, meta: dict):
    meta_path(dest).write_text(json.dumps(meta, ensure_ascii=False, indent=2) + '\n',
                               encoding='utf-8')


def append_log(imports_root: Path, record: dict):
    imports_root.mkdir(parents=True, exist_ok=True)
    with (imports_root / 'collection_runs.jsonl').open('a', encoding='utf-8') as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + '\n')


def archive_old(dest: Path):
    if not dest.exists():
        return
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    history = dest.parent / '.history'
    history.mkdir(parents=True, exist_ok=True)
    target = history / f'{stamp}-{dest.name}'
    counter = 1
    while target.exists():
        target = history / f'{stamp}-{counter}-{dest.name}'
        counter += 1
    os.replace(dest, target)
    old_meta = meta_path(dest)
    if old_meta.exists():
        os.replace(old_meta, target.with_name(target.name + '.meta.json'))


def download(url: str, dest: Path, timeout: int, retries: int, max_bytes: int):
    last_error = None
    for attempt in range(retries + 1):
        req = urllib.request.Request(url, headers={
            'User-Agent': USER_AGENT,
            'Accept': 'application/json,text/plain,text/markdown,text/csv,*/*',
        })
        tmp = dest.with_name(dest.name + '.tmp')
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            digest = hashlib.sha256()
            total = 0
            with urllib.request.urlopen(req, timeout=timeout) as response:
                status = getattr(response, 'status', 200) or 200
                content_type = response.headers.get('Content-Type', '')
                with tmp.open('wb') as handle:
                    while True:
                        chunk = response.read(1024 * 1024)
                        if not chunk:
                            break
                        total += len(chunk)
                        if total > max_bytes:
                            raise ValueError(f'Response exceeds max_bytes={max_bytes}')
                        digest.update(chunk)
                        handle.write(chunk)
            return {'tmp': tmp, 'sha256': digest.hexdigest(), 'bytes': total,
                    'http_status': status, 'content_type': content_type,
                    'url': url}
        except urllib.error.HTTPError as exc:
            last_error = exc
            if tmp.exists():
                tmp.unlink()
            if exc.code == 429 or 500 <= exc.code < 600:
                retry_after = exc.headers.get('Retry-After') if exc.headers else None
                delay = int(retry_after) if retry_after and retry_after.isdigit() else min(2 ** attempt, 30)
                if attempt < retries:
                    time.sleep(delay)
                    continue
            raise RuntimeError(f'HTTP {exc.code} for {url}') from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
            if tmp.exists():
                tmp.unlink()
            if attempt < retries:
                time.sleep(min(2 ** attempt, 30))
                continue
            raise RuntimeError(f'Fetch failed for {url}: {exc}') from exc
        except Exception:
            if tmp.exists():
                tmp.unlink()
            raise
    raise RuntimeError(f'Fetch failed for {url}: {last_error}')


def fetch_one(imports_root: Path, source_id: str, key: str, entry: dict,
              force=False, timeout=60, retries=3, max_bytes=64 * 1024 * 1024):
    url = entry.get('url')
    if not url:
        raise ValueError(f'{source_id}/{key}: missing url')
    dest = safe_dest(imports_root, entry.get('dest') or f'{source_id}/{key}')
    if dest.suffix.lower() in IMAGE_SUFFIXES:
        raise ValueError(f'{source_id}/{key}: image files are not collected')
    old_sha = sha_bytes(dest.read_bytes()) if dest.exists() else None
    old_meta = read_meta(dest) if dest.exists() else {}
    # A manifest-pinned hash can be checked without network. Otherwise fetch and
    # compare, so a changed upstream file is never hidden by stale local meta.
    expected = entry.get('sha256')
    if dest.exists() and not force and expected and old_sha == expected:
        return {'source_id': source_id, 'key': key, 'status': 'SKIPPED',
                'dest': str(dest), 'sha256': old_sha, 'bytes': dest.stat().st_size}

    result = download(url, dest, timeout, retries, max_bytes)
    new_sha = result['sha256']
    tmp = result['tmp']
    if dest.exists() and old_sha == new_sha:
        tmp.unlink(missing_ok=True)
        meta = old_meta or {}
        meta.update({'source_id': source_id, 'key': key, 'url': url,
                     'sha256': new_sha, 'bytes': result['bytes'],
                     'http_status': result['http_status'],
                     'content_type': result['content_type'],
                     'source_revision': entry.get('source_revision'),
                     'license_note': entry.get('license_note'),
                     'retrieved_at': meta.get('retrieved_at') or now_iso(),
                     'last_checked_at': now_iso()})
        write_meta(dest, meta)
        return {'source_id': source_id, 'key': key, 'status': 'SKIPPED',
                'dest': str(dest), 'sha256': new_sha, 'bytes': result['bytes']}

    if dest.exists():
        archive_old(dest)
    os.replace(tmp, dest)
    meta = {
        'source_id': source_id,
        'key': key,
        'url': url,
        'sha256': new_sha,
        'bytes': result['bytes'],
        'http_status': result['http_status'],
        'content_type': result['content_type'],
        'source_revision': entry.get('source_revision'),
        'license_note': entry.get('license_note'),
        'retrieved_at': now_iso(),
    }
    write_meta(dest, meta)
    return {'source_id': source_id, 'key': key, 'status': 'FETCHED',
            'dest': str(dest), 'sha256': new_sha, 'bytes': result['bytes'],
            'http_status': result['http_status']}


def command_list(manifest, source_filter=None):
    rows = []
    for source_id, key, entry, source in iter_files(manifest, source_filter):
        rows.append({'source_id': source_id, 'key': key,
                     'url': entry.get('url'),
                     'dest': entry.get('dest'),
                     'source_revision': entry.get('source_revision')})
    print(json.dumps(rows, ensure_ascii=False, indent=2))
    return 0


def command_fetch(manifest, root: Path, source_filter, group_filter, force,
                  timeout, retries, dry_run):
    imports_root = root / IMPORTS_DIR
    results = []
    for source_id, key, entry, source in iter_files(manifest, source_filter, group_filter):
        if dry_run:
            results.append({'source_id': source_id, 'key': key,
                            'status': 'DRY_RUN', 'url': entry.get('url'),
                            'dest': str(safe_dest(imports_root, entry.get('dest') or ''))})
            continue
        try:
            result = fetch_one(imports_root, source_id, key, entry, force, timeout, retries)
            result['at'] = now_iso()
            append_log(imports_root, result)
            results.append(result)
        except Exception as exc:
            record = {'source_id': source_id, 'key': key, 'status': 'FAILED',
                      'url': entry.get('url'), 'error': str(exc), 'at': now_iso()}
            append_log(imports_root, record)
            results.append(record)
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 1 if any(r['status'] == 'FAILED' for r in results) else 0


def command_verify(manifest, root: Path, source_filter=None):
    imports_root = root / IMPORTS_DIR
    results = []
    ok = True
    for source_id, key, entry, source in iter_files(manifest, source_filter):
        dest = safe_dest(imports_root, entry.get('dest') or f'{source_id}/{key}')
        if not dest.exists():
            results.append({'source_id': source_id, 'key': key,
                            'status': 'MISSING', 'dest': str(dest)})
            ok = False
            continue
        actual = sha_bytes(dest.read_bytes())
        meta = read_meta(dest)
        expected = entry.get('sha256') or meta.get('sha256')
        status = 'OK' if not expected or actual == expected else 'MISMATCH'
        ok = ok and status == 'OK'
        results.append({'source_id': source_id, 'key': key, 'status': status,
                        'dest': str(dest), 'sha256': actual,
                        'expected': expected})
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0 if ok else 1


def main():
    parser = argparse.ArgumentParser(description='Novel2Anima metadata-only source collector')
    parser.add_argument('--root', type=Path, default=PROJECT_ROOT,
                        help='project root; downloads go under <root>/database/imports')
    parser.add_argument('--manifest', type=Path, default=DEFAULT_MANIFEST)
    sub = parser.add_subparsers(dest='action', required=True)
    p = sub.add_parser('list')
    p.add_argument('--source')
    p = sub.add_parser('fetch')
    p.add_argument('--source')
    p.add_argument('--group')
    p.add_argument('--force', action='store_true')
    p.add_argument('--dry-run', action='store_true')
    p.add_argument('--timeout', type=int, default=60)
    p.add_argument('--retries', type=int, default=3)
    p = sub.add_parser('verify')
    p.add_argument('--source')
    args = parser.parse_args()

    manifest = load_manifest(args.manifest)
    if args.action == 'list':
        return command_list(manifest, args.source)
    if args.action == 'fetch':
        return command_fetch(manifest, args.root, args.source, args.group,
                             args.force, args.timeout, args.retries, args.dry_run)
    return command_verify(manifest, args.root, args.source)


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, OSError, RuntimeError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        raise SystemExit(1)
