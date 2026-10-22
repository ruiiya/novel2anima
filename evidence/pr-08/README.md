# PR-08 - DB cleanup, docs and skills

## Trạng thái

| Mục | Kết quả |
|---|---|
| Trạng thái | **MỘT PHẦN** - cleanup an toàn đã làm, còn legacy transitional |
| Branch | `rebuild/v4` |
| Cleanup thật | `generation.image_path` đã bị rebuild bỏ trên staging |
| Disposition | 23/23 bảng legacy có quyết định |
| Docs | `docs/v4/README.md`, `P8_LEGACY_DISPOSITION.md`, README, 3 skills |
| Tests | 3 PR-08; full suite 126 pass, 1 skip |

## Đã xóa: `generation.image_path`

- Script: `scripts/migrations/p8_drop_generation_image_path.py`
- Version: `011_p8_generation_no_image_path`
- Cách làm: tạo `generation_new`, copy đủ rows/PK/`image_sha256`/`evaluation_json`/`decision`/`created_at`, drop bảng cũ, rename, tạo lại index + trigger.
- Không đọc/ghi path nữa; render bytes nằm trong `asset_blob`, SHA-256 là khóa.
- Đã chạy trên staging, không chạy live.

## 23 bảng legacy

`scripts/qa/verify_p8_disposition.py` đọc mapping CSV, DB và code:

```text
legacy_table_count=23
disposition_count=23
missing_from_csv=[]
missing_disposition=[]
```

Chi tiết: [`docs/v4/P8_LEGACY_DISPOSITION.md`](../../docs/v4/P8_LEGACY_DISPOSITION.md).

`--require-clean` trả mã **3** vì còn:

- `character_profile.identity_json/outfit_json`
- `shot.character_id/shot_spec_json`
- `act_publication`
- các projection `shot_finding`, `shot_state`, observations

Đây là blocker thật: importer/seed/QA cũ vẫn đọc các cột này. Không xóa trước
khi reader/writer cuối cùng được chuyển, theo đúng quy tắc P8.

## Docs/skills

- `docs/v4/README.md`: trạng thái PR, layout, DB, command.
- `docs/v4/P8_LEGACY_DISPOSITION.md`: bảng 23 dòng, đã xóa/chưa xóa/lý do.
- `README.md`: V4 là canonical, `etl/` là shim.
- `skills/novel2anima-catalog`, `shot-pipeline`, `natural-language-prompt`:
  ghi rõ DB canonical và legacy transitional.

## Staging

- Backup trước cleanup: `db/backup/pr-08/pre_p8_staging.db`
- SHA-256: `5ab656eb24521c23a8f9dd592abd48f9b73a90ef7d082545b70dc8a291d9d83a`
- Sau cleanup: `quick_check=ok`, `foreign_key_check=[]`, `project=0`
- `generation` columns không còn `image_path`.

## Tests

```text
python -m unittest tests.test_pr08_cleanup -v
Ran 3 tests
OK

python -m unittest discover -s tests -q
Ran 126 tests
OK (skipped=1)

python -m unittest discover -s docs/v4/tests -q
Ran 14 tests
OK
```

## Không tuyên bố pass

PR-08 **chưa hoàn tất** theo định nghĩa "final schema no duplicate authoritative
stores". Đã hoàn tất một cleanup data-preserving và disposition/audit; các cột
transitional còn lại là công việc tiếp theo, cần chuyển reader/writer trước khi
drop.
