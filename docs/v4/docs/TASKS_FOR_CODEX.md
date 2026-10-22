# V4 — Execution backlog for Codex (implementation is not in this ZIP)

**Mục tiêu:** triển khai từng PR nhỏ; sau mỗi PR báo danh sách file thay đổi, tests và số liệu parity. Không apply trên production DB hoặc xóa file không có approval.

## PR-00: Inventory/baseline, không sửa source

**Input**: repo thật + DB + ignored files. **Tasks**: run git status/diff, backup API, hash manifest, audit DB; `inventory_external_readonly.py`; snapshot 80 tracked paths vs current. **Outputs**: `evidence/runtime_inventory.json`, diff, DB backup+restore report. **Done**: no source modifications; one-to-one inventory; unknowns listed.

## PR-01: DB contracts/migration runner

**Files**: new `src/novel2anima/storage/migrations.py`, schema version table, `sql/migrations/005_*` and `006_*` AFTER review, tests. **Tasks**: adapt proposals, add transactional version+checksum checks, FKs and on-DB-copy migration; never blindly replay DRAFT. **Done**: checksum mismatch abort, restore test, `integrity_check` OK.

## PR-02: Data relational backfill

**Files**: `src/novel2anima/storage/repositories/*`, `scripts/migrations/backfill_*`; structured tests. **Tasks**: draft identity/outfit/shot specs, ensure actor-target needs explicit source, gap queue. **Done**: all known IDs preserved, null/unknown flagged, no inferred duo actor substitution.

## PR-03: External import infrastructure

**Files**: `src/novel2anima/storage/import_ledger.py`, parsers for plan/prompt/review/wardrobe/catalog/assets, CLI `scripts/migrations/import_legacy.py`. **Tasks**: source classification, SHA + parser version, idempotent import, staged errors. **Done**: file source ledger complete; no hidden working directory dependency.

## PR-04: Domain package and compatibility shims

**Files**: 29 `etl/*.py` to `src/novel2anima/**`, `etl/` thin wrappers, `pyproject.toml`, tests. **Tasks**: move one module at a time following `mappings/REPOSITORY_80_FILES.csv`, update imports and new DB persistence. **Done**: original CI pass; CLI parity; all file data reads go through import/export.

## PR-05: Story/wardrobe/continuity invariants

**Files**: `story`, `wardrobe`, `continuity`, `storage`, schema tests. **Tasks**: immutable revisions, item slots, outfit anchor, actor→target + participant/project invariant, user vs inferred state. **Done**: solo+duo+headpat/outfit drift test pass.

## PR-06: 11 LLM stages & prompt registry

**Files**: `llm`, `pipeline`, `llm/schemas`, `llm_prompt_template` writer APIs and tests. **Tasks**: import human-authored instructions into DB with explicit approval; block stages with empty instructions; output schema validators, errors and retry keys. **Done**: 11 contract tests and no unapproved stage invoke; no unaudited write.

## PR-07: Prompt compile, optional natural language, render & QA

**Files**: `prompting`, `render`, `quality`; DB asset repo. **Tasks**: compile from canonical DB; pin exact inputs; store render BLOB and SHA; QA history; targeted revisions. **Done**: replay from DB only; asset byte SHA match; no actor reversal.

## PR-08: DB cleanup & docs/skills

**Files**: new data-preserving table rebuild migrations, `docs`, `README`, skills. **Tasks**: remove actual legacy columns/tables only after all reads/writes gone, consolidate duplicate architecture docs, compare indexes/FTS. **Done**: final schema no duplicate authoritative stores, all 23 legacy tables disposition verified.

## PR-09: Release gate

**Files**: final tests, backup/recovery guide and report. **Tasks**: cutover/rollback drill with realistic DB+images, full E2E, benchmark. **Done**: signed migration ledger, no unresolved required external data, rollback test pass.

## Reporting template per PR

`PR`, `scope`, `files changed`, `db migrations`, `data counts`, `tests`, `new blockers`, `rollback`, `approval state`; report any `SKIP` as incomplete, not pass. Implement per-PR instead of asking Codex to restructure the entire repo in one unreviewable change.
