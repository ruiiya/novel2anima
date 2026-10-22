# Backup, restore and rollback

## Nguyên tắc

- SQLite là nguồn canonical; render bytes nằm trong `asset_blob`.
- Backup bằng SQLite Backup API, không copy file khi đang ghi.
- Backup phải gồm DB; Git source đủ để dựng lại code. Không cần `data/plans`,
  `prompts/`, `reviews/` để replay.
- Không restore đè live đang chạy. Restore vào file mới, kiểm tra, rồi mới cutover.

## Backup

```powershell
$env:PYTHONPATH='src'
python -c "from novel2anima.storage.migrations import backup_database; from pathlib import Path; backup_database(Path('db/novel_anima.db'), Path('db/backup/release.db'))"
```

Hoặc dùng gate:

```powershell
$env:PYTHONPATH='src'
python scripts/release/release_gate.py --db db/backup/pr-01/staging_live.db --report evidence/pr-09/release_gate.json
```

Gate tự tạo snapshot nguồn, E2E copy, backup/restore copy và rollback copy trong
temporary directory; không ghi vào DB nguồn.

## Kiểm tra sau backup

```sql
PRAGMA quick_check;
PRAGMA foreign_key_check;
SELECT count(*) FROM tag;
SELECT count(*) FROM asset_blob;
SELECT count(*) FROM n2a_schema_migration;
```

So sánh `n2a_schema_migration.sha256` với `sql/migrations/*.sql`; gate làm việc này
và ghi `signed_ledger`.

## Restore

```powershell
python scripts/release/release_gate.py --db db/backup/pr-01/staging_live.db --work-dir db/backup/pr-09/drill
```

Quy trình thủ công:

1. Dừng writer/worker.
2. Backup DB hiện tại sang file forensic, không xóa.
3. Backup API từ bản backup đã chọn sang file mới.
4. `quick_check`, `foreign_key_check`, đếm bảng, SHA `asset_blob`, prompt revision.
5. Trỏ application sang file mới; chạy smoke path.
6. Chỉ sau signoff mới xóa bản cũ.

## Rollback

1. Dừng writer trên bản mới.
2. Giữ snapshot bản mới để điều tra, không ghi đè.
3. Restore snapshot trước cutover.
4. Chạy lại `quick_check`/FK/count; so sánh với số liệu trước cutover.
5. Ghi các write phát sinh sau cutover thành migration riêng; không trộn vào bản cũ.

## Số đo PR-09 trên staging

- DB: `db/backup/pr-01/staging_live.db`
- Kích thước ~400 MB, 1,208,773 tag (bản E2E copy thêm 6 tag synthetic).
- Backup + restore 2 lớp: ~10.2 giây (máy local, staging).
- `foreign_key_check`: ~37.6 giây.
- Rollback: khớp counts nguồn, `quick_check=ok`.
- Ảnh E2E là bytes tổng hợp 20 B; chưa phải render Anima thật.

## Ký ledger

`release_gate.json.signed_ledger` có `signature_type`:

- `sha256-content`: digest của payload, không cần key.
- `hmac-sha256`: đặt `N2A_RELEASE_SIGNING_KEY` khi chạy gate.

Signature bao gồm payload trước trường `signature`; verify bằng cách bỏ
`signature`, canonical JSON sort key, rồi HMAC/SHA lại.
