# Novel2Moss — DB Contract V4 (Visual Storytelling, schema 008)

## Phạm vi

DB chỉ hỗ trợ **Catalog → Story/Act/Beat → Storyboard/Visual Bible → ShotSpec → Continuity → Natural Prompt → QA → Seal → Export**. Hết trách nhiệm sau khi xuất artifact. Renderer/Image QA không có bảng trong DB và không truy cập DB.

Dự án độc lập, không dùng source, schema, runtime từ repo khác. `CONTENT_POLICY.md` là tệp duy nhất quyết định điều kiện nội dung; Database Contract không tự thay đổi policy.

## Nhóm bảng đang sử dụng

| Nhóm | Bảng |
|---|---|
| Source/Catalog | `source_registry`, `source_records`, `source_record_versions`, `import_runs`, `universes`, `characters`, `character_traits`, `outfits`, `outfit_parts`, `catalog_tags`, `character_tags`, `catalog_captions`, `vocabulary`... |
| Story | `stories`, `story_sources`, `story_revisions`, `story_roles`, `story_castings`, `acts`, `beats`, `story_events` |
| Storyboard | `storyboards`, `storyboard_shots`, `event_shot_mappings`, `shot_dependencies`, `storyboard_seals` |
| Visual Bible | `story_locations`, `story_props`, `visual_style_profiles`, character anchors trong storyboard plan |
| Shot/Continuity | `shots`, `shot_participants`, `shot_interactions`, `continuity_snapshots` |
| **Prompt canonical** | **`shot_prompts`**: `id`, `shot_id`, `revision`, `language`, `prompt_text`, `prompt_sha256`, `shot_spec_sha256`, `supersedes_prompt_id`, `created_at` |
| QA | `qa_reports` subject active `STORY/SHOT/PROMPT` |

Migrations `001–006` giữ nguyên, migration `007_natural_prompts.sql` thêm bảng prompt, và rebuild QA constraint để hỗ trợ `PROMPT` **vẫn giữ `LAYOUT` cũ ở DB cho lịch sử**, không cho phép lệnh `save-qa` mới dùng `LAYOUT`.

Migration 008 chỉ thêm bảng/storyboard snapshot append-only. Mỗi slot có stable key, order số, branch, predecessor và context hash. Seal chứa exact shot_id/prompt_id/qa_id và snapshot hash; các projection phải khớp plan hash. Chi tiết: `VISUAL_STORYTELLING.md`.

**Bảng lịch sử (không ghi mới):** `shot_layouts`, `shot_layout_items`, `layout_exports`, `layout_templates` là phần còn lại của V2 để tránh xóa dữ liệu. Không còn compiler, bbox hoặc JSON Layout trong đường dẫn nghiệp vụ đang hoạt động.

## Hợp đồng đọc/ghi

- `story_sources` immutable; lưu nguồn nguyên văn và nhãn.
- `story_roles` ổn định trong cả Blind/Non-Blind; casting thay đổi theo `from_revision/until_revision`.
- ShotSpec mới có Shot revision riêng; `shot_participants`/`shot_interactions` tham chiếu role cùng Story; continuity không ghi đè trái phép.
- Mỗi Shot có `shot_prompts` theo revision, text UTF-8. Chạy lại cùng nội dung trả cùng prompt ID; thay đổi text tạo revision mới, và bản cũ bất biến.
- Prompt text **không phải JSON**; JSON manifest/QA giữ riêng ngoài positive prompt.
- Khi đổi casting/ShotSpec, tái xác nhận context và sinh prompt mới; không coi prompt trước đó tự động hợp lệ.
- `qa_reports` chỉ append-only. `PASS` phải có bằng chứng đối chiếu, không suy từ hash/validator thuần cấu trúc.
- `export-bundle --prompt-id` xuất `natural.prompt.txt`, manifest, fidelity report. V4 `export-story-prompts --story-id` chỉ dùng seal của storyboard mới nhất, từ chối plan stale/unsealed, không tự lấy revision mới nhất của Shot/Prompt. Chỉ export lịch sử nếu chọn storyboard-id tường minh. Legacy story chưa có storyboard dùng quy tắc V3.
- `prompts.all.jsonl` và `prompts/A01.jsonl` là JSON Lines + dòng trống để gom Shot, nhưng trường `prompt` luôn là **string**, không phải JSON Layout.

## Quy tắc vận hành

- Dùng migration quản lý phiên bản, prepared SQL, transaction, foreign key và integrity check.
- Không sửa migration đã chạy. Khi nâng từ V2/V3, chạy `init` áp dụng các migration còn thiếu tới 008; dữ liệu cũ được giữ lại.
- `save-natural-prompt` đọc `.txt`, không chấp nhận object JSON hoặc markdown code fence. `export-bundle` lấy `--prompt-id`, không dùng `--layout-id`.
- `seed` chỉ vocabulary và source registry, không tải dataset ngoài và không seed layout templates mới.
- Không quản lý render_jobs/assets/QA RENDER, model settings, seed hoặc ảnh trong SQLite.

Chi tiết lệnh: `docs/novel2moss/DATABASE_OPERATIONS.md`. Quy tắc văn phong: `docs/novel2moss/MOSS_NATURAL_PROMPT.md`.
