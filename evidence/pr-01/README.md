# PR-01 — Migration runner + staging schema test

**Trạng thái:** COMPLETE
**Ngày:** 2026-10-22
**Branch:** `rebuild/v4`
**Tiền đề:** PR-00 commit `d1e0e64`
**Phạm vi:** additive schema 005/006 trên **staging copy**; không đụng DB thật, không backfill.

## 1. Kết quả

| Hạng mục | Kết quả |
|---|---|
| Migration runner | `src/novel2anima/storage/migrations.py` |
| Migration files | 002, 003, 004, **005_db_first**, **006_normalization** |
| Apply trên staging | **5 applied**, 0 failed |
| Dry-run lại | 0 applied, **5 skipped** (idempotent) |
| Checksum drift | **abort** đúng |
| Transaction rollback | **pass** |
| FK enforcement | **pass** |
| Live DB guard | **refuse** `db/novel_anima.db` |
| Staging verification | **23/23 bảng baseline không đổi**, 33 bảng mới, `quick_check=ok`, 0 FK violation |
| Test suite | **87 pass**, 0 fail |

## 2. Migration ledger

Các SHA-256 dưới đây là checksum của đúng file đã apply:

| Version | SHA-256 |
|---|---|
| `002_shot_state` | `11eabc02981293ce14d22f5b3d656a9efca49ad406cf847006f8a5512141e821` |
| `003_shot_finding` | `774a3eda5ad08060d041b21d08a08e671572451f70b4c62c4be6d8f380ca62d8` |
| `004_observation_publication` | `722c337ce92b10cc92f3942039e428be17c8153b644994104804d3a706b59266` |
| `005_db_first` | `e9d19e489a01bc032bafdb9fcbc38eb8b58e51b61b3f192aa91c56239caa0867` |
| `006_normalization` | `87cf6bdf7c2f69fcf483134c159f7a879d746b68e9bee829726cf769e9551c5f` |

- 005/006 được review từ DRAFT; bản gốc vẫn ở `docs/v4/sql/proposals/`.
- 005/006 cũng đã apply sạch trên base schema snapshot (không có dữ liệu live) — xem `staging_schema_test.json`.
- 002/003/004 vốn đã idempotent (`IF NOT EXISTS`), nên staging copy ghi nhận lại vào ledger mà không đổi schema.
- Đổi header DRAFT → migration chính thức, không đổi logic SQL.

## 3. Staging copy

- Nguồn: backup PR-00 `db/backup/pr-00/pr-00_20261022T034615Z.db`
- Bản staging: `db/backup/pr-01/staging_live.db`
  - 362.307.584 bytes
  - SHA-256: `59fa8d083c362225d9224a19696566b7af4540ec4f647fb09616042938e71ab8`
- Backup trước apply: `db/backup/pr-01/pre_migration_staging_live.db`
  - 361.881.600 bytes
  - SHA-256: `8f2335e8643b1b02d75ed92a128cd866a41f172b2299fa77cab28605dcd9fabb`
  - Trùng SHA-256 với backup PR-00

Các file DB/staging nằm dưới `db/backup/` nên **không vào Git**.

## 4. Kiểm tra sau apply

`scripts/diagnostics/verify_staging.py` so sánh với `evidence/pr-00/db_audit.json`:

- 23 bảng baseline: **đủ**, **0 bảng đổi row count**
- Bảng mới: 33 (28 bảng nghiệp vụ + ledger + 4 FTS shadow tables)
- `quick_check = ok`
- `foreign_key_check = []`
- Ledger: 5 dòng version + checksum
- Chi tiết: `staging_verification.json`

Các bảng mới quan trọng: `asset_blob`, `outfit_revision`, `shot_participant`, `shot_interaction`, `shot_prompt_revision`, `shot_prompt_tag`, `qa_run`, `qa_issue`, `import_batch`, `pipeline_run`, `llm_run`.

## 5. Test PR-01

`tests/test_migrations.py` (7 test) và `tests/test_verify_staging.py` (1 test):

- apply 005/006 lên base schema rồi rerun idempotent
- checksum drift abort
- migration lỗi giữa chừng rollback
- FK violation bị chặn và rollback
- live DB bị từ chối
- trigger body không bị split sai
- verify staging phát hiện count drift

Full suite: **87 pass** — xem `tests.txt`.

## 6. An toàn dữ liệu thật

- Không mở DB thật ở chế độ ghi.
- Không apply migration lên `db/novel_anima.db`.
- `db/novel_anima.db` giữ nguyên size/mtime:
  - main: 360.968.192 bytes, mtime `2026-10-21 17:11:38`
  - WAL: 6.686.792 bytes, mtime `2026-10-21 22:23:49`
- Lần hash lại trực tiếp bị một process bên ngoài giữ file; không có thao tác ghi nào được thực hiện. Baseline SHA-256 từ PR-00: `2cd296ce9be953a85d77acc4d18d46ca7f1531121b4a2d3645e76461fe3b0eac`.

## 7. Thay đổi sẽ commit

- `src/novel2anima/storage/migrations.py`
- `src/novel2anima/__init__.py`, `src/novel2anima/storage/__init__.py`
- `sql/migrations/005_db_first.sql`, `sql/migrations/006_normalization.sql`
- `scripts/diagnostics/verify_staging.py`
- `tests/test_migrations.py`, `tests/test_verify_staging.py`
- `docs/guides/migrations.md`
- `evidence/pr-01/*`

## 8. Bước tiếp theo

**PR-02:** backfill có kiểm soát (project document → `project_document_revision`; prompt legacy → `shot_prompt_revision`; character/project identity; duo actor/target reconciliation), vẫn trên staging copy. Chưa cutover live.
