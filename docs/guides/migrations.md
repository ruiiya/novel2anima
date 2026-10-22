# Migration runner (PR-01)

## Nguyên tắc

- Mỗi migration là một file `.sql` trong `sql/migrations/`; tên file (phần stem) là **version**.
- Runner lưu SHA-256 của đúng bytes đã apply vào `n2a_schema_migration`.
- Nếu file đã apply bị sửa → **abort** (`checksum drift`), không tự đoán.
- Mỗi migration chạy trong một transaction; `foreign_keys=ON`; lỗi giữa chừng → rollback.
- Runner từ chối `db/novel_anima.db` trừ khi truyền `--allow-live` (chỉ dùng cho cutover drill đã được duyệt).
- Luôn chạy trên **bản staging copy**. Backup trước khi apply là mặc định.

## Cài đặt tạm thời

PR-01 chưa có `pyproject.toml`/console script (PR-04). Chạy từ repo root với `PYTHONPATH=src`:

```powershell
$env:PYTHONPATH = "src"
```

## Kiểm tra trạng thái (dry-run)

```powershell
python -m novel2anima.storage.migrations `
  --db db\backup\pr-01\staging_live.db `
  --migrations sql\migrations `
  --dry-run `
  --report evidence\pr-01\staging_dry_run.json
```

## Apply lên staging copy

```powershell
python -m novel2anima.storage.migrations `
  --db db\backup\pr-01\staging_live.db `
  --migrations sql\migrations `
  --backup db\backup\pr-01\pre_migration_staging_live.db `
  --report evidence\pr-01\staging_migration_report.json
```

Sau khi apply:

```powershell
python scripts\diagnostics\verify_staging.py `
  --db db\backup\pr-01\staging_live.db `
  --baseline evidence\pr-00\db_audit.json `
  --output evidence\pr-01\staging_verification.json
```

`verify_staging.py` kiểm tra:

- 23 bảng baseline còn đủ và **row count không đổi**;
- bảng mới của 005/006 tồn tại;
- `quick_check=ok`, `foreign_key_check` rỗng;
- ledger có version + SHA-256.

## Phạm vi PR-01

- Chỉ **additive schema**. Không backfill dữ liệu, không drop bảng/cột legacy.
- 002/003/004 đã idempotent (`IF NOT EXISTS`); trên staging copy chúng được ghi nhận lại vào ledger.
- 005/006 được review từ DRAFT; bản gốc vẫn ở `docs/v4/sql/proposals/`.
- Backfill `project_document_revision`, `shot_participant`, prompt/tag mapping… là PR-02/03, không phải PR-01.
