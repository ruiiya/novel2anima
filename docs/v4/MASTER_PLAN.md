# MASTER PLAN V4 — Chuẩn hóa toàn bộ Novel2Anima (Repository + Database + LLM + Pipeline)

**Phiên bản:** V4 / 2026-10-22  
**Quy tắc:** V4 này **thay thế** kế hoạch V1–V3, nhưng kế thừa các SQL DRAFT 005–006 và mapping đã được kiểm chứng. Không thực hiện thay đổi phá hủy lên DB/repo nguồn ở giai đoạn thiết kế.

## A. Đầu vào và số liệu được xác minh

- Source ZIP `novel2anima_git_sql_20261022_090622.zip`: 80 file, 29 Python `etl/`, 3 skills; baseline 75 pass, 1 skip. Commit snapshot `e64835f388a5a87a59d5706dd2ca7d15b6187f4f`; file dirty `etl/check_prompts.py`, `etl/seed_plan.py`, `etl/story_logic.py`, `skills/novel2anima-shot-pipeline/SKILL.md`; untracked `765/`.
- SQL snapshot mô tả **23 đối tượng dạng bảng** (trong đó có `visual_concept_fts` virtual FTS), DB manifest ~360,968,192 bytes: `tag` 1,208,773; `tag_source` 1,479,995; `project` 31; `character_profile` 574; `act` 77; `shot` 7,099; `generation` 0. **Chưa kiểm chứng với DB sống**.
- 18 nhóm dữ liệu ngoài DB, gồm plan/review/prompts/wardrobe/characters/images/import reports; V4 không coi file này là nguồn chân lý.
- 11 bước LLM; giữ 33 file `.txt` zero-byte làm scaffold nhập instruction. Tất cả stages bị **DISABLED** cho đến khi prompt+schema hợp lệ được phê duyệt trong DB.

## B. Kiến trúc cuối cùng — một DB là nguồn nghiệp vụ chuẩn

1. **SQLite**: catalog; config active; projects/story/characters/outfits/acts/shots; participant + interaction actor→target; ShotSpec; continuity; prompt revision; LLM history; render assets BLOB; QA immutable runs/findings; migration/import ledgers; pipeline runs.
2. **Source Git**: Python logic, migrations có version/checksum, JSON Schema, tests/fixtures, skills/docs, prompt `.txt` rỗng. `config/` chứa **defaults/mẫu** được import vào DB theo lệnh; không đọc như active runtime config sau cutover.
3. **Filesystem**: import/export/cache/temp log/output cho ComfyUI. Phải pin nguồn/generation ID trong DB. File xuất ra ngoài không tự cập nhật ngược DB.
4. **LLM**: chỉ nhận input đã truy xuất/được giới hạn top-k từ DB; trả JSON có schema version và stable IDs, application validation và DB transaction quyết định ghi. LLM không chỉnh trực tiếp bản approved và không tự SQL-write.
5. **Render**: thử nghiệm hỗ trợ model thực (Anima); prompt/seed/checkpoint/reference/anchor pin theo revision; image bytes lưu `asset_blob`, export chỉ là bản sao có thể dựng lại. Cần benchmark DB BLOB, backup/restore trước khi bắt buộc lưu ảnh lớn.

## C. Quy tắc toàn cục không được thay đổi

- Một page/panel = **một shot**; story ngắn thường solo hoặc duo (1girl + 1boy), mở rộng hợp lý nhưng không tự sinh 3+ nhân vật.
- Directed interactions có `actor_character_id` và `target_character_id` trong cùng shot; `male headpat female` không được đảo. Không suy vai từ he/she hay thứ tự tag; không đủ chứng cứ → NEEDS_REVIEW.
- Outfit cụ thể là **revision + item cấu tạo + ảnh anchor**, không coi `lingerie` hay một chuỗi tag lặp lại là bảo đảm đồng nhất. Pin outfit revision theo từng shot/nhân vật và so sánh visual QC.
- Mọi revision approved/published bất biến. Edit tạo revision mới (không thay JSON cũ), mọi generation pin đúng revision. History LLM/QA append-only, projection mới nhất có thể dựng lại.
- Chỉ các JSON phi quan hệ linh hoạt mới nằm trong cột JSON có schema, không dùng JSON làm nơi lưu FK duy nhất. UUID/ID cần nhất quán, FK check ở mọi writer.
- Lấy checksum SHA-256 trước/sau import; đo row counts và khóa ID, mọi ngoại lệ explicit reconciliation. Không bao giờ dùng `git clean`, `git reset`, destructive rebuild hoặc tự xóa file raw khi chưa verify.

