# PR-07 - Prompt compile, render and QA

## Trạng thái

| Mục | Kết quả |
|---|---|
| Trạng thái | **HOÀN TẤT** |
| Branch | `rebuild/v4` |
| Migration | `010_prompt_pinning.sql` |
| Prompt | `prompting/compiler.py` |
| Render | `render/service.py`, `storage/assets.py` |
| QA | `quality/qa.py` |
| Tests | 4 test PR-07; full suite 123 pass, 1 skip |
| Staging | `db/backup/pr-01/staging_live.db`, 010 applied |

## Compile từ DB

`compile_shot(shot_id)` chỉ đọc:

- `shot_spec_revision` đã approved;
- `shot_participant`;
- `shot_interaction` với actor/target tường minh;
- `shot_outfit_binding` + `outfit_revision`/`outfit_item`;
- `tag` catalog.

Không đọc file prompt, không đọc CWD. Tag không có trong `tag` là lỗi; không tự sinh tag. Thứ tự deterministic: identity → outfit → interaction → action → expression → pose → camera → background → style → other, sau đó theo character/slot/tag.

`shot_prompt_tag` lưu `character_id` và `target_character_id` cho interaction, nên không thể đảo actor/target khi replay.

## Pin input

`shot_prompt_spec` pin:

- `shot_spec_revision_id`;
- `catalog_snapshot_sha256`;
- `outfit_snapshot_sha256`.

`shot_prompt_outfit_input` pin từng `(character_id, outfit_revision_id)`. `shot_prompt_revision.source_shot_spec_sha256` pin spec content. Prompt approved bị trigger khóa content, tag và outfit input.

## Render BLOB

- `asset_blob` dùng content-addressed SHA-256, dedupe theo SHA, verify `length(body)` và SHA khi đọc.
- `generation.image_path` để `NULL`; bytes nằm trong `asset_blob`.
- `generation_asset(role='render')` và `generation_provenance` pin prompt revision, seed, model settings, outfit snapshot.
- `get_render()`/`replay_render()` chỉ đọc DB; không đọc `data/` hay `prompts/`.

## QA

- `record_qa_run()` append `qa_run` + `qa_issue`; cùng `run_key` trả run cũ, không tạo history trùng.
- `qa_history()` trả toàn bộ lần chạy, không ghi đè issue cũ.
- `apply_targeted_revision()` tạo `shot_spec_revision` draft mới, giữ participants và actor/target, đánh dấu issue `fixed`; revision cũ không đổi.

## Migration staging

- Backup: `db/backup/pr-07/pre_010_staging_backup.db`
- Backup SHA-256: `82d83154a1e3f392bb7a4150be3862db91e9912bdbd29b04b874f2a6187c4432`
- `010_prompt_pinning` applied; `pending=[]`, `integrity=True`, `foreign_keys=True`
- `project=0`, `quick_check=ok`
- `shot_prompt_tag.target_character_id` đã có FK tới `character_profile(id)`

## Tests

```text
python -m unittest tests.test_pr07_compile_render_qa -v
Ran 4 tests
OK

python -m unittest discover -s tests -q
Ran 123 tests
OK (skipped=1)
```

## Giới hạn

- Chưa gọi Anima/workflow thật; `create_render()` nhận bytes từ adapter bên ngoài.
- Natural prompt chỉ dùng `shot_spec_json.natural_prompt` đã có; stage 08 LLM chưa bật.
- `image_path` legacy vẫn còn cột nhưng không được ghi; xóa cột thuộc PR-08.
