---
name: novel2anima-render-adapter
description: "Bàn giao Anima prompt (tag block + câu bổ trợ) từ file cho backend Anima-Aesthetic-v1.1 local/remote; hoàn toàn ngoài DB; không gửi JSON/bbox."
---
# Novel2Anima — Render Adapter (file-only)

> Đọc `docs/novel2anima/CONTENT_POLICY.md` và `docs/novel2anima/ANIMA_TAG_PROMPT.md`; adapter không tự định nghĩa policy.

## Vai trò

Backend có thể là `backend_type: local` hoặc `remote`; không tự suy diễn hành vi kiểm duyệt cloud lên local. Khi người dùng yêu cầu render, đọc bundle `natural.prompt.txt`, `prompt.manifest.json`, `fidelity_report.json`. **Không truy vấn SQLite, không tạo render job/ảnh trong DB.** Renderer mặc định: ComfyUI với Anima-Aesthetic-v1.1.

## Cấu hình renderer (giữ ngoài DB)

| Tham số | Giá trị khởi đầu |
|---|---|
| diffusion model | `anima-aesthetic-v1.1.safetensors` |
| text encoder | `qwen_3_06b_base.safetensors` |
| VAE | `qwen_image_vae.safetensors` |
| steps / CFG | 30 / 3.5–4.5 |
| sampler / scheduler | `er_sde` / `simple` |
| resolution | 896×1152, 1024×1024; 1–1.5 MP; bội số 16 |
| negative | `worst quality, low quality, artist name, blurry, jpeg artifacts, chromatic aberration` |

Workflow API mẫu: `exports/cnc_bunny/workflow/anima_bunny_all.json`. Không thêm LoRA style (đã merge trong Aesthetic); character LoRA weight 0.7–0.9 nếu có.

## Điều kiện giao nhận

1. Đọc UTF-8 nguyên bản từ `natural.prompt.txt`. Kiểm `prompt_sha256` và `format: anima-tag-v1` trong manifest bằng `tools/novel2anima/validate_anima_prompt.py --manifest ...`.
2. Kiểm QA: `BLOCKED` thì không dispatch; `SKIP` thì báo chưa xác minh, không giả vờ QA PASS. Đối chiếu `PROMPT_DERIVATION` ở policy theo artifact.
3. Gửi **đúng nội dung text** vào positive prompt của `CLIPTextEncode`: dòng 1 là tag block, dòng 2 là câu bổ trợ. Không gửi JSON manifest/record, không thêm bbox, không bọc code fence.
4. Batch `prompts.all.jsonl` / `prompts/A01.jsonl`: bỏ dòng trống, parse từng JSON line, chỉ trích **giá trị `prompt` kiểu string**.
5. Seed, checkpoint, sampler, negative, nơi lưu ảnh thuộc runtime **ngoài** DB. Không tự thêm `nsfw` vào negative; safety tag đã nằm trong positive.
6. Tắt prompt enhancer nếu backend có, để giữ đúng tag block đã QA; nếu bật thì log văn bản thực sự gửi model.
7. Ghi log runtime/ảnh riêng ngoài DB; phân biệt `EXPORTED`, `GENERATED`, `BACKEND_REJECTED`, `POLICY_BLOCKED`, `SKIP` theo chứng cứ.

## Output

Một text positive prompt cho mỗi Shot. Không cần `layout.prompt.json`, `render.prompt.json`, `bbox` hay tọa độ. Renderer chạy được khi DB Novel2Anima đóng hoặc bị di chuyển.