## D. Thiết kế source đích (không copy skeleton đè code)

```text
Novel2Anima/
├── README.md, pyproject.toml
├── src/novel2anima/
│   ├── catalog/{importers,retrieval,maintenance}/
│   ├── story/ wardrobe/ continuity/ prompting/
│   ├── llm/ quality/ render/ pipeline/ storage/
├── sql/{schema_v1.sql,migrations/}
├── config/                  # defaults và editor/export, không phải active store
├── llm/{prompts,schemas}/   # 11 prompt skeleton và schema, runtime templates = SQLite
├── scripts/{migrations,catalog,diagnostics,qa}/
├── tests/{unit,integration,contract,regression,fixtures}/
├── skills/                  # agent instructions ngắn; không copy docs lớn
├── docs/{architecture,contracts,db,decisions,guides,audits}/
├── data/                    # fixtures + explicit import/export/cache, không canonical
├── workspaces/              # tùy chọn; imported/exported previews, KHÔNG active state
└── db/                      # SQLite, snapshots, backups (gitignored)
```

## E. Lộ trình tổng hợp, thứ tự phụ thuộc và điều kiện Done

| Phase | Việc thực hiện | Tiền đề | Gate bắt buộc |
|---|---|---|---|
| P0 | Baseline source + DB + toàn bộ external data, backup/restore test | Repo + DB runtime | Git dirty/untracked bảo toàn; snapshot Backup API, SHA ledger, `integrity_check` |
| P1 | Chốt contracts/ownership & data model V4; phân loại 121 mapping | P0 | Review 23 bảng, 18 external groups, 80 source files; quyết định unresolved không bị đoán |
| P2 | Thiết kế runner migrations thật từ 005/006 DRAFT; schema tests/triggers/index/version | P1 | Apply copy staging được, checksum drift rejected, FK/integrity OK, restore/rollback diễn tập |
| P3 | Backfill relations deterministic từ DB cũ (ID stable), ledger exceptions | P2 | Counts/PK/FK parity; duo/actor và wardrobe unknown → reconciliation queue |
| P4 | Import toàn bộ JSON/TXT/assets vào bảng canonical theo SHA | P2–P3 | 100% nguồn kiểm kê có trạng thái imported/duplicate/blocked và lý do; byte hashes verified |
| P5 | Refactor 29 script `etl/`, source modules, DB repository/service, shims CLI | P3–P4 | Old CLI compatible; file-based inputs chỉ qua import; regression 75 baseline pass |
| P6 | LLM prompt registry/contract (11), wardrobe/actor lock, pipeline orchestrator | P5 | Stage không có system/task không chạy; LLM run history; solo/duo integration |
| P7 | Render/asset provenance, visual QA, targeted revision; optional NL prompt | P6 | Exact shot/outfit/prompt/model/reference pin; recreate assets via DB SHA |
| P8 | Retire legacy **sau** parity: rebuild obsolete schema/index/FTS; chuẩn hóa code/docs/skill | P5–P7 | Zero legacy runtime reads/writes; no data loss; final DB schema mapping signed |
| P9 | Pilot + cutover + backup restore + rollback drill + signoff | P8 | DB-only restore + E2E output; full QA; performance benchmark; no unowned file state |

Các phase P2–P4 có thể phát triển độc lập nhưng phải chốt data contracts và backup P0 trước. Không thực thi bất kỳ giai đoạn phá hủy nào khi gate trước chưa đạt.

## F. DB normalization — những thay đổi cốt lõi

