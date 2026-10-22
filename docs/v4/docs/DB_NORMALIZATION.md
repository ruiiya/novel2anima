# Chuẩn hóa toàn bộ SQLite V4

## Status và giới hạn

`sql/reference/*` là snapshot legacy đã cung cấp, `sql/proposals/005_db_first_DRAFT.sql` và `006_normalization_DRAFT.sql` là tài liệu SQL kiểm thử cấu trúc, **không phải final production schema và không được apply trực tiếp vào DB thật**. Cần DB sống + WAL + external datasets để finalize actual ALTER/rebuild/trigger/index + constraints.

## Domain và dữ liệu canonical

| Domain | Legacy | Canonical V4 | Xử lý |
|---|---|---|---|
| Catalog | tag/source/alias/role/relation/content label | Giữ cấu trúc, bổ sung `tag_relation_source`, `tag_alias_conflict` | Bảo toàn IDs; không rebuild mass |
| Concept | visual_concept, concept_tag/relation, FTS | Giữ bản ghi; FTS rebuildable | Kiểm tra FTS parity |
| Project | project | project + `project_document_revision` | version brief/story/plan |
| Character | `character_profile.identity_json` | `character_identity_revision` | legacy column projection trong transitional |
| Wardrobe | `character_profile.outfit_json` | `outfit_revision`, `outfit_item`, `shot_outfit_binding`, asset anchor | version/pin + FK |
| Shot | `shot.character_id`, shot_spec_json | `shot_participant`, `shot_interaction`, `shot_spec_revision` | actor/target thuộc đúng shot, đúng project |
| Prompt | prompt files, generation.prompt | `shot_prompt_revision`, `shot_prompt_tag`, `shot_prompt_spec` | canonical tag + optional NL, pin input |
| LLM | code/skills/reviews files | `llm_prompt_template`, `llm_run`, `pipeline_run`, `pipeline_step_run` | immutable history + idempotency |
| QA/continuity | shot_finding, shot_state, observations | `qa_run`, `qa_issue`, `continuity_assertion` (+ projections) | không mất lịch sử |
| Image/render | generation.image_path, external files | `asset_blob`, `generation_asset`, `generation_provenance` | BLOB SHA + pinned prompt/model |
| Config/import | etl/sources.json, reports/manifest | `catalog_source_config`, `n2a_setting_revision`, `import_batch`, `import_batch_file` | default Git → active DB |

## Relationship integrity

`project → act → shot`; `project → character_profile → identity/outfit revisions`;
`shot_participant(shot_id,character_id,slot_no)` cross-project gated;
`shot_interaction(shot_id,actor_character_id,target_character_id)` references **participants of this shot**, actor and target must differ when action directed;
`shot_outfit_binding(shot_id,character_id,outfit_revision_id)` must match both participant/owner;
`generation_provenance(generation_id,shot_prompt_revision_id)` prompt shot must match generation shot.

Một prompt attempt phải pin exact approved ShotSpec revision + outfit revision(s) + tag catalog snapshot/version + model/seed (ngay cả khi v3 DRAFT chỉ pin một phần). Missing pin là **P2 production schema gap**, không được tuyên bố reproducible.

## DB constraints/indexes/migration rules

- `PRAGMA foreign_keys=ON` **mỗi connection**; `PRAGMA busy_timeout`, WAL theo điều kiện; backup dùng Backup API.
- Migrations versioned, SHA256, ordering, guards against drift; journal có audit timestamp/result; không rerun arbitrary DDL trong ETL startup. DDL copy staging run first.
- Approved revisions immutable (`UPDATE` content blocked); creation of new revision là transaction; `status='retired'` có quy tắc riêng và không xóa historical links.
- Dữ liệu key (`project_id`,`shot_id`,`character_id`, `outfit_revision_id`) nằm relational, JSON chỉ chứa fields linh hoạt có `schema_version`, JSON_VALID; app validates full schema.
- Kiểm duplicate indexes và composite FK support; query-plan test trên SQLite data thực (`tag`, `tag_source`, `shot_participant`), đo write overhead trước tạo index.
- Triggers, cross-project checks, reference ownership phải test cả `INSERT/UPDATE/DELETE`, concurrent pipeline attempts và revisions. V3 in-memory tests không phủ hết.
- SHA-256 của `asset_blob.body` phải verify trong code: DB check chỉ so `length(body)` và metadata; triggers không tự hash BLOB.
- Dùng soft archive/restrict với records lịch sử; avoid destructive CASCADE approval chains.

## Phân loại 23 legacy tables

Chi tiết nằm ở `mappings/LEGACY_23_DB_TABLES.csv`. `visual_concept_fts` là FTS virtual table; `model_profile`/generation/observations có thể trống, vẫn giữ đến khi evidence rõ. 005/006 **chỉ add**, cleanup phải có migration riêng tại P8 sau khi `legacy code reads = 0`.

## Migration/cleanup phases

1. **P2:** design final 005/006 runner schema/checksum; apply only on backup-created staging copy; rollback tested.
2. **P3:** deterministic backfill identity/outfit/spec/participant from `character_id` and relation source; report unmapped duo and invalid JSON, do not guess actor-target.
3. **P4:** import external file hashes + structured data + BLOB assets; dedupe, preserve source provenance; client becomes DB-only.
4. **P8:** remove duplicate `shot.character_id`, `character_profile.*_json`, `generation.image_path`, file-based publication as authoritative (potential full table rebuild). Preserve old facts in archive/ledger; FTS/index rebuild only after parity.
5. **P9:** `PRAGMA integrity_check` OK; FK violations empty; counts/revision IDs preserved; recovery from database+source works; performance/backup latency accepted.

**Không được bỏ qua P8**: chỉ thực thi DDL thêm bảng chưa đồng nghĩa chuẩn hóa toàn bộ DB.
