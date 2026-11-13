---
name: novel2moss-render-adapter
description: "Bàn giao natural-language positive prompt từ file cho MOSS-Image backend local/remote; hoàn toàn ngoài DB; không gửi Layout JSON/bbox."
---
# Novel2Moss — Render Adapter (file-only)

> Đọc `docs/novel2moss/CONTENT_POLICY.md` và `docs/novel2moss/MOSS_NATURAL_PROMPT.md`; adapter không tự định nghĩa policy.

## Vai trò

Backend có thể được cấu hình `backend_type: local` hoặc `backend_type: remote`; không tự suy diễn hành vi kiểm duyệt cloud lên local. Khi người dùng yêu cầu render, đọc bundle `natural.prompt.txt`, `prompt.manifest.json`, `fidelity_report.json`. **Không truy vấn SQLite, không tạo render job/ảnh trong DB.** Có thể sử dụng ComfyUI hoặc bất kỳ renderer nào nhận positive text prompt.

## Điều kiện giao nhận

1. Đọc UTF-8 nguyên bản từ `natural.prompt.txt`. Kiểm `prompt_sha256` trong manifest bằng `tools/novel2moss/validate_natural_prompt.py --manifest ...`.
2. Kiểm tra QA: `BLOCKED` thì không dispatch; `SKIP` thì báo chưa được xác minh và không giả vờ QA PASS. Đối chiếu quyết định `PROMPT_DERIVATION` ở policy theo artifact.
3. Gửi **đúng nội dung text** vào positive prompt, không gửi cả JSON manifest/record, không thêm bbox/JSON layout/Markdown code fence. Nếu sử dụng batch `prompts.all.jsonl` hoặc `prompts/A01.jsonl`, bỏ dòng trống và parse từng JSON line, chỉ trích **giá trị `prompt` kiểu string**.
4. Các thông số negative prompt, resolution, steps, CFG, seed, model checkpoint và nơi lưu ảnh nằm trong cấu hình runtime **ngoài** Novel2Moss DB. Không tự chèn negative tags như `nsfw` vào positive/negative nếu người dùng không cấu hình.
5. Khi backend có prompt enhancer riêng, nên tắt enhancer nếu muốn giữ nguyên lời mô tả đã được QA; có thể bật nếu người dùng muốn thử nghiệm và log văn bản thực sự gửi model.
6. Ghi log runtime/ảnh riêng ngoài DB nếu thực sự chạy; phân biệt `EXPORTED`, `GENERATED`, `BACKEND_REJECTED`, `POLICY_BLOCKED`, `SKIP` dựa trên chứng cứ.

## Output

Một text positive prompt cho mỗi Shot. Không cần `layout.prompt.json`, `render.prompt.json`, `bbox` hoặc tọa độ. Renderer có thể chạy khi DB Novel2Moss đóng hoặc bị di chuyển.
