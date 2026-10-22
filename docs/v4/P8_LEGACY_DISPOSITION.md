# V4 - P8 legacy table disposition

Mục tiêu: mỗi bảng legacy có một quyết định rõ, không xóa mù. Bảng "keep" vẫn là
canonical. Bảng "projection" chỉ là read model. Bảng "removed" đã bị xóa khỏi schema.

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
| 14 | `character_profile` | keep | identity/outfit nằm trong revision tables |
| 15 | `act` | keep | act root |
| 16 | `shot` | keep | participants/spec nằm trong canonical tables |
| 17 | `generation` | cleanup | `image_path` đã bị rebuild bỏ; bytes ở `asset_blob` |
| 18 | `shot_state` | projection | latest inferred state |
| 19 | `act_continuity` | keep | initial act state |
| 20 | `shot_observation` | projection | compat đến khi assertion parity |
| 21 | `act_observation` | projection | compat đến khi assertion parity |
| 22 | `act_publication` | removed | prompt revision là canonical; file chỉ là export |
| 23 | `shot_finding` | projection | latest QA finding; `qa_issue` giữ history |

## Đã xóa thật

`generation.image_path`:

- Script: `scripts/migrations/p8_drop_generation_image_path.py`
- Version: `011_p8_generation_no_image_path`
- Rebuild giữ rows, PK, `image_sha256`, `evaluation_json`, `decision`, `created_at`;
  chỉ bỏ cột path.
- Recreate index `idx_generation_shot` và trigger `trg_generation_shot_frozen`.
- Render mới không ghi `image_path`; bytes nằm trong `asset_blob`.
- Đã chạy trên staging và live; backup dưới `db/backup/`.

`character_profile.identity_json/outfit_json`, `shot.character_id/shot_spec_json`,
`act_publication`:

- Script: `scripts/migrations/p8_drop_legacy_authority.py`
- Version: `012_p8_no_legacy_authority`
- Copy legacy JSON sang revision canonical nếu revision chưa có, rồi rebuild
  `character_profile` + `shot`; giữ PK, row count, index và trigger.
- Drop `act_publication`; prompt file chỉ là export, không còn outbox.
- Đã chạy trên staging và live; `quick_check=ok`, `foreign_key_check=[]`.

## Projection còn giữ

- `shot_finding`/`shot_state`/`shot_observation`/`act_observation` là read model
  phái sinh. Chúng không phải nguồn ghi canonical và có thể retire sau khi UI/QA
  đọc hoàn toàn `qa_issue`/`continuity_assertion`.
- Không còn cột hay bảng legacy transitional nào.

## Kiểm tra

```text
python scripts/qa/verify_p8_disposition.py --db db/backup/pr-01/staging_live.db \
  --json evidence/pr-08/disposition_after.json --require-clean
```

Kết quả: `legacy_table_count=23`, `disposition_count=23`, không bảng nào thiếu
disposition. `--require-clean` trả mã 0; chỉ còn projection read model.
