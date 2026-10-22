# PR-03 - External import infrastructure

## Trạng thái

| Mục | Kết quả |
|---|---|
| Trạng thái | **HOÀN TẤT** (chờ commit) |
| Branch | `rebuild/v4` |
| HEAD trước PR-03 | `8d18c0d` |
| Ngày | 2026-10-22 |
| Phạm vi | Migration `008`, ledger theo từng file, parser cho plan/prompt/review/wardrobe/roster/catalog/asset, CLI import và verifier |
| DB staging | `db/backup/pr-01/staging_live.db` |
| Live DB | Không ghi, không migrate, không hash lại được do file đang bị process khác giữ lock |

PR-03 chỉ ghi vào **bản staging**. Không có thay đổi nào trên `db/novel_anima.db`, không có `git clean`, `git reset`, hay ghi đè các file user đang sửa.

## 1. Migration 008

Đã backup staging trước khi apply:

- `db/backup/pr-03/pre_008_staging.db`
- size: `393,494,528` bytes
- SHA-256: `bbc550c0193d89535c295039f3c3d0acfb8c4cf57421a962a4d665b56268d9ba`

Apply `008_import_ledger.sql`:

- `status=ok`
- applied: `008_import_ledger` (`a6c3228d690cea0ba49a272deb93440d952e41eec784b0f9be908f83f3abe224`)
- skipped: `002` -> `007` (đã có từ trước)
- pending sau apply: `[]`
- `integrity_check=ok`, `foreign_key_check=[]`
- report: `evidence/pr-03/migration_apply.json`

`008` tạo:

- `import_file_ledger` - ledger theo `(source_relative_path, source_sha256, parser_version)`, lưu classification, parser version, status, target, exception, details và hash đã đọc.
- `qa_run_source` - giữ nguyên raw JSON của review cạnh `qa_run` / `qa_issue` đã chuẩn hóa.

Không sửa `import_batch_file` vì bảng đó gắn với `asset_blob`; PR-03 chưa lưu ảnh/render.

## 2. Import ledger

Nguồn được quét với `--source-root` tường minh, không đọc theo working directory.

| Chỉ số | Giá trị |
|---|---:|
| File hiện tại | 359 |
| Tổng byte hiện tại | 51,790,299 |
| Dòng ledger hiện tại | 369 |
| Dòng ledger cho source hiện tại | 359 |
| Imported ở lần apply đầu | 16 |
| Duplicate ở lần apply đầu | 13 |
| Blocked | 3 |
| Skipped by policy | 327 |
| `asset_blob` | 0 |

369 dòng ledger gồm 359 dòng đại diện source hiện tại và 10 dòng lịch sử cho các file source code đã thay đổi trong lúc hoàn thiện PR-03. Ledger là append-only theo hash; `verify_ledger` chỉ kiểm tra hash hiện tại và trả `missing=0`, `mismatched=0`, `stale_paths=0`.

Phân loại hiện tại:

| Classification | Số file |
|---|---:|
| `plan` | 8 |
| `prompt` | 19 |
| `review` | 3 |
| `wardrobe` | 2 |
| `roster` | 4 |
| `catalog` | 10 |
| `source_controlled` | 239 |
| `legacy_workspace` | 34 |
| `legacy_report` | 5 |
| `llm_scaffold` | 35 |
| **Tổng** | **359** |

Nguồn ngoài ledger:

- `db/novel_anima.db`, `-wal`, `-shm`: destination, không phải import source; bị skip trước khi hash.
- `.git`, `dist`, `evidence`, `db/backup`, các cache `__pycache__`, `.pytest_cache`, ...: excluded directory, được ghi trong report.
- Không có symlink nào bị bỏ qua trong lần chạy này.

Report đầy đủ:

- `evidence/pr-03/import_dry_run.json`
- `evidence/pr-03/import_apply.json`
- `evidence/pr-03/import_rerun.json`
- `evidence/pr-03/import_final.json`
- `evidence/pr-03/ledger_verification.json`

Lưu ý: `counts.target_rows.source_snapshot` trong `import_apply.json` / `import_dry_run.json` ghi `1` do bản report lúc đó dùng fallback `inserted`; DB thực tế có **7** snapshot. `counts_after_import.json` và query DB là nguồn số liệu cuối.

## 3. Dữ liệu đã nhập

Số liệu lấy trực tiếp từ staging sau import (`evidence/pr-03/counts_after_import.json`).

| Đích | Số dòng | Ghi chú |
|---|---:|---|
| `project_document_revision` | 37 | 31 dòng cũ + **6 plan document** mới |
| `shot_prompt_revision` | 1,890 | 765-r3: 1,510; fumika-60: 60; kanna-160: 160; kanna-160.hybrid: 160 |
| `shot_prompt_spec` | 1,890 | 1:1 với prompt revision, trỏ đúng `shot_spec_revision` |
| `qa_run` | 3 | 3 review file |
| `qa_issue` | 63 | 8 + 55 + 0 sau chuẩn hóa |
| `qa_run_source` | 3 | raw JSON của cả 3 review |
| `n2a_setting_revision` | 2 | wardrobe draft, không activate |
| `source_snapshot` | 18 | 11 cũ + **7 catalog provenance** |
| `reconciliation_item` | 12,521 | 12,506 cũ + **15 roster gap** |
| `import_batch` | 3 | apply, rerun, final |
| `import_file_ledger` | 369 | 359 current + 10 historical |
| `asset_blob` | 0 | asset storage vẫn deferred |

