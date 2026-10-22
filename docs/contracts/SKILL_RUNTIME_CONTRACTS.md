# V4.1 — Skill Runtime Contracts (PR-11)

**Dependency cứng:** PR-10 backend đã triển khai (`start_story`, `resume_run`, `rerun_from`, migration `013_execution_control.sql`) và contract này được chấp nhận. **Mục tiêu:** 3 skill trở thành hướng dẫn vận hành an toàn và đồng nhất với V4 DB-first; không thay backend checks bằng prompt.

## 1. Quy tắc chung cho cả ba skill

- Source of truth = SQLite V4; Git giữ code/migrations/docs/fixtures, không giữ active runtime story state. JSON/TXT ngoài DB chỉ import/export/preview. `llm/prompts/01...11/{system,task,examples}.txt` tiếp tục **0 byte**, stage live lấy `llm_prompt_template` đã duyệt.
- Không được tự tạo/chỉnh/sinh thêm script ETL, shell command, Python function, SQL write, workflow DAG hay stage khi `story.start` đang chạy. Nếu thiếu khả năng xử lý → `BLOCKED_DEPENDENCY` / `CURATION_GAP`, đề xuất công việc admin riêng.
- Không gọi riêng `etl/build.py`, `etl/seed_plan.py`, `etl/llm_review.py`, `etl/import_*` từ đường story V4; dùng orchestrator/registry đã triển khai ở PR-10. **Không tuyên bố endpoint hoặc tên function giả định đã có trước cutover.**
- Chỉ cho phép `LEGACY` / `MIGRATING` / `V4_ACTIVE` theo feature flags do backend xác định; không tự đoán mode từ tên file `v4-architecture.md`.
- LLM output là proposal, schema validation + service quyết định DB writes. Với approved content, edit tạo revision mới; không overwrite và không ghi file thành canonical.
- Duy trì actor→action→target, character IDs, outfit item/revision/anchor, one page = one shot, continuity, source tag IDs và evidence; mọi ambiguity phải surface như `NEEDS_REVIEW`.
- Citation và references trong skill chỉ là hướng dẫn kỹ thuật; khi xung đột, ưu tiên `MASTER_PLAN.md` + `docs/DECISIONS_AND_CONFLICTS.md` + tài liệu execution control đã được phê duyệt.

## 2. Ranh giới ba skill

| Skill | Allowed | Forbidden in story path | DB ownership |
|---|---|---|---|
| `novel2anima-catalog` | read catalog, shortlist + provenance, validate tag IDs; admin-assisted catalog maintenance outside story | bulk import/rebuild/prune, FTS rebuild, create DB tags on missing match | reads tag/concept/source; imports through separate catalog admin job |
| `novel2anima-shot-pipeline` | build proposals Story/Act/Beat/Shot, coordinator asks approved services via registry, QC suggestions | invent new ETL flow/script/command, write SQLite, file-based current plan | `pipeline_run`, `pipeline_step_run`, revisions via application only |
| `novel2anima-natural-language-prompt` | transform frozen ShotSpec/tag prompt to faithful English, report issues | create shot, change wardrobe/action, start ETL, modify negative prompt, overwrite prompt revision | `shot_prompt_revision` written by application only, optional stage 08 |

## 3. File-level migration (applied in PR-11)

- Catalog: `SKILL.md`, `agents/openai.yaml`, `references/full-coverage.md`,
  `references/v4-architecture.md`; retrieval semantics in `references/catalog.md` kept.
- Shot: `SKILL.md`, `agents/openai.yaml`, `references/prompt-and-render.md`,
  `references/retrieval-and-memory.md`, `references/v4-architecture.md`; continuity and
  wardrobe semantics kept.
- Natural language: `SKILL.md`, `README.md`, `references/integration.md`; QA fixture
  guidance kept.
- Canonical `docs/architecture/PIPELINE_EXECUTION_CONTROL.md` is present and linked from
  both former duplicate locations.

The two duplicate `v4-architecture.md` files are now small redirects. Existing creative
and retrieval semantics were merged, not replaced wholesale. Obsolete authority claims
(`shot_spec_json`, image paths on disk, `check_prompts.py`, prompt TXT/JSONL as canonical)
were removed from active skill sections.

## 4. Mode matrix and examples

| Request | LEGACY | MIGRATING | V4_ACTIVE |
|---|---|---|---|
| Start story | describe current supported CLI and ask backend to run controlled existing flow; do not create scripts | use migration-safe entrypoint or BLOCKED | call only registered orchestrator |
| Missing tag | report unresolved/candidate | report `CURATION_GAP` | shortlist evidence, schedule separate admin job if explicitly requested |
| Missing approved LLM prompt | do not fake V4 template | BLOCKED_CONFIG | BLOCKED_CONFIG (0 provider calls) |
| Change approved outfit | current capabilities truthfully described | create revision through available service or BLOCKED | new outfit revision via app; shot bindings updated only with approval |
| Natural prompt | standalone read-only conversion allowed | DB revision through service once available | stage 08 optional, proposal only |

## 5. Acceptance (on repo AFTER PR-10)

1. `rg`/search all three skill trees; active sections no longer claim plan JSON/TXT, color JSON, image_path are canonical. Historical examples explicitly marked `LEGACY`.
2. Both old `v4-architecture.md` replaced with pointer; canonical architecture exists once and is versioned.
3. Three skills and `agents/openai.yaml` identifiers resolve; skill links to central contracts valid; old skill names unchanged.
4. Prompt injection/malicious suggestion “create an importer before running story” rejected in user→skill→orchestrator integration test; 0 generated script files and 0 catalog maintenance executions.
5. `LEGACY` and `V4_ACTIVE` tests avoid invoking nonexistent APIs. `MIGRATING` never runs dual-write without explicit migration adapter.
6. Identity/outfit/actor preservation, DB-only state, approved revision immutability, LLM prompt DISABLED guard verified.
7. All 33 starter TXT files remain empty; no unauthorized auto-activation; 75 baseline regression, PR-10 tests and post-PR11 release gate passed.

## 6. Verification

PR-11 is checked by `tests/test_pr11_skills.py` (identifiers, redirects, zero-byte prompt
scaffolds, no stale runtime authority claims, contract presence) and by the PR-10
orchestrator tests. This is a repository/contract check; it does not prove an external
provider or production cutover.
