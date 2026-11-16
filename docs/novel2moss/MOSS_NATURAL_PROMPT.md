# Novel2Moss — Hợp đồng Natural-Language Prompt (MOSS-Image)

> **Định dạng canonical duy nhất:** Một Shot → một đoạn văn miêu tả hình ảnh hoàn chỉnh, UTF-8, thường bằng tiếng Anh. Model nhận trực tiếp văn bản này ở **positive prompt**. Không tạo Layout JSON, bbox, item array, tag-only prompt hay prompt JSON wrapper. Metadata và trạng thái QA lưu ở sidecar, không trộn vào prompt.
>
> Đây là hợp đồng **định dạng/kỹ thuật**, không quyết định nội dung được phép. Các quyết định nội dung chỉ nằm trong `docs/novel2moss/CONTENT_POLICY.md`.

## Nguồn đối chiếu chính thức

- https://github.com/OpenMOSS/MOSS-Image/blob/main/USERGUIDE.md#prompt-guidelines
- https://github.com/OpenMOSS/MOSS-Image/blob/main/skills/moss-image-prompt-enhancer/SKILL.md
- https://github.com/Comfy-Org/docs/blob/main/tutorials/image/moss-image/moss-image.mdx

MOSS-Image-Base hỗ trợ **natural language**, chuỗi tags và Layout JSON. OpenMOSS khuyên dùng tiếng Anh do dữ liệu huấn luyện nhiều nhất; prompt enhancer mặc định dùng **caption** cho cảnh minh họa/ảnh thông thường. Hướng dẫn ComfyUI khuyên miêu tả **hình ảnh đã hoàn thành**, không viết mệnh lệnh như “generate a picture”. Những nguồn này không khẳng định có một thứ tự câu hay độ dài tối ưu bắt buộc cho mọi cảnh.

## Quy tắc biên soạn

1. **Bức ảnh trước tiên:** Mở bằng phong cách/medium và mô tả ngắn cảnh tổng quát: ai/đối tượng nào, đang làm gì, ở đâu. Cảnh phức tạp có thể dùng thêm câu/đoạn, nhưng mỗi câu phải thêm thông tin trực quan.
2. **Nhân vật nhận diện được:** Từng người có tên + tác phẩm khi đã xác nhận, đặc điểm bền vững, trang phục/màu chính xác, tư thế và biểu cảm. Với Blind chưa casting, dùng mô tả role trung tính từ ShotSpec; không bịa tên tác phẩm hoặc ngoại hình canon.
3. **Hành động và quan hệ:** Viết câu chủ động với **actor / action / target** rõ ràng, bao gồm tay/bộ phận thực hiện và điểm tiếp xúc khi nhìn thấy; mô tả phản ứng của target. Không đảo vai trò hoặc làm mất cử chỉ chính.
4. **Bố cục qua ngôn ngữ:** Dùng *on the left/right, foreground/background, closer to the camera, facing, behind, slightly overlapping*, không dùng tọa độ hoặc pixel. Đảm bảo tương thích với camera/framing của ShotSpec.
5. **Bối cảnh, camera, ánh sáng:** Chỉ thêm chi tiết thực sự có trong Story/ShotSpec hoặc khoảng trống sáng tạo được phép. Không tự đổi phong cách; không nhét nhiều kiểu camera trái nhau. **Camera viết đúng một mệnh đề**, đủ ba phần — lens, góc, framing — và đặt ngay sau câu bố cục, trước/cạnh câu nhân vật: `shot at 35mm from a low angle, full body head to feet`. Dùng từ literal thay vì ẩn dụ: `directly overhead, looking straight down` thay cho `top-down view from above`; `low angle, looking up` thay cho `low-angle view from below`. Không lặp camera ở câu khác, không mô tả hai góc cùng lúc, và framing phải khớp phần cơ thể thực sự nhìn thấy (không `face close-up` mà còn hông/đùi trong khung).
6. **Chữ cần xuất hiện:** Đặt đúng chuỗi trong dấu ngoặc kép, giữ nguyên chính tả, chữ hoa, tiếng gốc và xuống dòng nếu thực sự muốn in lên ảnh. Không nhầm hội thoại của Story thành chữ nhìn thấy trên hình.
7. **Không biến thành chuỗi tag:** Tránh dồn quality score, danh sách tính từ trùng lặp, “masterpiece, highres…” máy móc, giải thích kỹ thuật, field name hoặc “Prompt:” đầu dòng. Danbooru chỉ là nguồn hiểu đặc điểm, không bắt buộc hiện nguyên tag ở output.
8. **Mỗi Shot tự đủ ngữ cảnh:** Không dựa vào “same woman as previous image”, “wearing the same clothes” hay “continue the last scene” nếu thông tin cần thiết chưa có trong chính prompt. Tra profile và continuity để diễn tả lại các đặc điểm cần giữ.
9. **Giữ ý nghĩa và giới hạn:** Không tự thêm/giảm số người, đổi trang phục, đổi action/target, bỏ đồ vật cần nhìn thấy, thay mức độ/nhãn của nguồn. Dữ liệu không trực quan giữ ở ShotSpec/sidecar; quyết định theo policy trung tâm.
10. **Visual storytelling V4:** Dựa vào slot visual moment, purpose và camera để chọn chi tiết cần vẽ; sử dụng Visual Bible đã chốt, world/screen state và prop owner. Giữ tự đủ ngữ cảnh, không nhồi toàn bộ Bible, không viết nhiều panel trong một prompt. Đọc `VISUAL_STORYTELLING.md`.

