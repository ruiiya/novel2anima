---
name: novel2moss-orchestrator
description: "Điều phối pipeline Novel2Moss từ Story đến MOSS-Image Layout với các cổng bảo toàn nội dung, lựa chọn tool linh hoạt, phát hành và bàn giao."
---
# Novel2Moss — Điều phối toàn bộ workflow

> **Policy nội dung bắt buộc:** Đọc `docs/novel2moss/CONTENT_POLICY.md` trước khi xử lý. Mọi quyết định nội dung tuân theo scope và phiên bản tại đó; skill này không tự đặt chính sách khác.

## Khi sử dụng

Khi người dùng muốn khởi tạo/tiếp tục dự án Novel2Moss, lập nhiều Act, tạo Shot, xuất prompt MOSS Layout hoặc chạy QA toàn bộ dự án.

## Tài liệu bắt buộc đọc

Đọc **trước tiên** `docs/novel2moss/CONTENT_POLICY.md`, sau đó `docs/novel2moss/PROJECT_BOUNDARIES.md`, `docs/novel2moss/CONTENT_FIDELITY.md`, `docs/novel2moss/TOOL_FLEXIBILITY.md`, `docs/novel2moss/MOSS_LAYOUT.md`. Chỉ policy trung tâm được quyết định điều kiện nội dung; các hợp đồng khác quản lý hình học, dữ liệu, công cụ. Nếu thiếu policy, báo thiếu hợp đồng và không thực hiện `PROMPT_DERIVATION` hoặc `RENDER_DISPATCH`.

## Workflow