Các bảng projection của PR-02 giữ nguyên: `character_identity_revision=574`, `outfit_revision=1,142`, `outfit_item=2,805`, `shot_spec_revision=7,099`, `shot_participant=10,444`, `shot_interaction=1,160`, `shot_outfit_binding=339`.

### Plan

6 plan document được nhập, không tạo project/act mới:

- `765/plan-765-r3.input.json`
- `765/plan-765-r3.json`
- `765/plan-fumika-60.input.json`
- `765/plan-fumika-60.json`
- `data/plans/plan-kanna-160.input.json`
- `data/plans/plan-kanna-160.json`

Hai `act_specs` bị block vì project title không tồn tại trong DB:

- `act_specs/duo_greeting.json` - `plan_project_not_found`
- `act_specs/solo_tea.json` - `plan_project_not_found`

Không suy đoán project/act từ tên file hay act number.

### Prompt

- 4 file positive prompt được import: 1,890 block.
- 4 file `kanna-act01..04.hybrid.txt` là exact slice của `prompts/kanna-160.hybrid.txt`; được ghi `duplicate`, không tạo revision thứ hai.
- 11 file negative/test được skip theo policy; không được coi là prompt production.
- Không gán prompt theo filename; mapping chỉ đến từ `prompt_file` trong plan document.
- `kanna-160.txt` và `kanna-160.hybrid.txt` được xử lý riêng; hybrid lưu `natural_prompt` từ `SCENE & ACTION`, positive tags từ STYLE/IDENTITY/OUTFIT/CINEMATOGRAPHY.

### Review / QA

- 3 review file, 70 finding thô.
- 63 `qa_issue` chuẩn hóa:
  - Act 1: 8
  - Act 13: 55
  - Act 77: 0
- Các finding trùng `(shot, axis)` được gộp thành một issue, giữ **tất cả** finding trong `evidence_json` và giữ raw JSON trong `qa_run_source.raw_json`; severity lấy max.
- Không gắn review vào project bằng cách đoán act number.

### Wardrobe

- `data/wardrobe/colour_choice.json`
- `data/wardrobe/colour_cue.json`

Cả hai được lưu thành `n2a_setting_revision` trạng thái `draft`; không active, không ghi đè setting đang dùng.

### Roster

- BA và Idolmaster là exact duplicate của DB; ghi `duplicate`.
- `data/characters/dxd_roster.json` khác DB:
  - 1 `roster_identity_mismatch`
  - 14 `roster_outfit_mismatch`
  - Tổng 15 gap được queue; file bị `blocked`, **không overwrite** canonical `character_profile`.
- `data/characters/ba_outfits.json` là report, không phải roster; skip.

### Catalog

- `data/sources/manifest.json` xác minh 7 file: byte length + SHA-256.
- Tạo 7 `source_snapshot` provenance row.
- Raw catalog cache không copy vào `asset_blob`; cache files được ghi `duplicate` sau khi manifest xác minh.
- 2 file không được manifest tham chiếu được skip, không claim là đã migrate.

### Asset

Không có file ảnh nào trong source scope lần này. `asset_blob` vẫn `0`; policy `asset_blob_deferred` được giữ nguyên cho các lần import sau.

## 4. Idempotency

Lần chạy lại với cùng source:

| Lần | Imported | Duplicate | Blocked | Skipped | Business rows mới |
|---|---:|---:|---:|---:|---|
| Apply đầu (`pr03-apply-001`) | 16 | 13 | 3 | 327 | 6 plan, 1,890 prompt, 3 QA, 2 setting, 7 snapshot |
| Rerun (`pr03-rerun-001`) | 0 | 29 | 3 | 327 | 0 |
| Final sau code freeze (`pr03-final-001`) | 0 | 29 | 3 | 327 | 0 |

Sau rerun:

- `project_document_revision` vẫn 37
- `shot_prompt_revision` vẫn 1,890
- `qa_run` vẫn 3, `qa_issue` vẫn 63
- `n2a_setting_revision` vẫn 2
- `source_snapshot` vẫn 18
- `reconciliation_item` vẫn 12,521

Chỉ `import_batch` tăng và ledger cập nhật `import_batch_id`/`checked_at`; không nhân bản dữ liệu nghiệp vụ.

## 5. Kiểm chứng

### Ledger

`scripts/diagnostics/verify_import_ledger.py`:

- `status=ok`
- 359 source hiện tại / 369 ledger rows
- `missing=[]`
- `mismatched=[]`
- `stale_paths=[]`
- `quick_check=ok`
- 0 FK violation

### Staging

`scripts/diagnostics/verify_staging.py`:

