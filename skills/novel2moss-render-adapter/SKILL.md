---
name: novel2moss-render-adapter
description: "Xuất hoặc render JSON MOSS-Image Layout và render prompt đa bbox một cảnh của Novel2Moss từ artifact file độc lập; không truy vấn/ghi SQLite, không lưu render state trong DB."
---
# Novel2Moss — Render Adapter ngoài ranh giới DB

> **Policy nội dung bắt buộc:** Đọc `docs/novel2moss/CONTENT_POLICY.md` trước khi xử lý. Mọi quyết định nội dung tuân theo scope và phiên bản tại đó; skill này không tự đặt chính sách khác.

## Vai trò

Chuyển **artifact export** của Novel2Moss thành yêu cầu sinh ảnh, hoặc chỉ kiểm tra/export. Không thêm/sửa sự kiện truyện, danh tính, trang phục hay cường độ nội dung. Đọc `docs/novel2moss/TOOL_FLEXIBILITY.md` và `docs/novel2moss/MOSS_LAYOUT.md`.

Renderer là downstream độc lập. Nó chỉ cần thư mục:

```text
exports/<story_id>/<shot_key>/<revision>/
  layout.prompt.json
  render.prompt.json        # tùy chọn: đa bbox một cảnh
  prompt.manifest.json
  fidelity_report.json
```

Không kết nối SQLite, không đọc/ghi `render_jobs`/`render_assets`, không yêu cầu Novel2Moss CLI còn sống.

Bản gộp để render hàng loạt: `exports/<story_id>/prompts.all.jsonl` — toàn bộ Shot hiện hành; và `exports/<story_id>/prompts/<act_id>.jsonl` (ví dụ `prompts/A01.jsonl`) — chỉ Shot của Act đó. Mỗi block là một dòng JSON đầy đủ gồm metadata sidecar (`shot_key`, `page`, `act`, `beat`, `camera`, `focus`, `bundle_dir`, `prompt_sha256`) và `prompt` là canonical `layout.prompt.json` (`summary` + `items` + bbox). Các block cách nhau đúng **một dòng trống**; khi đọc, bỏ qua dòng rỗng rồi parse từng dòng. Renderer chỉ gửi trường `prompt`; caption rút gọn không đủ vì thiếu `items`/bbox/metadata. Các file này không thay thế bundle và không được dùng để sửa nội dung.

## Điều kiện trước khi chạy

- Có bundle export hợp lệ; `prompt.manifest.json` khớp `layout.prompt.json` bằng `prompt_sha256`; nếu dùng `render.prompt.json`, kiểm tra hash riêng của file đó.
- Nếu dùng `prompts.all.jsonl` hoặc `prompts/<act_id>.jsonl`: bỏ dòng trống, parse từng dòng JSON, và đếm block phải khớp số Shot hiện hành (toàn Story hoặc của Act); sai lệch hoặc parse lỗi thì báo `SKIP` thay vì render thiếu/thừa.
- `layout.prompt.json` chỉ chứa `summary`, `items`, `bbox_coord_space="abs_centralized"`, `bbox_format="yxyx"`; không có ID nội bộ, width/height, role/character ID hoặc provenance.
- Nếu dùng `render.prompt.json`: có đủ `scene_type`, `gen_brief`, `elements`, `bbox_coord_space="abs_centralized"`; có panel nền; mỗi nhân vật một `obj`; bbox centered `yxyx`; ít nhất một cặp bbox chồng lấn; không xếp grid.
- Có QA trước export trong `fidelity_report.json`; nếu verdict là `BLOCKED`, không dispatch. Nếu `SKIP`/thiếu QA, chỉ được export/kiểm tra, không khẳng định đã render.
- Yêu cầu quyết định `PROMPT_DERIVATION=PASS` theo `CONTENT_POLICY.md` trước khi dispatch. Đây là kiểm tra riêng, không phụ thuộc việc backend có nhận JSON hay không.
- Cấu hình `backend_type: local` hoặc `remote`. Không tự gán hành vi kiểm duyệt của cloud cho runtime local.

## Render prompt đa bbox

`render.prompt.json` là companion export-side cho renderer nhận scene schema `scene_type / gen_brief / elements / bbox_coord_space`; không thay `layout.prompt.json` và không phải schema compiler chính thức của MOSS-Image.

Với MOSS-Image-Base/SFT, positive prompt phải là `layout.prompt.json` (`summary/items`, `abs_centralized/yxyx`). Không đưa `elements` vào compiler chính thức.

- `elements[0]` là `panel` nền full canvas; mỗi nhân vật là một `obj` với `salience` primary/secondary.
- `gen_brief` phải có: một cảnh liên tục, `not a grid or rows`, `no panels/split screen/comic grid`, overlap thân/chi, mặt không bị che, không thừa chi/trùng người.
- Bbox **chồng lấn** theo tương tác; không 2×2/3×2/ô chân dung. Nếu bbox xếp grid, không dispatch.
- Nếu backend chỉ nhận text: dùng `natural.prompt.txt` trong bundle (hoặc bản gộp `prompts.all.nl.txt` / `prompts_nl/<act_id>.txt`, đọc bằng cách tách theo dòng trống) thay cho `layout.prompt.json`; vẫn giữ JSON làm source of truth và ghi chú `SPATIAL_CONTROL_DEGRADED`.
- Không đổi nội dung, số người, pose, trang phục hay nhãn nội dung khi chuyển format.

## Tạo yêu cầu

- Positive prompt là nội dung `layout.prompt.json` hoặc `render.prompt.json`; không thêm Markdown code fence hoặc trường sidecar vào prompt.
- Width/height lấy từ manifest/draft; không sửa Layout JSON. Giữ nguyên Unicode của chữ cần xuất hiện trên ảnh.
- Negative prompt, seed, sampler, guidance, steps, checkpoint và đường dẫn output nằm trong config runtime **bên ngoài** bundle.
- Ghi log runtime với prompt hash, model/checkpoint, seed, sampler, kích thước, output path và trạng thái thực tế. Không tự bịa giá trị còn thiếu.
- Ảnh do model trả ra không chứng minh đúng bố cục; QA ảnh là quy trình bên ngoài, không ghi vào DB Novel2Moss.

## Không phá hủy artifact

Nếu Shot/Layout thay đổi, tạo revision/thư mục export mới. Giữ nguyên prompt hash và output lịch sử; không ghi đè generation cũ. Nếu cần thay thế, tạo bản mới theo revision.

## Kết quả

Trả `EXPORTED`, `GENERATED`, `BACKEND_REJECTED`, `POLICY_BLOCKED` hoặc `SKIP` theo policy và runtime thực tế. Nếu chỉ export, liệt kê file đã xuất, không gọi đó là kết quả render.

## Bàn giao

Đường dẫn bundle, `prompt_sha256`, manifest, fidelity report, runtime/model/seed, output path/checksum (nếu có), trạng thái và lỗi kỹ thuật thực tế. Không lưu các giá trị này vào SQLite Novel2Moss.