1. **Kiểm tra trước, không giả định:** Khảo sát repository thật, schema, văn bản nguồn, profile nhân vật đã xác nhận, revision, tool hiện có và artifact đã sinh. Chỉ thao tác trong Novel2Moss. Coi source và tầng lưu trữ là mới hoàn toàn cho đến khi kiểm chứng tại repository này; không fallback sang code/schema dự án khác.
2. **Xác lập nguồn:** Tiếp nhận mọi Story, giữ nguyên văn bản truyện và nhãn/tag gốc, kể cả NSFW; tuyệt đối không làm nhẹ hoặc tự đổi mức. Blind Mode không chặn nhập hay lập kế hoạch do thiếu tên nhân vật hoặc metadata chưa rõ. Tách kiểm tra tạo prompt khỏi quản lý nguồn; không tự bịa tuổi, tình trạng đồng thuận hay điều kiện runtime.
3. **Đề xuất Story và DỪNG chờ chốt:** Dùng `novel2moss-story-planner` soạn brief gồm premise, nhân vật/vai trò, nhãn nội dung, scope và dàn ý Act/Beat. Với Non-Blind, tra `novel2moss-character-profile` trước và nêu casting đề xuất trong brief. Trình bày brief cho người dùng. **Không** tạo `stories`, `story_roles`, `story_castings`, `story_revisions`, Act/Beat/Event trước khi người dùng xác nhận rõ ràng. Nếu chưa chốt, trả `WAITING_FOR_STORY_APPROVAL` và dừng.
4. **Ghi Story đã chốt:** Sau xác nhận, tạo Story + roles + casting (Non-Blind: casting trước Shot) rồi lưu plan/Act/Beat/Event đúng bản đã duyệt. Không thêm cảnh hoặc sự kiện ngoài phạm vi đã chốt.
5. **Mô tả Shot** bằng `novel2moss-shot-spec`: actor, target, biểu cảm, outfit, state, chiều hành động và camera. Kế thừa trạng thái bằng `novel2moss-continuity`.
6. **Xác định nhân vật** bằng `novel2moss-character-profile`; chỉ dùng `novel2moss-blind-cast` khi danh tính thật sự chưa được chọn.
7. **Lập Layout** bằng `novel2moss-layout-planner`: tạo draft pixel từ góc trên trái, rồi biên dịch tất định ra MOSS Layout JSON theo tâm. Đây là **định dạng prompt canonical** trong Novel2Moss V1. Có thể xuất thêm `render.prompt.json` đa bbox cho renderer nhận scene schema `scene_type/gen_brief/elements`; companion này không thay canonical, không đổi nội dung và không dùng cho compiler MOSS-Image chính thức. Không fallback sang tag-only/hybrid/caption-only nếu chưa có thay đổi kiến trúc được người dùng duyệt.
8. **Qua cổng QA** bằng `novel2moss-fidelity-qa`: kiểm tra mạch truyện, hình học, ánh xạ nguồn→prompt, chống grid cho prompt đa bbox và xác minh quyết định `PROMPT_DERIVATION` từ policy (không tự tái diễn giải điều kiện).
9. **Export bundle** bằng `n2m_db.py export-bundle`: ghi `layout.prompt.json`, `prompt.manifest.json`, `fidelity_report.json`; kèm `render.prompt.json` nếu dùng renderer đa bbox. **Sau khi xuất đủ bundle, gộp toàn bộ prompt hiện hành của Story vào một file `prompts.all.jsonl`** tại thư mục export gốc của Story: mỗi dòng là một object gồm `shot_key`, `page`, `act`, `beat`, `camera`, `focus`, `bundle_dir` và `prompt` (nội dung canonical `layout.prompt.json`). File gộp chỉ để bàn giao/render hàng loạt; renderer chỉ gửi trường `prompt`, không thay thế bundle canonical. **Bắt buộc thêm: xuất prompt dạng JSON có dòng trống phân tách** — `prompts.all.jsonl` chứa toàn bộ Shot hiện hành của Story, và một file mỗi Act `prompts/<act_id>.jsonl` (ví dụ `prompts/A01.jsonl`) chỉ chứa Shot của Act đó. Mỗi block là **một dòng JSON đầy đủ** cùng schema `prompts.all.jsonl` (`shot_key`, `page`, `act`, `beat`, `camera`, `focus`, `bundle_dir`, `prompt_sha256`, `prompt` = canonical `layout.prompt.json` với `summary`/`items`/bbox), **mỗi prompt cách nhau đúng một dòng trống**, không header, không code fence; kết thúc file bằng đúng một `\n`; không có ba dòng trống liên tiếp. Số block mỗi file Act phải bằng số Shot hiện hành của Act. Chỉ dùng caption rút gọn là **không đủ** vì mất `items`, bbox và metadata. Database workflow **kết thúc tại đây**.
10. **Render (tùy chọn, ngoài DB)** bằng `novel2moss-render-adapter`: chỉ đọc artifact bundle, không kết nối/ghi SQLite. Dùng `layout.prompt.json` hoặc `render.prompt.json` theo backend. Lưu output và runtime log ở thư mục render bên ngoài. Mọi revision phải truy được về thay đổi nguồn Story/Shot cụ thể.

## Cổng chốt Story (bắt buộc)

- Chỉ coi Story đã chốt khi người dùng xác nhận rõ ràng bằng lời (`chốt`, `duyệt`, `đồng ý`, `ok`) sau khi đã xem brief. Im lặng, câu hỏi, hoặc yêu cầu chỉnh sửa **không** phải xác nhận.
- Trước khi chốt: chỉ trình bày brief và phương án; **không ghi DB**, không tạo Act/Beat/Event/Shot, không chạy Layout/QA/export.
- Nếu đã có Story nháp từ trước, giữ nguyên `DRAFT`; không thêm cấu trúc mới cho tới khi chốt.
- Khi chốt, ghi dấu xác nhận vào plan/revision (`approval.status=APPROVED`, người xác nhận, thời điểm). Chưa có xác nhận thì để `PENDING`.
- Mọi thay đổi premise, nhân vật, nhãn hoặc phạm vi sau đó mở lại cổng: trình bày lại và chờ chốt trước khi ghi tiếp.

## Các bất biến

