# V4 - P8 legacy table disposition

Mục tiêu: mỗi bảng legacy có một quyết định rõ, không xóa mù. Bảng "keep" vẫn là
canonical. Bảng "projection" chỉ là read model. Bảng "transitional" còn cột/file cũ
nhưng không còn là nguồn ghi mới.

Nguồn kiểm tra: `docs/v4/mappings/LEGACY_23_DB_TABLES.csv` và
`scripts/qa/verify_p8_disposition.py`.

| # | Bảng | P8 | Ghi chú |
|---:|---|---|---|
| 1 | `source_snapshot` | keep | provenance import |
| 2 | `tag` | keep | canonical catalog, 1.2M+ rows |
| 3 | `tag_source` | keep | provenance |
| 4 | `tag_alias` | keep | winner + `tag_alias_conflict` |
| 5 | `tag_role` | keep | multi-role |
| 6 | `tag_relation` | keep | relation + `tag_relation_source` |
| 7 | `tag_content_label` | keep | label catalog |
| 8 | `visual_concept` | keep | concept catalog |
| 9 | `concept_tag` | keep | mapping |
| 10 | `concept_relation` | keep | empty, reserved |
| 11 | `visual_concept_fts` | keep | rebuildable index |
| 12 | `model_profile` | keep | render reference |
| 13 | `project` | keep | project root |
| 14 | `character_profile` | transitional | `identity_json`, `outfit_json` còn đọc bởi importer/seed cũ; revision là canonical |
| 15 | `act` | keep | act root |
| 16 | `shot` | transitional | `character_id`, `shot_spec_json` còn đọc bởi QA/seed cũ; participant/spec revision là canonical |
| 17 | `generation` | cleanup | `image_path` đã bị rebuild bỏ; bytes ở `asset_blob` |
| 18 | `shot_state` | projection | latest inferred state |
| 19 | `act_continuity` | keep | initial act state |
| 20 | `shot_observation` | projection | compat đến khi assertion parity |
| 21 | `act_observation` | projection | compat đến khi assertion parity |
| 22 | `act_publication` | transitional | export history; prompt revision là canonical |
| 23 | `shot_finding` | projection | latest QA finding; `qa_issue` giữ history |

## Đã xóa thật

`generation.image_path`:

- Script: `scripts/migrations/p8_drop_generation_image_path.py`
- Version: `011_p8_generation_no_image_path`
- Rebuild giữ rows, PK, `image_sha256`, `evaluation_json`, `decision`, `created_at`;
  chỉ bỏ cột path.
- Recreate index `idx_generation_shot` và trigger `trg_generation_shot_frozen`.
- Render mới không ghi `image_path`; bytes nằm trong `asset_blob`.
- Đã chạy trên staging, không chạy trên live.

## Chưa xóa (có lý do)

- `character_profile.identity_json/outfit_json`: importer roster và seed cũ vẫn đọc.
  Chỉ xóa sau khi importer/seed chuyển hẳn sang `character_identity_revision` và
  `outfit_revision`.
- `shot.character_id/shot_spec_json`: QA/seed/import cũ vẫn đọc. Chỉ xóa sau khi
  mọi reader dùng `shot_participant` + `shot_spec_revision`.
- `act_publication`: seed cũ vẫn ghi khi xuất prompt file. Chỉ xóa sau khi bỏ
  file publication hoặc chuyển thành export job.
- `shot_finding`/`shot_state`/observations: projection tương thích; chỉ retire sau
  khi UI/QA đọc `qa_issue`/`continuity_assertion`.

## Kiểm tra

```text
python scripts/qa/verify_p8_disposition.py --db db/backup/pr-01/staging_live.db \
  --json evidence/pr-08/disposition_after.json
```

Kết quả: `legacy_table_count=23`, `disposition_count=23`, không bảng nào thiếu
disposition. `--require-clean` vẫn trả mã 3 vì còn các cột transitional ở trên.
Đây là trạng thái đúng, không phải pass giả.
