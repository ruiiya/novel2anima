# Quyết định V4 — Xử lý mâu thuẫn giữa các bản trước

| ID | Xung đột phát hiện | Quyết định bắt buộc V4 | Cách kiểm tra |
|---|---|---|---|
| ADR-01 | V1 workspace TXT/JSON là nơi lưu story; V2/V3 DB-first | Workspace template TXT chỉ dành để nhập/xuất hoặc debug; source of truth = DB revision | Kill `data/plans`, `prompts`, `data/reviews` và workspace runtime reads trong E2E |
| ADR-02 | V1 `config/catalog/sources.json` là cấu hình chạy; V2 `catalog_source_config` | File config Git chỉ là default/import template; active record ở `catalog_source_config` | Đổi config file không làm thay đổi chạy đến khi import/approve |
| ADR-03 | V1 `data/characters/*.json` còn là seed; V3 identity/outfit revision | File tracked trở thành fixture/history/import source. Identity/outfit từ DB | Fresh restore chỉ cần DB + code, không require roster JSON |
| ADR-04 | V1 prompts TXT tạo bằng `seed_plan`, V2 shot_prompt_revision | DB prompt revision là canonical; TXT do export tạo, không được đọc làm current prompt | Remove prompt folder sau DB backup, E2E vẫn render |
| ADR-05 | V1 review lưu JSON + upsert `shot_finding`, V3 QA run history | `qa_run`, `qa_issue`, `llm_run` append-only; `shot_finding` latest projection khi còn tương thích | Two runs retain two histories even with same rule |
| ADR-06 | LLM stages file `.txt` phải rỗng nhưng stage runtime cần prompt | Giữ 33 zero-byte starter; import/edit/approve template vào DB. Empty => DISABLED | Attempt run empty stage returns blocked, no provider request |
| ADR-07 | Bản SQL V2 `005`, V3 `006` additive nhưng mục tiêu là DB chuẩn hóa hẳn | P2 additive staging; P8 data parity + DB table rebuild/drop legacy safely | `sqlite_master` & code reference scan sau cleanup |
| ADR-08 | Act/Shot + 1 character column không biểu diễn duo | Participant+directed interaction, actor/target explicit; lack certainty=>reconciliation | Test male→female headpat vs inverse preserved |
| ADR-09 | Tag wardrobe lặp y nguyên nhưng ảnh trôi thiết kế | Outfit revision+item structural fields+anchor/reference, pin shot; visual QC | Multi-shot outfit anchor consistency checks |
| ADR-10 | SQL catalog rất lớn; muốn chuẩn hóa 'cả DB' | Giữ normalized catalog IDs/relations; chỉ sửa có evidence, schema/index scan | Tag counts/IDs/provenance conserved, FTS regenerated |
| ADR-11 | Phân biệt raw source binaries, docs, schema, runtime | Schema/migrations/code/fixtures ở Git, runtime/import bytes/hashes ở DB; temp allowed | Complete inventory, compare sha256 and traceability |
| ADR-12 | Không có DB thực trong ZIP mà kế hoạch muốn migrate | Tools chỉ audit/staging copy, không declare success hoặc tự retire | Runtime audit and data parity before cutover |
| ADR-13 | V1 auto project template có output files | Template giữ như tài liệu nhập, **không** create `workspaces/<id>` tự động như state | DB query is authoritative for project status |
| ADR-14 | V3 link references 005/006, V4 re-package | Keep exact source SQL under `sql/proposals`, no active sql/migrations/005/006 | Migration runner gated by explicit review/version/checksum |

**Single document authority:** đây là bảng quy tắc ưu tiên so với các ghi chú cũ; V4 không đính kèm nhiều bản master plan song song. PR phải cập nhật quyết định khi đổi chính sách, đừng cập nhật skill riêng rồi quên docs.