- `status=ok`
- 23/23 bảng baseline còn tồn tại
- 22 bảng baseline không đổi
- `source_snapshot` tăng `11 -> 18`, được khai báo là **allowed provenance change**; đây là 7 snapshot mới, không phải backfill nội dung cũ
- 36 bảng mới (bao gồm FTS shadow tables)
- `quick_check=ok`, 0 FK violation

Các bảng baseline quan trọng giữ nguyên:

- `tag=1,208,773`
- `tag_source=1,479,995`
- `tag_alias=149,546`
- `tag_role=30,265`
- `tag_relation=213,175`
- `tag_content_label=9,994`
- `visual_concept=583`
- `concept_tag=9,741`
- `project=31`
- `character_profile=574`
- `act=77`
- `shot=7,099`
- `shot_state=665`
- `act_continuity=48`
- `act_publication=27`
- `shot_finding=69`

Report: `evidence/pr-03/verify_staging.json`, `evidence/pr-03/counts_after_import.json`.

## 6. An toàn live DB

- `run_import` từ chối `db/novel_anima.db` nếu không có `allow_live=True`.
- Import thật chỉ chạy trên `db/backup/pr-01/staging_live.db`.
- Live DB hiện tại:
  - size: `360,968,192` bytes (giống PR-00 audit)
  - mtime: `2026-10-21T10:11:38.023348+00:00`
  - hash hiện tại: không đọc được vì file bị process khác giữ lock
  - hash đã ghi nhận trước đó: `2cd296ce9be953a85d77acc4d18d46ca7f1531121b4a2d3645e76461fe3b0eac`
- `db/novel_anima.db`, `-wal`, `-shm` bị importer skip trước khi hash, nên không có đường đọc/ghi live DB trong PR-03.

Chi tiết: `evidence/pr-03/database_checksums.json`.

## 7. Backup và checksum staging

| Artifact | Size | SHA-256 |
|---|---:|---|
| `pre_008_staging.db` | 393,494,528 | `bbc550c0193d89535c295039f3c3d0acfb8c4cf57421a962a4d665b56268d9ba` |
| `pre_import_staging.db` | 393,527,296 | `4cb50f06b416d863202aa8646671af47b9caeebd47b782aa9453e9c4716a2349` |
| `staging_live.db` sau PR-03 | 397,799,424 | `0031b7b7eb5b89a4f3567f91be30f26b147fd611e868dce0d1572c8a4f58297f` |

Checksum source/migration/test: `evidence/pr-03/checksums.txt`.

## 8. Tests

| Bộ test | Kết quả |
|---|---|
| Full suite `tests/` | **102 pass**, 0 fail |
| V4 bundle `docs/v4/tests/` | **14 pass**, 0 fail |

Output:

- `evidence/pr-03/tests.txt`
- `evidence/pr-03/v4_bundle_tests.txt`

Test mới bao phủ:

- classify + ledger đầy đủ file, kể cả skip/report/LLM scaffold
- prompt mapping, exact slice duplicate, prompt count mismatch
- idempotent rerun: 0 imported, không tăng business rows
- dry-run rollback toàn bộ, kể cả ledger/batch
- từ chối live DB
- catalog SHA-256 mismatch -> manifest/cache blocked, không tạo snapshot
- roster mismatch -> queue + block, không overwrite
- asset deferral, không ghi `asset_blob`
- `source_root` độc lập với process CWD
- canonical DB không bị hash/ledger
- `verify_staging` allowed provenance drift

## 9. Files thay đổi

Mới:

- `sql/migrations/008_import_ledger.sql`
- `src/novel2anima/storage/import_ledger.py`
- `src/novel2anima/storage/importers/` (`base`, `assets`, `catalog`, `plan`, `prompt`, `review`, `roster`, `wardrobe`, `__init__`)
- `scripts/migrations/import_legacy.py`
- `scripts/diagnostics/verify_import_ledger.py`
- `tests/test_import_ledger.py`
- `evidence/pr-03/`

Sửa:

- `scripts/diagnostics/verify_staging.py` - thêm `--allow-changed` cho provenance drift có chủ đích
- `tests/test_migrations.py` - thêm `008_import_ledger` vào discovery
- `tests/test_verify_staging.py` - test allowed change

Không đụng tới các file user đang sửa:

- `etl/check_prompts.py`
- `etl/seed_plan.py`
- `etl/story_logic.py`
- `skills/novel2anima-shot-pipeline/SKILL.md`

`765/` và `dist/` vẫn là untracked/user workspace; không commit.

## 10. Việc chuyển sang PR sau

- `asset_blob` / render/reference image persistence vẫn deferred.
- 2 `act_specs` chưa có project/act tương ứng; không tạo tự động.
- 15 gap roster DXD đang chờ quyết định của con người.
- 1,253 gap interaction từ PR-02 vẫn giữ nguyên; PR-03 không suy đoán actor/target cho duo shot.
- Các prompt test/negative và catalog cache không tham chiếu vẫn chỉ là skipped evidence, không phải runtime truth.