- Giữ tag, alias, role, relations, concepts, FTS & original provenance; không bulk rebuild >1M tags khi chưa có lý do định lượng.
- Chuẩn hóa `character_profile.identity_json` → `character_identity_revision`, `outfit_json` → `outfit_revision` + `outfit_item`, `shot.shot_spec_json` → `shot_spec_revision`, `shot.character_id` → `shot_participant`, interactions actor→target, bindings outfit revision.
- `project_document_revision` là story/brief/plans canonical; beats là thành phần có thứ tự và version (ban đầu document revision có schema; cân nhắc bảng beat riêng khi query thực yêu cầu). Không tạo hai nguồn authoritative cho cùng entity.
- `shot_prompt_revision`, `shot_prompt_tag`, `shot_prompt_spec` lưu nguồn/biên dịch; `llm_prompt_template` + `llm_run` giữ các instructions và lần gọi; `qa_run` + `qa_issue` không ghi đè findings.
- `asset_blob` là canonical ảnh/reference, `generation_asset` nối ảnh render; `generation_provenance` pin prompt revision; `import_batch` ledger nguồn và data; `continuity_assertion` phân biệt inferred/user-approved.
- P8 quyết định retire `shot.character_id`, `generation.image_path`, `act_publication.prompt_path`, `shot_finding` mutable projection, duplicated JSON snapshot; **không drop trong P2–P7**.
- `model_profile`, observations/FTS có thể đang 0 rows, không xóa vì vắng dữ liệu.

## G. LLM execution (không lưu canonical state trong folder txt)

User chat → 01 brief → 02 story → 03 character → 04 wardrobe → 05 act/beat → 06 shot direction → deterministic DB retrieval → 07 tag selection → compiler Python → 08 NL optional → 09 semantic review → render → 10 visual QC → 11 targeted revision.

Mỗi `llm_run` lưu `pipeline_run_id`, template_id/revision, execution_key, model/provider, request/response, validation status, input revision IDs/hashes và QA. LLM chỉ trả đề xuất cấu trúc; thông qua validators mới tạo bản draft mới, người dùng approve khi cần. `system.txt` / `task.txt` / `examples.txt` zero-byte không được auto-activate.

## H. Quản trị rủi ro và quyết định cần xác minh ở DB runtime

1. Filesystem đang có plan/reviews/prompts nào, có bao nhiêu ảnh và kích thước bao nhiêu? Snapshot không chứa chúng.
2. Duo shots thiếu character mapping? `shot.character_id` chỉ cho một nhân vật. Không tự suy actor/target từ caption/tag.
3. Phân loại outfit cũ có item, reference anchor nào có thể nhận dạng? Không để `outfit_revision` giả được approve.
4. V3 SQL DRAFT chỉ mới chạy test in-memory/small; phải kiểm thử `PRAGMA foreign_keys=ON`, WAL, triggers và SQLite version thật.
5. DB BLOB làm tăng backup/restore và write contention; benchmark nhất là Anima renders; cần chính sách asset chunk/thumbnail và SQLite size limits.
6. Conflicting aliases và color precedence: shot explicit > act explicit > catalog choice với lingerie > heuristic. Cần query provenance và approved status, không tạo độ chắc chắn giả.
7. Nếu nguồn asset lớn không thể nhúng DB thực tế, phải trình trade-off cho người dùng **trước** khi thay đổi nguyên tắc DB-only recovery; không tự đổi thiết kế.

## I. Tài liệu phụ trách và định nghĩa hoàn thành

- `docs/DECISIONS_AND_CONFLICTS.md`: quyết định V4 khi V1–V3 xung đột.
- `mappings/MASTER_MAPPING.csv`: coverage 121/121, mỗi hàng phải có status owner khi thực thi.
- `docs/TASKS_FOR_CODEX.md`: tasks từng pha có file impact, tests, acceptance.
- `docs/TEST_CUTOVER_ROLLBACK.md`: test evidence, rollback drills và final signoff.

**Done chỉ khi** code đọc/ghi SQLite canonical, toàn bộ dữ liệu runtime được kiểm kê và migrate/được xử lý ngoại lệ, schema cuối không còn bảng/cột trùng vai trò chưa có lý do, pipeline solo/duo/wardrobe/LLM/QA/render chạy, có thể restore từ DB backup và source code mà không cần file JSON/TXT ngoài, tất cả tests và cutover gates pass. Bộ V4 hiện tại **chưa đáp ứng Done**: nó là thiết kế được đóng gói, không phải migration dữ liệu đã thực thi.
