# PR-04 - Domain package and compatibility shims

## Trạng thái

| Mục | Kết quả |
|---|---|
| Trạng thái | **HOÀN TẤT phần cấu trúc** |
| Branch | `rebuild/v4` |
| Phạm vi | 30 module `etl/*.py` -> `src/novel2anima/**` + `scripts/**`; `etl/` còn shim mỏng |
| Package | `pyproject.toml`, src-layout |
| CLI cũ | `python etl/<name>.py` vẫn chạy |
| Tests | 107 pass, 1 skip (102 cũ + 5 PR-04) |

## Mapping đã thực hiện

| Nguồn | Đích |
|---|---|
| `etl/build.py` | `src/novel2anima/catalog/build_service.py` |
| `etl/story_logic.py` | `src/novel2anima/story/logic.py` |
| `etl/build_story_plan.py` | `src/novel2anima/story/beat_planner.py` |
| `etl/plan_actions.py` | `src/novel2anima/story/action_planner.py` |
| `etl/seed_plan.py` | `src/novel2anima/pipeline/plan_seeder.py` |
| `etl/wardrobe.py` | `src/novel2anima/wardrobe/rules.py` |
| `etl/state_rules.py` | `src/novel2anima/continuity/rules.py` |
| `etl/infer_state.py` | `src/novel2anima/continuity/inference.py` |
| `etl/story_db.py` | `src/novel2anima/storage/story_repository.py` |
| `etl/act_quality.py` | `src/novel2anima/quality/act_quality.py` |
| `etl/check_prompts.py` | `src/novel2anima/quality/prompt_rules.py` |
| `etl/check_story.py` | `src/novel2anima/quality/story_rules.py` |
| `etl/qa_shots.py` | `src/novel2anima/quality/shot_rules.py` |
| `etl/llm_review.py` | `src/novel2anima/llm/adapters/review_adapter.py` |
| `etl/import_*.py`, `etl/analyze_posts.py`, `etl/add_ba_outfits.py` | `src/novel2anima/catalog/importers/**` |
| `etl/cleanup_db.py`, `etl/prune_tags.py` | `src/novel2anima/catalog/maintenance/**` |
| `etl/suggest_tags.py` | `src/novel2anima/catalog/retrieval/suggest_tags.py` |
| `etl/sources.json` | `config/catalog/sources.json` |
| `etl/check_reseed.py` | `scripts/qa/check_reseed.py` |
| `etl/migrate_*.py` | `scripts/migrations/*.py` |

`etl/*.py` chỉ còn shim: thêm `src` vào `sys.path`, import module đích, alias `sys.modules[__name__]`, và chạy `runpy` khi gọi CLI.

## Đường dẫn

`src/novel2anima/paths.py` là nguồn duy nhất cho `ROOT`, `db/`, `data/`, `config/`. Các module đã bỏ `sys.path.insert` và không còn phụ thuộc CWD cho `data/sources`, `data/plans`, `data/reviews`, `data/wardrobe`.

## Tests

```text
python -m unittest discover -s tests -v
Ran 107 tests
OK (skipped=1)

python -m unittest discover -s docs\v4\tests -v
Ran 14 tests
OK
```

## Giới hạn còn lại

- Các CLI import legacy vẫn đọc file nguồn trực tiếp trong phạm vi importer; chưa ép toàn bộ qua `import_file_ledger` (PR-03 cung cấp ledger, PR-04 mới hoàn tất package boundary).
- Các wrapper `etl/` sẽ bị xóa ở PR-08 sau khi xác nhận không còn consumer.
- `asset_blob` vẫn deferred.
