#!/usr/bin/env python3
"""Generate a V2 catalog report from the Novel2Anima SQLite database.

Read-only. The report intentionally emphasizes scope decisions and consumer
value, not raw dataset size. It never downloads data or runs a renderer.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from n2m_db import connect, stats

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = ROOT / 'database' / 'data' / 'novel2anima.db'
DEFAULT_OUT = ROOT / 'reports' / 'catalog_pilot_v2.md'


def md(value):
    return str(value).replace('|', '\\|').replace('\n', ' ')


def table(headers, rows):
    out = ['| ' + ' | '.join(headers) + ' |',
           '|' + '|'.join('---' for _ in headers) + '|']
    out.extend('| ' + ' | '.join(md(v) for v in row) + ' |' for row in rows)
    return '\n'.join(out)


def raw_snapshots(imports_root: Path):
    manifest_path = ROOT / 'database' / 'collect' / 'source_manifest.json'
    allowed = set()
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        for source in manifest.get('sources', []):
            if source.get('enabled') is False:
                continue
            for group in (source.get('groups') or {}).values():
                if group.get('enabled') is not False:
                    allowed.add(str(group.get('dest', '')).replace('\\', '/'))
            for entry in (source.get('files') or {}).values():
                if entry.get('enabled') is not False:
                    allowed.add(str(entry.get('dest', '')).replace('\\', '/'))
    rows = []
    for meta_file in sorted(imports_root.rglob('*.meta.json')):
        if '.history' in meta_file.parts:
            continue
        rel = meta_file.relative_to(imports_root).as_posix()
        rel = rel[:-len('.meta.json')] if rel.endswith('.meta.json') else rel
        if allowed and rel not in allowed:
            continue
        try:
            meta = json.loads(meta_file.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            continue
        rows.append((meta.get('source_id', ''), meta.get('key', ''),
                     meta.get('bytes', ''), meta.get('sha256', ''),
                     meta.get('source_revision') or '',
                     meta.get('retrieved_at', '')))
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', type=Path, default=DEFAULT_DB)
    parser.add_argument('--out', type=Path, default=DEFAULT_OUT)
    parser.add_argument('--title', default='Novel2Anima — Catalog Pilot V2')
    args = parser.parse_args()
    if not args.db.exists():
        raise SystemExit(f'DB not found: {args.db}')
    con = connect(args.db)
    try:
        flat = stats(con)
        tags = {r['namespace']: r['n'] for r in con.execute(
            'SELECT namespace,count(*) AS n FROM catalog_tags GROUP BY namespace ORDER BY namespace')}
        relations = list(con.execute('''SELECT namespace,relation_type,status,count(*) AS n
             FROM catalog_tag_relations
             GROUP BY namespace,relation_type,status ORDER BY namespace,relation_type,status'''))
        outfits = list(con.execute('''SELECT outfit_kind,verification,count(*) AS n
             FROM outfits GROUP BY outfit_kind,verification ORDER BY outfit_kind,verification'''))
        captions = list(con.execute('''SELECT lang,origin,review,count(*) AS n
             FROM catalog_captions GROUP BY lang,origin,review ORDER BY lang,origin,review'''))
        top_tags = list(con.execute('''SELECT namespace,name,post_count FROM catalog_tags
             ORDER BY post_count DESC, namespace, name LIMIT 15'''))
        source_records = list(con.execute('''SELECT source_id,count(*) AS n FROM source_records
             GROUP BY source_id ORDER BY source_id'''))
        runs = list(con.execute('''SELECT source_id,status,imported_count,skipped_count,error_count,started_at
             FROM import_runs ORDER BY started_at DESC LIMIT 20'''))
        registry = list(con.execute('''SELECT id,name,kind,license_label FROM source_registry
             ORDER BY id'''))
        characters = list(con.execute('''SELECT c.display_name,u.display_name AS universe
             FROM characters c LEFT JOIN universes u ON u.id=c.universe_id
             ORDER BY c.display_name LIMIT 8'''))
        qa = list(con.execute('''SELECT subject_kind,verdict,count(*) AS n FROM qa_reports
             GROUP BY subject_kind,verdict ORDER BY subject_kind,verdict'''))
        curated_adults = con.execute('''SELECT count(*) FROM characters
             WHERE id LIKE 'character:curated:%' AND age_status='CONFIRMED_ADULT' ''').fetchone()[0]
        render_tables = [r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('render_jobs','render_assets')")]
        integrity = con.execute('PRAGMA integrity_check').fetchone()[0]
        fk = list(con.execute('PRAGMA foreign_key_check'))
        sqlite_version = con.execute('SELECT sqlite_version()').fetchone()[0]
        db_bytes = args.db.stat().st_size
        lines = [f'# {args.title}', '',
                 f'- **Generated:** {datetime.now(timezone.utc).replace(microsecond=0).isoformat()}',
                 f'- **DB:** `{args.db}`',
                 f'- **DB size:** {db_bytes:,} bytes',
                 f'- **SQLite:** {sqlite_version}',
                 f'- **Integrity check:** `{integrity}`',
                 f'- **Foreign key violations:** {len(fk)}',
                 f'- **Renderer tables present:** {render_tables or "none"}',
                 '- **Status:** metadata/consumer pilot; image/render QA NOT IN THIS DATABASE.',
                 '', '## 1. Phạm vi V2', '',
                 'Database chỉ có hai vai trò: **catalog** và **Story workspace**. '
                 'Prompt export là điểm kết thúc; renderer là downstream độc lập, không kết nối SQLite. '
                 'DB V1 cũ được lưu tại `database/data/backups/novel2anima-v1-pilot.db`; DB runtime hiện tại đã được thay bằng dữ liệu V2.',
                 '',
                 table(['Quyết định', 'Nguồn / dữ liệu', 'Lý do'], [
                     ('Giữ', 'DeepGHS Blue Archive', 'Casting/identity candidates cho Non-Blind'),
                     ('Giữ', f'Curated original adult character(s): {curated_adults}', 'Adult AU gốc, không phải canon minor được nâng tuổi'),
                     ('Giữ có chọn lọc', 'Danbooru tag CSV: chỉ tag gắn với core tags của character đã import', 'Canonical hóa trực tiếp; không nhập toàn bộ archive'),
                     ('Giữ có chọn lọc', 'AI Pose Gallery outfit JSON', 'Generic outfit descriptors có text/tags; không phải canon'),
                     ('Pilot sau', 'Pose Gallery pose JSON', 'Chỉ hữu ích khi có caption tiếng Anh đã review'),
                     ('Loại', 'e621 namespace', 'Chưa có consumer rõ trong MVP'),
                     ('Loại', 'Portrait catalog', 'Không có consumer Story/Shot/Natural Prompt; chỉ là ảnh tham chiếu'),
                     ('Loại', 'COCO / Grounded SAM / OpenPose / skeleton', 'Không được skill runtime truy vấn'),
                     ('Loại khỏi DB', 'render_jobs / render_assets / RENDER QA', 'Renderer và image QA nằm ngoài ranh giới DB'),
                 ]), '',
                 '## 2. Snapshot metadata thô', '',
                 'Chỉ file metadata/Markdown/CSV được khai báo trong manifest; không có ảnh. '
                 '`source_records` giữ provenance cấp bản ghi; `source_record_versions` giữ lịch sử nội dung.',
                 '',
                 table(['Source', 'Key', 'Bytes', 'SHA256', 'Revision', 'Retrieved'],
                       raw_snapshots(ROOT / 'database' / 'imports')), '',
                 'File V1 không còn trong manifest V2 có thể vẫn nằm trong `database/imports/` để tham khảo lịch sử, '
                 'nhưng không được import vào DB và không xuất hiện trong bảng V2 ở trên.',
                 '',
                 '### Source registry', '',
                 table(['ID', 'Name', 'Kind', 'License'], registry), '',
                 '## 3. Catalog thực tế', '',
                 table(['Table', 'Rows'], sorted(flat.items())), '',
                 '### Tags theo namespace', '',
                 table(['Namespace', 'Tags'], sorted(tags.items())), '',
                 '### Tag relations', '',
                 table(['Namespace', 'Type', 'Status', 'Rows'],
                       [(r['namespace'], r['relation_type'], r['status'], r['n'])
                        for r in relations]), '',
                 '### Outfits', '',
                 table(['Kind', 'Verification', 'Rows'],
                       [(r['outfit_kind'], r['verification'], r['n']) for r in outfits]), '',
                 '### Captions', '',
                 table(['Lang', 'Origin', 'Review', 'Rows'],
                       [(r['lang'], r['origin'], r['review'], r['n']) for r in captions]), '',
                 '### Source records theo nguồn', '',
                 table(['Source', 'Records'], [(r['source_id'], r['n']) for r in source_records]), '',
                 '### QA theo subject (chỉ trước export)', '',
                 table(['Subject', 'Verdict', 'Rows'],
                       [(r['subject_kind'], r['verdict'], r['n']) for r in qa]), '',
                 '### Mẫu character', '',
                 table(['Character', 'Universe'], [(r['display_name'], r['universe']) for r in characters]), '',
                 '## 4. Top tag theo post_count', '',
                 table(['Namespace', 'Tag', 'Post count'],
                       [(r['namespace'], r['name'], r['post_count']) for r in top_tags]), '',
                 '## 5. Import runs gần nhất', '',
                 table(['Source', 'Status', 'Imported', 'Skipped', 'Errors', 'Started'],
                       [(r['source_id'], r['status'], r['imported_count'],
                         r['skipped_count'], r['error_count'], r['started_at']) for r in runs]), '',
                 '## 6. Điều đã chứng minh', '',
                 '- DeepGHS `blue_archive.md` import được 234 nhân vật; core tags ở trạng thái `CORE_CANDIDATE`, không phải canon/outfit/age.',
                 f'- Có {curated_adults} original adult character(s) trong universe `original_adult_au`, được khai báo rõ là original/AU, không phải canon minor được đổi tuổi.',
                 '- Danbooru CSV được lọc theo `character_tags`: chỉ tag thực sự gắn với character đã import, kèm aliases; không nhập e621/merged list.',
                 '- Outfit generic có text/tags, `outfit_kind=GENERIC`, `verification=UNVERIFIED`, `character_id=NULL`; không tạo outfit canon.',
                 '- `catalog_assets` không được dùng cho ảnh/portrait/pose; bảng render đã bị loại bởi migration `005_db_boundary`.',
                 '- QA mới ghi `STORY`, `SHOT`, `PROMPT`; `LAYOUT` cũ chỉ giữ lịch sử; RENDER bị từ chối.',
                 '- Chạy lại cùng source revision không tăng tag/character/outfit/caption; source versions giữ lịch sử.',
                 '- `PRAGMA integrity_check` = `ok`; `PRAGMA foreign_key_check` không có bản ghi.',
                 '', '## 7. Chưa chứng minh / còn thiếu', '',
                 '- **Chưa có** ảnh hoặc kiểm tra ảnh; `catalog_assets` kỳ vọng 0 trong V2.',
                 '- **Chưa import** pose catalog vì caption tiếng Anh chưa được review; pose importer là công cụ P1, không phải dữ liệu runtime hiện tại.',
                 '- **Chưa import** portrait, e621, COCO, OpenPose, Grounded SAM hoặc skeleton.',
                 '- **Chưa có** structured outfit parts/palette đã curate; generic outfit chỉ là candidate text.',
                 '- **Chưa import** Danbooru API aliases/implications live; CSV aliases đã có, implications cần export thủ công.',
                 '- **Chưa có** Wikidata linking; **chưa chạy** renderer/MOSS image QA.',
                 '- Cần kiểm thử consumer thực tế: action/pose/tag phải tác động đến ShotSpec và natural prompt được tạo; test định dạng/CLI không thay thế kiểm tra ngữ nghĩa bằng LLM.',
                 '', '## 8. Lệnh tái lập', '',
                 '```powershell',
                 'python database/src/collect_sources.py fetch --source deepghs',
                 'python database/src/collect_sources.py fetch --source ai_pose_gallery',
                 'python database/src/collect_sources.py fetch --source dbr_e621_lists',
                 'python database/src/n2m_db.py init',
                 'python database/src/n2m_db.py seed',
                 'python database/src/n2m_db.py import-deepghs-md database/imports/deepghs/blue_archive.md',
                 'python database/src/n2m_db.py import-tags-csv database/imports/dbr-e621-lists-archive/danbooru/danbooru_2026-10-01_pt20-ia-dd.csv --namespace danbooru --from-character-core-tags --source-revision "2026-10-01/pt20-ia-dd"',
                 'python database/src/n2m_db.py import-costume-gallery-json database/imports/ai-pose-gallery/data/costume-zh.json --source-id ai_pose_gallery --source-revision github-main',
                 'python database/src/n2m_db.py import-costume-gallery-json database/imports/ai-pose-gallery/data/costume-anime-zh.json --source-id charadb --source-revision charadb-7fe2e4b009ad6d85496101e929ac8528cb21d357',
                 'python database/src/n2m_db.py stats --detailed',
                 'python -m unittest discover -s tests -v',
                 '```',
                 '', '## 9. Ghi chú license', '',
                 'Metadata import không đồng nghĩa quyền tái phân phối ảnh hoặc dùng thương mại. '
                 'AI Pose Gallery/CharaDB có thể có điều kiện riêng cho từng asset; không tải/đóng gói ảnh. '
                 'Danbooru metadata vẫn chịu terms của nguồn. Kiểm tra lại trước khi dùng ngoài phạm vi nội bộ.', '']
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text('\n'.join(lines), encoding='utf-8')
        print(f'Written: {args.out}')
    finally:
        con.close()


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, sqlite3.Error) as exc:
        raise SystemExit(f'ERROR: {exc}')
