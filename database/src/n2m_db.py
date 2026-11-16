#!/usr/bin/env python3
"""Novel2Moss DB: stdlib-only SQLite, catalog imports and natural prompt export.

No network requests are made. Fetch external data explicitly after checking source terms.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / 'data' / 'novel2moss.db'


def js(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def sha(value: bytes | str) -> str:
    if isinstance(value, str):
        value = value.encode('utf-8')
    return hashlib.sha256(value).hexdigest()


def uid(prefix: str) -> str:
    return f'{prefix}_{uuid.uuid4().hex[:18]}'


def connect(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA foreign_keys = ON')
    con.execute('PRAGMA journal_mode = WAL')
    con.execute('PRAGMA busy_timeout = 5000')
    return con


def _table_exists(con, name):
    return con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None


def _backup_render_state(con):
    """Export V1 render/QA rows to a sidecar before migration 005 drops them."""
    jobs = [dict(r) for r in con.execute('SELECT * FROM render_jobs')] if _table_exists(con, 'render_jobs') else []
    assets = [dict(r) for r in con.execute('SELECT * FROM render_assets')] if _table_exists(con, 'render_assets') else []
    qa = ([dict(r) for r in con.execute("SELECT * FROM qa_reports WHERE subject_kind='RENDER'")]
          if _table_exists(con, 'qa_reports') else [])
    if not jobs and not assets and not qa:
        return None
    db_row = con.execute('PRAGMA database_list').fetchone()
    db_path = Path(db_row[2]) if db_row and db_row[2] else (ROOT / 'data' / 'novel2moss.db')
    backup_dir = db_path.parent / 'backups'
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    target = backup_dir / f'render-export-{stamp}.json'
    payload = {
        'exported_at': datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        'database': str(db_path),
        'note': 'Renderer state removed by migration 005_db_boundary; this file is the external backup.',
        'render_jobs': jobs,
        'render_assets': assets,
        'render_qa_reports': qa,
    }
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Backed up render state before DB boundary migration: {target}')
    return target


def apply_migrations(con):
    # Existing DBs without the migrations table are supported.
    con.execute('CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT (datetime(\'now\')))')
    applied = {r[0] for r in con.execute('SELECT version FROM schema_migrations')}
    for file in sorted((ROOT / 'migrations').glob('*.sql')):
        version = file.stem
        if version in applied:
            continue
        if version == '005_db_boundary':
            _backup_render_state(con)
        con.executescript(file.read_text(encoding='utf-8'))
        if not con.execute('SELECT 1 FROM schema_migrations WHERE version=?', (version,)).fetchone():
            con.execute('INSERT INTO schema_migrations(version) VALUES (?)', (version,))
        con.commit()
        print(f'Applied migration: {version}')


def register_source(con, source_id, name, kind, homepage, license_label, license_url='', notes=''):
    con.execute('''INSERT INTO source_registry(id,name,kind,homepage_url,license_label,license_url,usage_notes)
      VALUES(?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET
      name=excluded.name,kind=excluded.kind,homepage_url=excluded.homepage_url,
      license_label=excluded.license_label,license_url=excluded.license_url,
      usage_notes=excluded.usage_notes''',
      (source_id, name, kind, homepage, license_label, license_url, notes))


SOURCES = [
    ('curated', 'Novel2Moss original curated examples', 'local', 'local://novel2moss', 'Original project data', '', 'Only self-authored sample metadata.'),
    ('deepghs', 'DeepGHS anime character index', 'dataset', 'https://huggingface.co/datasets/deepghs/character_index', 'MIT (dataset listing); character IP separately', 'https://huggingface.co/datasets/deepghs/character_index', 'Import names/core tags only; these are candidates, NOT verified original outfits. Check dataset and third-party rights.'),
    ('danbooru', 'Danbooru tag taxonomy API', 'api', 'https://danbooru.donmai.us/wiki_pages/api:tags', 'Check current site terms and individual content rights', 'https://danbooru.donmai.us/wiki_pages/help:api', 'Import tag metadata only; not images; rate-limit and use proper User-Agent for collecting.'),
    ('wikidata', 'Wikidata structured entities', 'api', 'https://www.wikidata.org/wiki/Wikidata:Data_access', 'CC0 for structured data', 'https://www.wikidata.org/wiki/Wikidata:Licensing', 'Prefer targeted SPARQL export, not bulk fuzzy search; verify identifiers.'),
    ('moss_official', 'OpenMOSS Natural Caption Prompt Guide', 'documentation', 'https://github.com/OpenMOSS/MOSS-Image/blob/main/USERGUIDE.md', 'Code repository rights may differ from generated images', '', 'Read official guidance for natural-language captions; this is documentation, not an imported dataset.'),
    ('posescript', 'PoseScript pose descriptions', 'dataset', 'https://github.com/naver/posescript', 'CC BY-NC-SA 4.0 dataset', 'https://github.com/naver/posescript/blob/main/LICENSE', 'Optional manual import only; non-commercial/SA and AMASS dependencies.'),
    ('dbr_e621_lists', 'Danbooru tag list archive (DraconicDragon; V2 uses Danbooru namespace)', 'dataset', 'https://github.com/DraconicDragon/dbr-e621-lists-archive', 'Repository license plus upstream Danbooru terms', 'https://github.com/DraconicDragon/dbr-e621-lists-archive/blob/main/LICENSE', 'V2 imports only selected Danbooru tags; no e621 or merged list.'),
    ('ai_pose_gallery', 'AI Pose Gallery metadata', 'dataset', 'https://github.com/anhao/ai-pose-gallery-zh', 'Code MIT; image/data rights may differ per asset', 'https://github.com/anhao/ai-pose-gallery-zh', 'Import JSON metadata only. Do not download or redistribute images before checking per-asset terms.'),
    ('charadb', 'CharaDB generic outfit metadata', 'dataset', 'https://github.com/taki-ttt/charadb', 'Check CharaDB terms; metadata and images can differ', 'https://github.com/taki-ttt/charadb', 'Generic outfit metadata only; never treat it as a canon outfit for a character.'),
]

VOCAB = {
  'POSE': [
    ('standing','standing upright','đứng thẳng','The person is standing upright.'),
    ('sitting','sitting on a chair','ngồi ghế','The person is sitting on a chair.'),
    ('kneeling','kneeling on the floor','quỳ','The person is kneeling on the floor.'),
    ('crouching','crouching low','ngồi xổm','The person is crouching low.'),
    ('leaning','leaning toward another person','nghiêng người','The person leans slightly toward another.'),
    ('reclining','reclining','ngả người','The person reclines with their back supported.'),
    ('walking','walking forward','đi bộ','The person walks forward.'),
    ('arms_crossed','arms crossed','khoanh tay','The person crosses both arms over the chest.'),
    ('looking_back','looking over the shoulder','ngoảnh đầu','The person looks over one shoulder.'),
  ],
  'ACTION': [
    ('head_pat','patting a head','xoa đầu','Actor gently pats the head of the target.'),
    ('handshake','shaking hands','bắt tay','Actor and target shake hands.'),
    ('pointing','pointing toward','chỉ tay','Actor points toward a target.'),
    ('handing_object','handing an object','đưa vật','Actor hands an object to the target.'),
    ('talking','speaking to','nói chuyện','Actor speaks to target.'),
    ('walking_together','walking together','cùng đi','Two people walk side by side.'),
    ('looking_at','looking at','nhìn','Actor looks toward the target.'),
    ('hugging','hugging','ôm','Two people embrace.'),
    ('reaching','reaching toward','vươn tay','Actor extends one arm toward a target.'),
  ],
  'EXPRESSION': [
    ('smile','gentle smile','mỉm cười','A gentle, visible smile.'),
    ('surprised','surprised expression','ngạc nhiên','Eyes widened with surprise.'),
    ('neutral','neutral expression','bình thản','Neutral relaxed facial expression.'),
    ('concerned','concerned expression','lo lắng','Brows slightly knitted in concern.'),
    ('laughing','laughing','cười lớn','Laughing with an open smile.'),
  ],
  'SPATIAL': [
    ('left_of','to the left of','bên trái','Place the actor to the left of the target.'),
    ('right_of','to the right of','bên phải','Place the actor to the right of the target.'),
    ('in_front_of','in front of','phía trước','Place the actor in front of the target.'),
    ('behind','behind','phía sau','Place the actor behind the target.'),
    ('facing','facing','đối diện','Make actor face the target.'),
    ('close_to','close to','ở gần','Place the two subjects close together.'),
    ('touching','touching','chạm','Allow physical contact between two subjects.'),
  ],
  'CAMERA': [
    ('wide_shot','wide shot','toàn cảnh','Wide shot showing full environment.'),
    ('medium_shot','medium shot','trung cảnh','Medium shot framing upper body or figures.'),
    ('close_up','close-up','cận cảnh','Close-up focusing on face or an object.'),
    ('over_shoulder','over-the-shoulder shot','qua vai','Camera over one participant shoulder.'),
    ('eye_level','eye-level angle','ngang mắt','Camera positioned at eye level.'),
    ('low_angle','low angle','góc thấp','Camera looks upward from a low angle.'),
  ],
  'LIGHTING': [
    ('soft_daylight','soft daylight','ánh sáng ban ngày','Soft natural daylight.'),
    ('golden_hour','golden hour','giờ vàng','Warm golden-hour sunlight.'),
    ('moonlight','moonlight','ánh trăng','Cool blue moonlight.'),
    ('studio_softbox','soft studio light','ánh sáng studio','Soft diffused studio illumination.'),
  ],
  'LOCATION': [
    ('sunlit_room','sunlit room','phòng có nắng','A sunlit room with a window.'),
    ('garden','garden','khu vườn','A green garden with plants.'),
    ('classroom','classroom','lớp học','An empty classroom interior.'),
    ('city_street','city street','đường phố','A city street.'),
  ],
  'STYLE': [
    ('anime_illustration','anime illustration','minh họa anime','Detailed anime illustration.'),
    ('painterly','painterly illustration','tranh vẽ','Painterly illustration with soft textures.'),
    ('photorealistic','photorealistic image','ảnh chân thực','Photorealistic image.'),
  ],
}

def seed(con):
    for s in SOURCES:
        register_source(con, *s)
    for category, rows in VOCAB.items():
        for code, en, vi, description in rows:
            con.execute('''INSERT OR IGNORE INTO vocabulary
                (id,category,code,label_en,label_vi,description_en,source_record_id)
                VALUES(?,?,?,?,?,?,NULL)''',
                (f'vocab:{category.lower()}:{code}',category,code,en,vi,description))
    con.commit()
    print(f'Seeded {sum(map(len, VOCAB.values()))} vocabulary items + {len(SOURCES)} source registrations (idempotent).')


def track_source_record(con, source_id, external_key, entity_kind, payload, run_id):
    body = js(payload)
    digest = sha(body)
    record_id = f'src:{source_id}:{sha(external_key)[:18]}'
    con.execute('''INSERT INTO source_records (id,source_id,external_key,entity_kind,content_sha256,payload_json,import_run_id)
                   VALUES (?,?,?,?,?,?,?) ON CONFLICT(source_id,external_key) DO UPDATE SET
                   content_sha256=excluded.content_sha256,payload_json=excluded.payload_json,
                   retrieved_at=datetime('now'),import_run_id=excluded.import_run_id''',
                (record_id,source_id,external_key,entity_kind,digest,body,run_id))
    con.execute('''INSERT OR IGNORE INTO source_record_versions(source_record_id,content_sha256,payload_json)
                VALUES (?,?,?)''', (record_id,digest,body))
    return record_id


def begin_import(con, source_id, details=None):
    run_id = uid('import')
    con.execute('INSERT INTO import_runs(id,source_id,status,details_json) VALUES (?,?,?,?)',
                (run_id, source_id, 'RUNNING', js(details or {})))
    # Persist the RUNNING row before the data transaction. A failed import then
    # remains visible with an error count instead of disappearing on rollback.
    con.commit()
    return run_id


def finish_import(con, run_id, imported, skipped=0, errors=0, details=None):
    if details is None:
        con.execute('''UPDATE import_runs SET status=?, imported_count=?, skipped_count=?, error_count=?,
                      finished_at=datetime('now') WHERE id=?''',
                    ('COMPLETE' if errors == 0 else 'FAILED', imported, skipped, errors, run_id))
    else:
        con.execute('''UPDATE import_runs SET status=?, imported_count=?, skipped_count=?, error_count=?,
                      details_json=?, finished_at=datetime('now') WHERE id=?''',
                    ('COMPLETE' if errors == 0 else 'FAILED', imported, skipped, errors,
                     js(details), run_id))
    con.commit()


def slugify(raw):
    value = re.sub(r'[^a-z0-9_]+','_',raw.lower().strip().replace(' ','_')).strip('_')
    return re.sub(r'_+','_',value) or 'unnamed'


def parse_deepghs(text):
    """Read the 'Character Index' Markdown table in a DeepGHS pages/<series>.md file.

    Output is source tag vocabulary, NOT verified identity/outfit information.
    """
    series = None
    within = False
    for line in text.splitlines():
        if line.startswith('# ') and series is None:
            series = line[2:].strip()
        if line.strip().lower() == '## character index':
            within = True
            continue
        if not within:
            continue
        if line.startswith('## '):
            break
        if not line.startswith('|'):
            continue
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        if len(cells) < 6:
            continue
        first = cells[0]
        if first.lower().startswith('character') or re.fullmatch(r':?-+:?',first.replace(' ','')):
            continue
        match = re.search(r'\[([^\]]+)\]\((https?://[^)]+)\)',first)
        if not match:
            continue
        char_tag = match.group(1).strip()
        if not char_tag:
            continue
        tags_cell = cells[-1]
        tags = [v.strip() for v in tags_cell.strip('`').split(',') if v.strip()]
        count = re.search(r'\d+', cells[-2])
        yield (series or 'unknown', char_tag, match.group(2), tags, int(count.group()) if count else None)


def import_deepghs(con, path: Path):
    seed(con)
    text = path.read_text(encoding='utf-8')
    file_sha = sha(path.read_bytes())
    run_id = begin_import(con, 'deepghs', {'file': path.name, 'sha256': file_sha,
                                           'parser': 'deepghs-character-index-v1'})
    imported = skipped = rows = 0
    try:
        for series, char_tag, url, tags, count in parse_deepghs(text):
            rows += 1
            series_slug = slugify(series)
            universe_id = f'universe:{series_slug}'
            con.execute('INSERT OR IGNORE INTO universes(id,slug,display_name) VALUES (?,?,?)',
                        (universe_id,series_slug,series.replace('_',' ')))
            unique_key = f'{series}/{char_tag}'
            source_record_id = track_source_record(con, 'deepghs', unique_key, 'character_index',
                         {'series':series,'tag':char_tag,'page_url':url,'core_tags':tags,
                          'post_count':count,'source_file_sha256':file_sha},run_id)
            char_id = f'character:deepghs:{sha(unique_key)[:18]}'
            char_slug = slugify(char_tag)
            was_existing = con.execute('SELECT 1 FROM characters WHERE id=?',(char_id,)).fetchone()
            # No inferred age/origin outfit, no overwriting the curated character profile.
            con.execute('''INSERT OR IGNORE INTO characters(id,universe_id,slug,display_name,age_status,identity_json)
              VALUES (?,?,?,?,?,?)''', (char_id,universe_id,char_slug,char_tag.replace('_',' '),'UNKNOWN','{}'))
            for tag in tags:
                # Resolve by (namespace,name): a tag may already have a hash-based id
                # from a CSV import, so do not assume the slug id was inserted.
                tag_id = f'tag:danbooru:{slugify(tag)}'
                con.execute('''INSERT INTO catalog_tags(id,namespace,name,original_name)
                  VALUES(?,?,?,?) ON CONFLICT(namespace,name) DO UPDATE SET
                  original_name=excluded.original_name''', (tag_id,'danbooru',tag,tag))
                actual = con.execute('SELECT id FROM catalog_tags WHERE namespace=? AND name=?',
                                     ('danbooru', tag)).fetchone()
                con.execute('''INSERT OR IGNORE INTO character_tags(character_id,tag_id,source_record_id,tag_role)
                  VALUES(?,?,?,?)''',(char_id,actual['id'],source_record_id,'CORE_CANDIDATE'))
            imported += int(not was_existing)
            skipped += int(bool(was_existing))
        finish_import(con,run_id,imported,skipped,details={
            'file': path.name, 'sha256': file_sha, 'rows_parsed': rows,
            'new_characters': imported, 'existing_characters': skipped,
            'note': 'core tags are CORE_CANDIDATE; no age/outfit inference'})
    except Exception as exc:
        con.rollback()
        finish_import(con, run_id, imported, skipped, errors=1,
                      details={'file': path.name, 'sha256': file_sha, 'error': str(exc)})
        raise
    return imported, skipped


def import_character_list(con, path: Path):
    """Import curated character slugs backed by Danbooru character-category rows.

    The JSON lists characters that a copyright page does not cover; every entry
    must already exist as category 4 in the tag archive, so the importer only
    records provenance, the tag and its aliases. No age/outfit inference, no
    identity merge with other universes.
    """
    seed(con)
    data = json.loads(path.read_text(encoding='utf-8'))
    universe_slug = slugify(data['universe'])
    universe_id = f'universe:{universe_slug}'
    run_id = begin_import(con, 'dbr_e621_lists', {'file': path.name,
                          'sha256': sha(path.read_bytes()),
                          'mode': 'character-list', 'universe': universe_slug})
    imported = skipped = rejected = 0
    try:
        con.execute('INSERT OR IGNORE INTO universes(id,slug,display_name) VALUES (?,?,?)',
                    (universe_id, universe_slug, data['universe'].replace('_', ' ')))
        for item in data['characters']:
            tag = item['name']
            if str(item.get('category')) != '4':
                rejected += 1
                continue
            record = track_source_record(con, 'dbr_e621_lists', f'{universe_slug}/{tag}',
                                         'character_tag', item, run_id)
            char_id = f'character:danbooru:{sha(universe_slug + "/" + tag)[:18]}'
            exists = con.execute('SELECT 1 FROM characters WHERE id=?', (char_id,)).fetchone()
            con.execute('''INSERT OR IGNORE INTO characters
                (id,universe_id,slug,display_name,identity_json)
                VALUES (?,?,?,?,?)''',
                (char_id, universe_id, tag, tag.replace('_', ' '),
                 js({'source_record_id': record, 'danbooru_tag': tag,
                     'post_count': item.get('post_count')})))
            con.execute('''INSERT INTO catalog_tags(id,namespace,name,original_name,category,post_count)
                VALUES (?,?,?,?,?,?) ON CONFLICT(namespace,name) DO UPDATE SET
                category=excluded.category, post_count=excluded.post_count''',
                (f'tag:danbooru:{tag}', 'danbooru', tag, tag, 4, item.get('post_count')))
            for alias in item.get('aliases') or []:
                con.execute('''INSERT INTO catalog_tag_relations
                    (namespace,antecedent,consequent,relation_type,status,source_record_id)
                    VALUES ('danbooru',?,?,'ALIAS','archive_unspecified',?)
                    ON CONFLICT(namespace,antecedent,consequent,relation_type) DO NOTHING''',
                    (alias, tag, record))
            imported += int(not exists)
            skipped += int(bool(exists))
        finish_import(con, run_id, imported, skipped, details={
            'file': path.name, 'universe': universe_slug,
            'new_characters': imported, 'existing_characters': skipped,
            'rejected_non_character_category': rejected,
            'note': 'identity UNVERIFIED; tags from Danbooru category 4 rows only'})
    except Exception as exc:
        con.rollback()
        finish_import(con, run_id, imported, skipped, errors=1,
                      details={'file': path.name, 'error': str(exc)})
        raise
    return imported, skipped


def import_danbooru_tags(con, path: Path):
    seed(con)
    data = json.loads(path.read_text(encoding='utf-8'))
    tags = data if isinstance(data,list) else data.get('tags', data.get('data',[]))
    if not isinstance(tags,list):
        raise ValueError('JSON must be an array or {"tags":[...]}')
    run_id = begin_import(con,'danbooru')
    imported=skipped=0
    for tag in tags:
        name = tag.get('name')
        if not name:
            skipped+=1
            continue
        cat = tag.get('category')
        if cat is not None and cat not in (0,1,3,4,5):
            skipped+=1
            continue
        key = str(tag.get('id') or name)
        rec_id = track_source_record(con,'danbooru',f'tag/{key}','tag',tag,run_id)
        tag_id = f'tag:danbooru:{slugify(name)}'
        existing = con.execute('SELECT 1 FROM catalog_tags WHERE id=?',(tag_id,)).fetchone()
        con.execute('''INSERT INTO catalog_tags
              (id,namespace,name,original_name,category,post_count,deprecated,source_record_id)
              VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(namespace,name) DO UPDATE SET
              original_name=excluded.original_name, category=excluded.category,
              post_count=excluded.post_count,deprecated=excluded.deprecated,
              source_record_id=excluded.source_record_id''',
              (tag_id,'danbooru',name,name,cat,tag.get('post_count'),int(bool(tag.get('is_deprecated',False))),rec_id))
        imported += int(not existing)
        skipped += int(bool(existing))
    finish_import(con,run_id,imported,skipped)
    return imported,skipped


def wikidata_value(binding, field):
    v = binding.get(field)
    return (v.get('value') if isinstance(v,dict) else v) or None


def import_wikidata(con,path):
    seed(con)
    payload = json.loads(path.read_text(encoding='utf-8'))
    bindings = payload.get('results',{}).get('bindings',[])
    run_id = begin_import(con,'wikidata')
    imported=skipped=0
    for b in bindings:
        url = wikidata_value(b,'item') or wikidata_value(b,'character')
        label = wikidata_value(b,'itemLabel') or wikidata_value(b,'characterLabel')
        if not url or not label:
            skipped+=1
            continue
        qid = url.rsplit('/',1)[-1]
        if not re.fullmatch(r'Q\d+',qid):
            skipped+=1
            continue
        rec_id = track_source_record(con,'wikidata',qid,'fictional_character',b,run_id)
        # Do not auto-merge with a third-party catalog by name: identity collision risk.
        universe=None
        work_url = wikidata_value(b,'work')
        work_name = wikidata_value(b,'workLabel')
        if work_url and work_name:
            wq = work_url.rsplit('/',1)[-1]
            if re.fullmatch(r'Q\d+',wq):
                universe=f'universe:wikidata:{wq}'
                con.execute('INSERT OR IGNORE INTO universes(id,slug,display_name) VALUES(?,?,?)',
                  (universe,f'wd_{wq.lower()}',work_name))
        char_id=f'character:wikidata:{qid}'
        existing=con.execute('SELECT 1 FROM characters WHERE id=?',(char_id,)).fetchone()
        con.execute('''INSERT OR IGNORE INTO characters(id,universe_id,slug,display_name,identity_json)
          VALUES(?,?,?,?,?)''', (char_id,universe,qid.lower(),label,js({'wikidata_id':qid,'source_record_id':rec_id})))
        imported += int(not existing)
        skipped += int(bool(existing))
    finish_import(con,run_id,imported,skipped)
    return imported,skipped


def create_story(con,title,mode,raw_text,labels):
    story_id=uid('story')
    source_id=uid('source')
    con.execute('INSERT INTO stories(id,title,cast_mode) VALUES(?,?,?)',(story_id,title,mode))
    con.execute('''INSERT INTO story_sources(id,story_id,source_kind,raw_text,raw_labels_json,content_sha256)
       VALUES(?,?,?,?,?,?)''',
       (source_id,story_id,'user_input',raw_text,js(labels),sha(raw_text)))
    con.commit()
    return story_id


def add_role(con,story_id,role_key,description=''):
    if not con.execute('SELECT 1 FROM stories WHERE id=?',(story_id,)).fetchone():
        raise ValueError('Story not found')
    existing = con.execute('SELECT id,role_description FROM story_roles WHERE story_id=? AND role_key=?',
                           (story_id,role_key)).fetchone()
    if existing:
        if (existing['role_description'] or '') != (description or ''):
            raise ValueError('Role already exists with different description; review before updating')
        return existing['id']
    role_id=uid('role')
    with con:
        con.execute('INSERT INTO story_roles(id,story_id,role_key,role_description) VALUES(?,?,?,?)',
                    (role_id,story_id,role_key,description))
    return role_id


def bind_role(con,story_id,role_key,character_id,outfit_id=None):
    row=con.execute('''SELECT r.id, s.current_revision FROM story_roles r
       JOIN stories s ON s.id=r.story_id WHERE r.story_id=? AND r.role_key=?''',(story_id,role_key)).fetchone()
    if row is None:
        raise ValueError(f'Role {role_key} not found in story')
    if not con.execute('SELECT 1 FROM characters WHERE id=?',(character_id,)).fetchone():
        raise ValueError(f'Character {character_id} not found')
    if outfit_id:
        outfit=con.execute('SELECT character_id FROM outfits WHERE id=?',(outfit_id,)).fetchone()
        if outfit is None or outfit[0] not in (None,character_id):
            raise ValueError('Outfit does not belong to character or does not exist')
    # Same binding is idempotent: do not create a new revision when nothing changed.
    current = con.execute('''SELECT character_id,outfit_id FROM story_castings
                       WHERE story_role_id=? AND until_revision IS NULL''',(row['id'],)).fetchone()
    if current and current['character_id'] == character_id and current['outfit_id'] == outfit_id:
        return row['current_revision']
    # Casting revision advances the shared Story revision counter.
    newrev=row['current_revision']+1
    with con:
        con.execute('UPDATE story_castings SET until_revision=? WHERE story_role_id=? AND until_revision IS NULL',
                    (newrev-1,row['id']))
        con.execute('''INSERT INTO story_castings(id,story_role_id,character_id,outfit_id,from_revision)
         VALUES(?,?,?,?,?)''',(uid('casting'),row['id'],character_id,outfit_id,newrev))
        con.execute('UPDATE stories SET current_revision=?,updated_at=datetime(\'now\') WHERE id=?',
                    (newrev,story_id))
    return newrev


ANIMA_SAFETY_TAGS = ('safe', 'sensitive', 'nsfw', 'explicit')


def validate_natural_prompt(prompt: str, language: str = 'en') -> str:
    """Validate the Anima prompt block; structural checks only.

    Full grammar validation (framing/angle/camera conflicts, quality tags, token
    budget) lives in tools/novel2moss/validate_anima_prompt.py, which the renderer
    side runs; this keeps one source of truth for the byte-level export gate.
    """
    if not isinstance(prompt, str):
        raise ValueError('Anima prompt must be UTF-8 text')
    if language not in ('en', 'vi', 'zh'):
        raise ValueError('Unsupported prompt language (en/vi/zh)')
    text = prompt.replace('\r\n', '\n').replace('\r', '\n').strip()
    if not text:
        raise ValueError('Anima prompt must not be empty')
    if text.startswith('```') or text.endswith('```'):
        raise ValueError('Anima prompt must not be a fenced code block')
    if text.startswith('{'):
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            pass
        else:
            if isinstance(payload, dict):
                raise ValueError('Positive prompt must be a tag block, not a JSON object')
    if '\x00' in text:
        raise ValueError('Anima prompt contains a NUL character')
    tag_line = text.splitlines()[0]
    if ',' not in tag_line:
        raise ValueError('Anima prompt line 1 must be a comma-separated tag block')
    if not any(t.strip() in ANIMA_SAFETY_TAGS for t in tag_line.lower().split(',')):
        raise ValueError('Anima prompt tag block must start with a safety tag '
                         '(safe/sensitive/nsfw/explicit)')
    return text


def save_natural_prompt(con, shot_id: str, prompt_text: str, language: str = 'en'):
    text = validate_natural_prompt(prompt_text, language)
    with con:
        shot = con.execute('SELECT shot_spec_json FROM shots WHERE id=?', (shot_id,)).fetchone()
        if shot is None:
            raise ValueError(f'Shot not found: {shot_id}')
        spec_hash = sha(shot['shot_spec_json'])
        previous = con.execute('''SELECT * FROM shot_prompts WHERE shot_id=?
                                  ORDER BY revision DESC LIMIT 1''', (shot_id,)).fetchone()
        if previous and previous['prompt_text'] == text and previous['language'] == language:
            return previous['id'], previous['revision']
        revision = previous['revision'] + 1 if previous else 1
        prompt_id = uid('prompt')
        con.execute('''INSERT INTO shot_prompts(id,shot_id,revision,language,prompt_text,
                         prompt_sha256,shot_spec_sha256,supersedes_prompt_id)
                         VALUES(?,?,?,?,?,?,?,?)''',
                    (prompt_id,shot_id,revision,language,text,sha(text),spec_hash,
                     previous['id'] if previous else None))
    return prompt_id, revision


def _prompt_bundle_data(con, prompt_id: str):
    prompt = con.execute('''SELECT p.*,s.shot_key,s.revision AS shot_revision,s.shot_spec_json,
                          s.beat_id,b.beat_order,a.id AS act_id,a.act_order,a.story_id
                          FROM shot_prompts p JOIN shots s ON s.id=p.shot_id
                          JOIN beats b ON b.id=s.beat_id JOIN acts a ON a.id=b.act_id
                          WHERE p.id=?''', (prompt_id,)).fetchone()
    if prompt is None:
        raise ValueError(f'Natural prompt not found: {prompt_id}')
    if sha(prompt['shot_spec_json']) != prompt['shot_spec_sha256']:
        raise ValueError('Prompt source ShotSpec checksum mismatch')
    if sha(prompt['prompt_text']) != prompt['prompt_sha256']:
        raise ValueError('Natural prompt checksum mismatch')
    qa = con.execute('''SELECT verdict,policy_ref,report_json,created_at FROM qa_reports
                        WHERE subject_kind='PROMPT' AND subject_id=?
                        ORDER BY rowid DESC LIMIT 1''', (prompt_id,)).fetchone()
    return prompt, qa


def export_bundle(con, prompt_id: str, out_dir: Path, qa_id=None):
    """Export natural text and traceability sidecars, no renderer dependency."""
    prompt, qa = _prompt_bundle_data(con, prompt_id)
    if qa and qa['verdict'] == 'BLOCKED':
        raise ValueError('Blocked QA for natural prompt; export refused')
    if json.loads(prompt['shot_spec_json']).get('visual_context_sha256'):
        from n2m_storyboard import latest_qa, require_prompt_qa
        require_prompt_qa(latest_qa(con,prompt_id),prompt['shot_id'])
    if qa_id:
        qa = con.execute('''SELECT * FROM qa_reports WHERE id=? AND subject_kind='PROMPT'
                            AND subject_id=? AND verdict='PASS' ''',(qa_id,prompt_id)).fetchone()
        if qa is None:
            raise ValueError('Pinned prompt QA not found')
    out_dir = out_dir.expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    text_path = out_dir / 'natural.prompt.txt'
    manifest_path = out_dir / 'prompt.manifest.json'
    qa_path = out_dir / 'fidelity_report.json'
    text_path.write_text(prompt['prompt_text'], encoding='utf-8', newline='')
    manifest = {
        'format': 'anima-tag-v1',
        'prompt_id': prompt_id, 'story_id': prompt['story_id'],
        'shot_id': prompt['shot_id'], 'shot_key': prompt['shot_key'],
        'shot_revision': prompt['shot_revision'], 'prompt_revision': prompt['revision'],
        'language': prompt['language'], 'shot_spec_sha256': prompt['shot_spec_sha256'],
        'prompt_sha256': prompt['prompt_sha256'], 'prompt_file': 'natural.prompt.txt',
        'fidelity_report_file': 'fidelity_report.json',
        'exported_at': datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    if qa:
        fidelity = {'subject_kind': 'PROMPT', 'subject_id': prompt_id,
                    'verdict': qa['verdict'], 'policy_ref': qa['policy_ref'],
                    'report': json.loads(qa['report_json']), 'created_at': qa['created_at']}
        if qa_id:
            fidelity['qa_id'] = qa_id
    else:
        fidelity = {'subject_kind': 'PROMPT', 'subject_id': prompt_id,
                    'verdict': 'SKIP', 'reason': 'No pre-export natural prompt QA recorded'}
    qa_path.write_text(json.dumps(fidelity, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return {'out_dir': str(out_dir), 'prompt': str(text_path), 'manifest': str(manifest_path),
            'fidelity_report': str(qa_path), 'prompt_sha256': prompt['prompt_sha256']}


def export_story_prompts(con, story_id: str, out_dir: Path, storyboard_id=None):
    """Export latest Shot revisions, one natural prompt per Shot, grouped by Act.

    All prompts must exist before writing: no silently truncated Story export.
    """
    if not con.execute('SELECT 1 FROM stories WHERE id=?', (story_id,)).fetchone():
        raise ValueError(f'Story not found: {story_id}')
    from n2m_storyboard import sealed_selection
    selection = sealed_selection(con,story_id,storyboard_id)
    if selection:
        storyboard_id, bindings = selection
        shots = [con.execute('''SELECT s.*,a.id AS act_id,a.act_order,b.beat_order
            FROM shots s JOIN beats b ON b.id=s.beat_id JOIN acts a ON a.id=b.act_id
            WHERE s.id=? AND a.story_id=?''',(b['shot_id'],story_id)).fetchone() for b in bindings]
    else:
        bindings = None
        shots = con.execute('''SELECT s.*,a.id AS act_id,a.act_order,b.beat_order
        FROM shots s JOIN beats b ON b.id=s.beat_id JOIN acts a ON a.id=b.act_id
        WHERE a.story_id=? AND s.revision=(SELECT max(x.revision) FROM shots x
                 WHERE x.beat_id=s.beat_id AND x.shot_key=s.shot_key)
        ORDER BY a.act_order,b.beat_order,s.shot_key''', (story_id,)).fetchall()
    if not shots:
        raise ValueError('Story has no Shots to export')
    planned = []
    for index,shot in enumerate(shots):
        p = ({'id':bindings[index]['prompt_id']} if bindings else
             con.execute('SELECT id FROM shot_prompts WHERE shot_id=? ORDER BY revision DESC LIMIT 1',
                         (shot['id'],)).fetchone())
        if not p:
            raise ValueError(f'Missing natural prompt for current Shot {shot["shot_key"]} ({shot["id"]})')
        prompt, qa = _prompt_bundle_data(con, p['id'])
        if qa and qa['verdict'] == 'BLOCKED':
            raise ValueError(f'Blocked QA for current Shot {shot["shot_key"]}')
        planned.append((shot, prompt))
    out_dir = out_dir.expanduser().resolve()
    acts = {}
    all_lines = []
    for index,(shot, prompt) in enumerate(planned):
        act_key = f'A{shot["act_order"]:02d}'
        shot_dir = out_dir / 'bundles' / act_key / f'B{shot["beat_order"]:02d}' / shot['id'] / str(prompt['revision'])
        export_bundle(con, prompt['id'], shot_dir, bindings[index]['qa_id'] if bindings else None)
        shot_spec = json.loads(shot['shot_spec_json'])
        row = {'shot_key': shot['shot_key'], 'page': shot_spec.get('page'),
               'act': act_key, 'beat': shot['beat_order'],
               'camera': shot_spec.get('camera'), 'focus': shot_spec.get('focus'),
               'bundle_dir': str(shot_dir.relative_to(out_dir)).replace('\\','/'),
               'prompt_sha256': prompt['prompt_sha256'], 'prompt': prompt['prompt_text']}
        if bindings:
            row.update({k: bindings[index][k] for k in ('shot_order','branch_key','purpose','qa_id','continuity_sha256')})
            row['storyboard_id'] = storyboard_id
        line = json.dumps(row, ensure_ascii=False, separators=(',', ':'))
        all_lines.append(line)
        acts.setdefault(act_key, []).append(line)
    def write_lines(path: Path, lines):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('\n\n'.join(lines) + '\n', encoding='utf-8', newline='')
    write_lines(out_dir / 'prompts.all.jsonl', all_lines)
    for name, lines in acts.items():
        write_lines(out_dir / 'prompts' / f'{name}.jsonl', lines)
    return {'story_id': story_id, 'storyboard_id': storyboard_id, 'shots': len(planned), 'acts': len(acts),
            'output': str(out_dir / 'prompts.all.jsonl')}


def stats(con):
    names=['source_registry','source_records','source_record_versions','import_runs','universes','characters',
           'character_traits','outfits','outfit_parts','catalog_tags','character_tags',
           'catalog_assets','catalog_tag_relations','catalog_tag_taxonomy','catalog_entity_links',
           'catalog_captions','pose_references','pose_reference_views','layout_templates',
           'stories','story_roles','story_castings','acts','beats','story_events','shots',
           'shot_layouts','layout_exports','shot_prompts','qa_reports',
           'storyboards','storyboard_shots','story_locations','story_props','visual_style_profiles',
           'event_shot_mappings','shot_dependencies','storyboard_seals']
    return {name:con.execute(f'SELECT count(*) FROM {name}').fetchone()[0] for name in names}


def stats_detailed(con):
    """Counts by namespace/kind plus the flat table counts used by earlier versions."""
    result = {'tables': stats(con)}
    result['tags_by_namespace'] = {
        row['namespace']: row['n'] for row in con.execute(
            'SELECT namespace,count(*) AS n FROM catalog_tags GROUP BY namespace ORDER BY namespace')}
    result['outfits_by_kind'] = {
        row['outfit_kind']: row['n'] for row in con.execute(
            'SELECT outfit_kind,count(*) AS n FROM outfits GROUP BY outfit_kind ORDER BY outfit_kind')}
    result['poses_by_source'] = {
        row['source_id']: row['n'] for row in con.execute(
            '''SELECT s.source_id,count(*) AS n FROM pose_references p
               JOIN source_records s ON s.id=p.source_record_id
               GROUP BY s.source_id ORDER BY s.source_id''')}
    result['assets_by_role'] = {
        row['asset_role']: row['n'] for row in con.execute(
            'SELECT asset_role,count(*) AS n FROM catalog_assets GROUP BY asset_role ORDER BY asset_role')}
    result['import_runs'] = [
        {'source_id': row['source_id'], 'status': row['status'],
         'imported': row['imported_count'], 'skipped': row['skipped_count'],
         'errors': row['error_count'], 'started_at': row['started_at']}
        for row in con.execute('''SELECT source_id,status,imported_count,skipped_count,error_count,started_at
                                  FROM import_runs ORDER BY started_at DESC LIMIT 15''')]
    return result


def search_catalog(con, kind, query, limit=20, namespace=None):
    """Simple, explicit LIKE search across catalog entities. No fuzzy auto-merge."""
    query = (query or '').strip()
    if not query:
        raise ValueError('Search query must not be empty')
    like = f'%{query}%'
    if kind == 'tag':
        sql = 'SELECT id,namespace,name,original_name,category,post_count FROM catalog_tags WHERE name LIKE ?'
        params = [like]
        if namespace:
            sql += ' AND namespace=?'
            params.append(namespace)
        sql += ' ORDER BY post_count DESC, name LIMIT ?'
        params.append(limit)
    elif kind == 'character':
        sql = '''SELECT c.id,c.display_name,c.slug,c.identity_review,
                        u.slug AS universe_slug,u.display_name AS universe
                 FROM characters c LEFT JOIN universes u ON u.id=c.universe_id
                 WHERE c.display_name LIKE ? OR c.slug LIKE ?
                 ORDER BY c.display_name LIMIT ?'''
        params = [like, like, limit]
    elif kind == 'universe':
        sql = '''SELECT id,slug,display_name FROM universes
                 WHERE display_name LIKE ? OR slug LIKE ? ORDER BY display_name LIMIT ?'''
        params = [like, like, limit]
    elif kind == 'pose':
        sql = '''SELECT p.id,p.caption_en,p.category,p.pose_code,p.source_url,
                        (SELECT v.view_name FROM pose_reference_views v
                         WHERE v.pose_reference_id=p.id LIMIT 1) AS view_name
                 FROM pose_references p
                 WHERE p.caption_en LIKE ? OR p.category LIKE ? OR p.pose_code LIKE ?
                 ORDER BY p.id LIMIT ?'''
        params = [like, like, like, limit]
    elif kind == 'outfit':
        sql = '''SELECT DISTINCT o.id,o.name,o.slug,o.outfit_kind,o.verification,o.character_id
                 FROM outfits o
                 LEFT JOIN catalog_captions c
                   ON c.entity_kind='outfit' AND c.entity_id=o.id
                 WHERE o.name LIKE ? OR o.slug LIKE ? OR c.text LIKE ?
                 ORDER BY o.name LIMIT ?'''
        params = [like, like, like, limit]
    elif kind == 'action':
        sql = '''SELECT id,category,code,label_en,label_vi,description_en,review
                 FROM vocabulary WHERE category='ACTION'
                   AND (code LIKE ? OR label_en LIKE ? OR description_en LIKE ?)
                 ORDER BY code LIMIT ?'''
        params = [like, like, like, limit]
    else:
        raise ValueError('kind must be one of: tag, character, universe, pose, outfit, action')
    return [dict(row) for row in con.execute(sql, params)]


def main():
    p=argparse.ArgumentParser(description='Novel2Moss DB - local-only, standard library SQLite starter')
    p.add_argument('--db',type=Path,default=DEFAULT_DB,help='SQLite path (default: data/novel2moss.db)')
    sub=p.add_subparsers(dest='action',required=True)
    for action in ('init','seed'):
        sub.add_parser(action)
    a=sub.add_parser('stats');a.add_argument('--detailed',action='store_true')
    a=sub.add_parser('import-deepghs-md');a.add_argument('file',type=Path)
    a=sub.add_parser('import-character-list-json');a.add_argument('file',type=Path)
    a=sub.add_parser('import-danbooru-json');a.add_argument('file',type=Path)
    a=sub.add_parser('import-wikidata-json');a.add_argument('file',type=Path)
    a=sub.add_parser('import-tags-csv');a.add_argument('file',type=Path);a.add_argument('--namespace',required=True,choices=('danbooru','e621'));a.add_argument('--limit',type=int);a.add_argument('--no-aliases',action='store_true');a.add_argument('--source-revision');a.add_argument('--dry-run',action='store_true');a.add_argument('--from-character-core-tags',action='store_true')
    a=sub.add_parser('import-tag-relations-json');a.add_argument('file',type=Path);a.add_argument('--namespace',required=True,choices=('danbooru','e621'));a.add_argument('--kind',required=True,choices=('alias','implication'));a.add_argument('--source-revision');a.add_argument('--dry-run',action='store_true')
    a=sub.add_parser('import-pose-gallery-json');a.add_argument('file',type=Path);a.add_argument('--limit',type=int);a.add_argument('--source-revision');a.add_argument('--dry-run',action='store_true')
    a=sub.add_parser('import-costume-gallery-json');a.add_argument('file',type=Path);a.add_argument('--source-id',default='ai_pose_gallery',choices=('ai_pose_gallery','charadb'));a.add_argument('--limit',type=int);a.add_argument('--source-revision');a.add_argument('--dry-run',action='store_true')
    a=sub.add_parser('create-story');a.add_argument('--title',required=True);a.add_argument('--mode',choices=('BLIND','NON_BLIND'),required=True);a.add_argument('--text-file',type=Path,required=True);a.add_argument('--label',action='append',default=[])
    a=sub.add_parser('add-role');a.add_argument('--story-id',required=True);a.add_argument('--key',required=True);a.add_argument('--description',default='')
    a=sub.add_parser('bind-role');a.add_argument('--story-id',required=True);a.add_argument('--key',required=True);a.add_argument('--character-id',required=True);a.add_argument('--outfit-id')
    a=sub.add_parser('export-bundle');a.add_argument('--prompt-id',required=True);a.add_argument('--out-dir',type=Path,required=True)
    a=sub.add_parser('export-story-prompts');a.add_argument('--story-id',required=True);a.add_argument('--out-dir',type=Path,required=True);a.add_argument('--storyboard-id')
    a=sub.add_parser('search-characters');a.add_argument('query');a.add_argument('--limit',type=int,default=10)
    a=sub.add_parser('search-catalog');a.add_argument('kind',choices=('tag','character','universe','pose','outfit','action'));a.add_argument('query');a.add_argument('--namespace',choices=('danbooru','e621'));a.add_argument('--limit',type=int,default=20)
    args=p.parse_args()
    con=connect(args.db)
    try:
        apply_migrations(con)
        if args.action=='init':print(f'Database initialized: {args.db}')
        elif args.action=='seed': seed(con)
        elif args.action=='stats':
            print(json.dumps(stats_detailed(con) if args.detailed else stats(con),indent=2,ensure_ascii=False))
        elif args.action=='import-deepghs-md': print('New, existing:',*import_deepghs(con,args.file))
        elif args.action=='import-character-list-json': print('New, existing:',*import_character_list(con,args.file))
        elif args.action=='import-danbooru-json': print('New, existing/skipped:',*import_danbooru_tags(con,args.file))
        elif args.action=='import-wikidata-json': print('New, existing/skipped:',*import_wikidata(con,args.file))
        elif args.action=='import-tags-csv':
            from catalog_imports import import_tags_csv
            result=import_tags_csv(con,args.file,args.namespace,limit=args.limit,
                                   with_aliases=not args.no_aliases,
                                   source_revision=args.source_revision,dry_run=args.dry_run,
                                   from_character_core_tags=args.from_character_core_tags)
            print(json.dumps(result,indent=2,ensure_ascii=False))
        elif args.action=='import-tag-relations-json':
            from catalog_imports import import_tag_relations_json
            result=import_tag_relations_json(con,args.file,args.namespace,args.kind,
                                             source_revision=args.source_revision,dry_run=args.dry_run)
            print(json.dumps(result,indent=2,ensure_ascii=False))
        elif args.action=='import-pose-gallery-json':
            from catalog_imports import import_pose_gallery
            result=import_pose_gallery(con,args.file,limit=args.limit,
                                       source_revision=args.source_revision,dry_run=args.dry_run)
            print(json.dumps(result,indent=2,ensure_ascii=False))
        elif args.action=='import-costume-gallery-json':
            from catalog_imports import import_generic_outfits
            result=import_generic_outfits(con,args.file,source_id=args.source_id,limit=args.limit,
                                          source_revision=args.source_revision,dry_run=args.dry_run)
            print(json.dumps(result,indent=2,ensure_ascii=False))
        elif args.action=='search-catalog':
            print(json.dumps(search_catalog(con,args.kind,args.query,args.limit,args.namespace),
                             indent=2,ensure_ascii=False))
        elif args.action=='create-story':
            print(create_story(con,args.title,args.mode,args.text_file.read_text(encoding='utf-8'),args.label))
        elif args.action=='add-role':print(add_role(con,args.story_id,args.key,args.description))
        elif args.action=='bind-role':print('New story revision:',bind_role(con,args.story_id,args.key,args.character_id,args.outfit_id))
        elif args.action=='export-bundle':
            print(json.dumps(export_bundle(con,args.prompt_id,args.out_dir),
                             indent=2,ensure_ascii=False))
        elif args.action=='export-story-prompts':
            print(json.dumps(export_story_prompts(con,args.story_id,args.out_dir,args.storyboard_id),
                             indent=2,ensure_ascii=False))
        elif args.action=='search-characters':
            for row in con.execute('''SELECT c.id,c.display_name,c.slug,u.display_name AS universe
              FROM character_search f JOIN characters c ON c.rowid=f.rowid
              LEFT JOIN universes u ON u.id=c.universe_id
              WHERE character_search MATCH ? LIMIT ?''',(args.query,args.limit)):
                print(dict(row))
    finally:
        con.close()


if __name__=='__main__':
    try:main()
    except (ValueError,sqlite3.Error,FileNotFoundError) as exc:
        print(f'ERROR: {exc}',file=sys.stderr)
        sys.exit(1)