- Novel2Moss hoạt động độc lập, không yêu cầu ứng dụng nào khác đã checkout, build, cài, mount hoặc đang chạy. Tương đồng ý tưởng không tạo ra phụ thuộc code/dữ liệu.
- Không áp chỉ tiêu số cảnh hoặc số Shot; chia cảnh theo hành động và ý nghĩa thật, không theo số lượng cưỡng ép.
- Không lấy ngẫu nhiên tag hoặc tự làm đẹp chung chung gây đổi nhân vật, hành động, trang phục, cảm xúc hay cường độ.
- Giữ chính xác nhãn nguồn và provenance. Mọi kết luận nội dung ở bước tạo prompt/render phải gắn với **quyết định policy trung tâm**, scope và bằng chứng. Không tự thay thế truyện để biến quyết định thành `PASS`.
- Với cùng đầu vào đã duyệt, các bước cho kết quả lặp lại được (idempotent); không âm thầm ghi DB.
- Hợp đồng đầu ra không phụ thuộc tool; mọi cổng trả `PASS`, `WARN`, `BLOCKED` hoặc `SKIP` kèm bằng chứng.

## Các artifact bàn giao

`story_plan.json`, `shot_spec.json`, `layout.draft.json`, `album_index.json`, `prompts.all.jsonl` + `prompts/<act_id>.jsonl` (mỗi block một dòng JSON đầy đủ, cách nhau đúng một dòng trống), `prompts.all.nl.txt` + `prompts_nl/<act_id>.txt` (prose cho backend text-only, cách nhau đúng một dòng trống), và bundle export gồm `layout.prompt.json`, `prompt.manifest.json`, `fidelity_report.json`; kèm `render.prompt.json` tùy chọn khi renderer nhận `elements` đa bbox. `prompts.all.jsonl` là bản gộp một dòng một Shot, không thay bundle canonical. Output render (nếu có) nằm ngoài DB/artifact bundle. Có thể cấu hình đường dẫn, không được đổi ý nghĩa.

## Điều kiện hoàn thành

Mọi cảnh được yêu cầu có artifact Story/Shot truy xuất được nguồn, Layout đã biên dịch khớp kích thước, phát hiện QA ngữ nghĩa, `prompts.all.jsonl` đã gộp đủ số Shot hiện hành, **mỗi Act có đúng một file `prompts/<act_id>.jsonl` khớp số Shot của Act, cả hai dùng block JSON đầy đủ phân tách bằng đúng một dòng trống**, và báo cáo trung thực những gì đã chạy so với những gì chỉ mới export. Không báo hoàn thành Story khi chưa có xác nhận chốt của người dùng; trạng thái đúng là `WAITING_FOR_STORY_APPROVAL`.

## Chế độ Database V2 (bắt buộc)

1. Gọi `novel2moss-database` kiểm tra `schema_migrations`, integrity, khóa ngoại; DB là system of record sau khi commit. Dùng `docs/novel2moss/DATABASE_CONTRACT.md` và `DATABASE_SKILL_MAPPING.md` để điều phối; không đoán tên bảng.
2. Nếu `cast_mode=BLIND`: **sau khi Story được chốt**, tạo `stories` + `story_sources` → `story_roles` → `story_revisions`/Act/Beat/Event → ShotSpec/Continuity → **có thể** gán nhân vật sau qua `story_castings`. Nếu `cast_mode=NON_BLIND`: tra `characters/outfits` + nêu casting trước; **sau khi chốt** mới tạo Story + roles + casting → Story/Act/Beat/Event → ShotSpec/Continuity.
3. Các bước chung: save-layout → save QA trước export → `export-bundle`. Database workflow dừng tại bundle; không có `queue-render`, không ghi render state.
4. Mỗi bước lưu ID thật và revision trả về, truy nguyên từ `story_sources` → `story_revisions` → `beats/story_events` → `shots` → `shot_layouts` → `layout_exports` → `qa_reports`. Dựng lại ngữ cảnh từ DB trước khi resume. Renderer chỉ nhận bundle file.
5. Gọi `novel2moss-catalog-ingest` chỉ khi cần thêm dữ liệu từ nguồn/curated; việc import không được tự tạo casting hoặc thay state đã duyệt. Công cụ thay thế được; hợp đồng DB là bắt buộc.
6. Đối chiếu revision để tránh stale write; nếu schema hoặc dữ liệu mâu thuẫn, dừng **ghi** và báo lỗi rõ thay vì xoá database hay tạo bản giả. Chỉ thao tác ghi khi người dùng đang yêu cầu tạo/cập nhật dữ liệu.