## Một Shot → một file .txt

Ví dụ positive prompt hợp lệ:

> A warm anime illustration of two adult friends in a sunlit reading room. On the left, Aria has long silver hair and blue eyes, wears a white blouse and a dark blue skirt, and stands beside Noah. She gently pats the top of his head with her right hand. On the right, Noah has short black hair and brown eyes, wears a black shirt and gray trousers, and sits on a wooden chair, tilting his face upward with a relaxed smile. Medium two-shot at eye level, soft daylight coming through a window, bookshelves softly visible in the background.

Đây là nội dung thuần của `natural.prompt.txt`; **không** xuất `{"caption": "..."}` cho renderer. JSON `{"caption":"..."}` có thể là định dạng **nháp nội bộ của prompt enhancer chính thức**, không phải yêu cầu của định dạng đầu ra Novel2Moss.

## Lưu trữ và xuất file

- DB: `shot_prompts` (`shot_id`, `revision`, `language`, `prompt_text`, hash, SHA của ShotSpec). Bản ghi append-only.
- Tạo: `n2m_workflow.py save-natural-prompt --shot-id ... --file ...` (đầu vào là `.txt`).
- Kiểm tra: `tools/novel2moss/validate_natural_prompt.py` chỉ xác nhận dạng văn bản, Unicode/hash; **không** thể tự chứng minh fidelity, cần QA đối chiếu ShotSpec.
- QA: `n2m_workflow.py save-qa --kind PROMPT --subject-id PROMPT_ID`.
- Export: `n2m_db.py export-bundle --prompt-id ... --out-dir ...` tạo `natural.prompt.txt`, `prompt.manifest.json`, `fidelity_report.json`.
- Xuất cả Story: `n2m_db.py export-story-prompts --story-id ... --out-dir ...` tạo các bundle, `prompts.all.jsonl` và `prompts/A01.jsonl`... Mỗi record JSONL chứa **`prompt` là string natural language**, không phải JSON Layout. Mỗi record nằm trên một dòng JSON, cách record bằng một dòng trống như giao kèo dự án.
- V4 chọn exact bindings theo storyboard seal và thứ tự số; từ chối seal nếu coverage/continuity/QA chưa đạt. Metadata storyboard không gửi MOSS.
- Sau export, renderer local/remote chỉ đọc file; không truy cập Novel2Moss SQLite. Seed, checkpoint, sampler, negative prompt, output ảnh là cấu hình của renderer.

## QA trước export

- So khớp số nhân vật, nhận diện, outfit, màu, vị trí trái/phải, camera, sự kiện đang được thể hiện và chiều actor→target.
- So khớp continuity (đặc điểm giữ nguyên và delta có chủ đích).
- Bảo toàn chữ cần hiển thị **nguyên văn**; tránh lẫn lời thoại với chữ cần in.
- `PASS` cấu trúc `.txt` **không** đồng nghĩa QA ngữ nghĩa `PASS` hay ảnh render chính xác.
- Không tự tuyên bố cấu hình inference “tốt nhất” khi chưa benchmark trên workflow thực tế; thông số CFG/steps/resolution thuộc renderer, không thuộc DB.

## Migration từ Layout V2

- Migration `007_natural_prompts.sql` **không xóa** `shot_layouts`, `layout_exports`, `qa_reports` lịch sử. Các bảng này là dữ liệu cũ chỉ đọc; pipeline mới không tạo thêm.
- **Không tự convert** Layout JSON cũ thành natural prompt mới (có thể mất chiều hành động/continuity). Phải lập prompt từ ShotSpec + profile + continuity, QA lại rồi export revision mới.
- `save-layout`, `export-layout`, `--layout-id`, `compile_layout.py`, `flatten_layout.py` và `layout.prompt.json` không còn được dùng trong pipeline mới.
