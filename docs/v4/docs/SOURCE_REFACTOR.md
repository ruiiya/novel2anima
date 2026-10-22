# Chuẩn hóa source/skill/test/CLI

## Mục tiêu

Tách 29 script `etl/` đang lẫn catalog ingestion, domain, migration, LLM review, QA và CLI thành package `src/novel2anima/` + `scripts/`. Bảng `mappings/REPOSITORY_80_FILES.csv` có đủ 80 paths được chụp trong ZIP; file thay đổi/untracked cần **đối chiếu với checkout thật trước khi dùng `git mv`**.

## Quy tắc dịch chuyển

1. P0 bảo toàn dirty files và untracked `765/`; dump git diff, archive các workspaces không track. Không `git clean/reset`.
2. Tạo pyproject package và import topology. Không move 29 script một lượt; refactor từng domain, lưu CLI wrappers `etl/foo.py` có thông điệp deprecation đến khi parity. Dùng `python -m ...` hoặc console scripts thay cho `sys.path.insert`.
3. Tách repository access: `storage` chỉ SQL/transaction; domain không tự mở connection tùy tiện. DB writer phải bảo đảm `PRAGMA foreign_keys=ON`, transactions/idempotency, migrations approved.
4. `catalog` dùng SQL search/top-k thay gửi toàn bộ tag tới LLM. Giữ importer provenance và content_scope. `story` + `wardrobe` + `continuity` giải quyết logic trước khi compile.
5. `prompting` giữ canonical Danbooru-tag compiler; natural language conversion tùy chọn và lưu riêng (không overwrite tag prompt).
6. `render` là adapter thực khi đã kiểm thử Anima/workflow, không tạo stub rồi tuyên bố done. Skills chỉ mô tả thao tác; specs/version ở docs và tests.
7. `data/` và `workspaces/` sau cutover chỉ còn fixture/import/export/cache, không có quyền quyết định current plan/outfit/prompt.
8. Không tự động xóa legacy. Scan grep sau refactor cho `data/plans`, `data/reviews`, `prompts/*.txt`, `.image_path`, `outfit_json`, `--plan-json` và xác minh mỗi chỗ chỉ là importer/exporter/compat.

## Naming và coding standard

- Package `novel2anima`; modules snake_case; tables/columns snake_case, PK `id` trong bảng có row identity; giao bảng many-to-many composite PK nếu hợp lý; FK suffix `_id`.
- Mỗi service có input/output contract version; enum/status dùng domain constants; migration riêng cho schema chứ không tự chạy từ `build.py`.
- Python test tách `unit/`, `contract/`, `integration/`, `regression/`; chỉ fixtures mẫu ở Git. Không trỏ test mặc định đến production DB.
- `llm/prompts/*.txt` luôn 0 byte trong Git; prompt runtime ở DB; JSON Schemas trong Git versioned.
- 3 skills giữ facade mỏng trỏ tới `docs/`; hai bản `v4-architecture.md` trùng byte gộp thành một tài liệu, cập nhật reference links.

## Tập nghiệm thu kỹ thuật

- Original 75 unittest pass (1 skip có lý do trên source ZIP); bổ sung tests parity CLI cũ/mới.
- 29 scripts có mapping owner và final wrapper/entrypoint (không script orphan).
- Không còn bất kỳ runtime FS reads/writes của domain ngoài importer/export/cache.
- Khi xóa folder `prompts` và `data/plans` trên **workspace copy** sau migration, generation result giữ nguyên với cùng seed/model/config.
- Tài liệu README phản ánh implemented vs planned; skill không quảng bá render/natural-language integration như đã chạy nếu chưa có adapter.
