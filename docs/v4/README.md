# Novel2Anima V4

## Trạng thái triển khai

| PR | Nội dung | Trạng thái |
|---|---|---|
| PR-00 | Inventory/baseline | hoàn tất |
| PR-01 | Migration runner, schema version | hoàn tất |
| PR-02 | Relational backfill | hoàn tất |
| PR-03 | Import ledger | hoàn tất |
| PR-04 | Domain package (`etl/` removed) | hoàn tất |
| PR-05 | Story/wardrobe/continuity invariants | hoàn tất |
| PR-06 | 11 LLM contracts, prompt registry | hoàn tất |
| PR-07 | Compile, render BLOB, QA history | hoàn tất |
| PR-08 | Legacy cleanup + docs/skills | hoàn tất |
| PR-09 | Release gate | **READY** trên staging; chưa render Anima thật/cutover |
| PR-10 | Pipeline execution control (static DAG, idempotent runs, `catalog_job`) | hoàn tất code + migration `013`; chưa provider/render thật |
| PR-11 | Skill runtime alignment V4.1 | hoàn tất merge, giữ 3 skill ID |

> PR-10/11 gate: `python scripts\release\release_gate_v41.py --db <db>
> --report evidence\pr-10\release_gate.json`. `production_signoff` vẫn `false` cho đến
> khi có external provider, Anima render thật và cutover/rollback drill.

## Nguồn chuẩn

- Kiến trúc: [`MASTER_PLAN.md`](MASTER_PLAN.md)
- Backlog/acceptance: [`docs/TASKS_FOR_CODEX.md`](docs/TASKS_FOR_CODEX.md)
- DB invariants: [`docs/DB_NORMALIZATION.md`](docs/DB_NORMALIZATION.md)
- LLM contracts: [`docs/LLM_PIPELINE_CONTRACTS.md`](docs/LLM_PIPELINE_CONTRACTS.md)
- Refactor rules: [`docs/SOURCE_REFACTOR.md`](docs/SOURCE_REFACTOR.md)
- Legacy disposition: [`P8_LEGACY_DISPOSITION.md`](P8_LEGACY_DISPOSITION.md)
- Release gate: [`RELEASE_GATE.md`](RELEASE_GATE.md)
- Backup/recovery: [`BACKUP_RECOVERY.md`](BACKUP_RECOVERY.md)

## Layout

```text
src/novel2anima/
  catalog/       tag catalog, importers, maintenance, retrieval
  storage/       migrations, ledger, repositories, assets
  story/         logic, beat planner, action planner
  wardrobe/      wardrobe rules
  continuity/    rules and inference
  prompting/     canonical tag compiler
  llm/           contracts, registry, adapters
  render/        render persistence
  quality/       prompt/story/shot/QA rules
sql/migrations/  additive + data-preserving migrations
docs/v4/         authoritative V4 documentation
```

## DB

- Live: `db/novel_anima.db` (catalog; no project rows after reset).
- Staging: `db/backup/pr-01/staging_live.db` (safe target for V4 migrations).
- Render bytes: `asset_blob`, content-addressed by SHA-256.
- Prompt authority: `shot_prompt_revision`; exported `.txt` is not authoritative.

## Commands

```text
python -m unittest discover -s tests -q
python -m unittest discover -s docs/v4/tests -q
python scripts/qa/verify_p8_disposition.py --db <staging.db>
PYTHONPATH=src python -m novel2anima.storage.migrations --db <staging.db> --migrations sql/migrations
```

CLI dùng package module: `python -m novel2anima.<domain>.<module>`. Không còn
`etl/` shim hay reader legacy.
