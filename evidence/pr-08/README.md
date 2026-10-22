# PR-08 - DB cleanup, docs and skills

## Trạng thái

| Mục | Kết quả |
|---|---|
| Trạng thái | **HOÀN TẤT** - không còn cột/bảng legacy transitional |
| Branch | `rebuild/v4` |
| Cleanup thật | `image_path`, profile JSON, shot legacy columns, `act_publication`, `etl/` |
| Disposition | 23/23 bảng legacy có quyết định; `--require-clean` exit 0 |
| Docs | `docs/v4/README.md`, `P8_LEGACY_DISPOSITION.md`, README, 3 skills |
| Tests | 4 PR-08; full suite 124 pass, 1 skip |

## Đã xóa: `generation.image_path`

- Script: `scripts/migrations/p8_drop_generation_image_path.py`
- Version: `011_p8_generation_no_image_path`
- Cách làm: tạo `generation_new`, copy đủ rows/PK/`image_sha256`/`evaluation_json`/`decision`/`created_at`, drop bảng cũ, rename, tạo lại index + trigger.
- Không đọc/ghi path nữa; render bytes nằm trong `asset_blob`, SHA-256 là khóa.
- Đã chạy trên staging và live; backup dưới `db/backup/`.

## Đã xóa: legacy authority + shims

- Script: `scripts/migrations/p8_drop_legacy_authority.py`
- Version: `012_p8_no_legacy_authority`
- Copy legacy JSON sang revision canonical nếu chưa có, rebuild `character_profile`
  và `shot`, drop `act_publication`.
- Xóa toàn bộ `etl/` shim và hai migration script legacy
  `migrate_plan_semantics`, `migrate_runtime`; CLI dùng `python -m novel2anima...`.
- Đã chạy trên staging và live; `quick_check=ok`, `foreign_key_check=[]`.

## 23 bảng legacy

`scripts/qa/verify_p8_disposition.py` đọc mapping CSV, DB và code:

```text
legacy_table_count=23
disposition_count=23
missing_from_csv=[]
missing_disposition=[]
```

Chi tiết: [`docs/v4/P8_LEGACY_DISPOSITION.md`](../../docs/v4/P8_LEGACY_DISPOSITION.md).

`--require-clean` trả mã **0**. `character_profile`/`shot` chỉ còn cột canonical;
`act_publication` đã bị xóa. Các projection `shot_finding`, `shot_state`,
observations vẫn là read model phái sinh, không phải nguồn ghi canonical.

## Docs/skills

- `docs/v4/README.md`: trạng thái PR, layout, DB, command.
- `docs/v4/P8_LEGACY_DISPOSITION.md`: bảng 23 dòng, đã xóa/projection.
- `README.md`: V4 là canonical; `etl/` đã bị xóa.
- `skills/novel2anima-catalog`, `shot-pipeline`, `natural-language-prompt`:
  ghi rõ DB canonical và không còn shim legacy.

## Staging

- Backup trước cleanup authority: `db/backup/pr-09/pre_012_staging.db`
- Sau cleanup: `quick_check=ok`, `foreign_key_check=[]`, `project=0`
- `generation` columns không còn `image_path`.

## Tests

```text
python -m unittest tests.test_pr08_cleanup -v
Ran 4 tests
OK

python -m unittest discover -s tests -q
Ran 124 tests
OK (skipped=1)

python -m unittest discover -s docs/v4/tests -q
Ran 14 tests
OK
```

## Ghi chú

PR-08 đã hoàn tất phần schema: không còn cột/bảng legacy transitional. Projection
QA/continuity vẫn tồn tại có chủ đích như read model; retire khi UI/QA đọc hoàn
toàn `qa_issue`/`continuity_assertion`.
