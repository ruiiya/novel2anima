# Novel2Anima V3 — Chuyển sang Natural Prompt

## Mục tiêu

Đầu ra canonical của mỗi Shot là **văn bản natural-language** mô tả hình ảnh cho MOSS-Image (mặc định tiếng Anh). Không dùng JSON Layout, bounding box hay flatten từ Layout trước đó. Database chỉ phục vụ từ Story đến xuất prompt; render độc lập.

## Thay đổi chính

- Thay `novel2anima-layout-planner` bằng `novel2anima-natural-language-prompt` với quy trình đọc ShotSpec, nhân vật, outfit và continuity rồi viết trực tiếp đoạn mô tả hoàn chỉnh.
- Chuyển `novel2anima-orchestrator` và `novel2anima-fidelity-qa` sang pipeline **ShotSpec → Natural Prompt → QA → Export**; áp dụng cho cả Blind và Non-Blind.
- Bổ sung `007_natural_prompts.sql`: bảng `shot_prompts` có revision/hash bất biến; QA mới hỗ trợ loại `PROMPT`.
- Bổ sung `save-natural-prompt`, `export-bundle --prompt-id`, `export-story-prompts --story-id`.
- Mỗi Shot export `natural.prompt.txt` (chỉ text), `prompt.manifest.json` và `fidelity_report.json`. File tổng hợp `prompts.all.jsonl` và theo Act chứa trường `prompt` là chuỗi text, không phải JSON prompt MOSS.
- Loại khỏi luồng hoạt động compiler bbox, flatten Layout, JSON Layout và các tài liệu/skill chuyên Layout. Dữ liệu layout lịch sử vẫn còn trong database khi nâng cấp.
- Không tự gọi LLM và không render; skill mô tả cách LLM tạo prompt, các CLI quản lý dữ liệu và kiểm tra cấu trúc. Fidelity ngữ nghĩa cần đánh giá riêng.

## Nâng cấp từ bản Layout

```powershell
python install.py --target D:\NGV\novel2anima --mode claude --upgrade
cd D:\NGV\novel2anima
python database/src/n2m_db.py init
python database/src/n2m_db.py seed
python -m unittest discover -s tests -v
```

Installer sao lưu tệp cũ trước khi thay thế và chỉ loại khỏi thư mục dự án đích các file Layout được chỉ định rõ. Không tự sửa `CONTENT_POLICY.md` ở dự án đích và không xóa bản ghi Layout lịch sử. **Không tự chuyển prompt Layout cũ sang text**: hãy tạo lại natural prompt từ ShotSpec/Profile/Continuity và QA lại.

## Tài liệu kỹ thuật

- `README.md`
- `docs/novel2anima/MOSS_NATURAL_PROMPT.md`
- `docs/novel2anima/DATABASE_OPERATIONS.md`
- `docs/novel2anima/DATABASE_CONTRACT.md`

## Nguồn tham khảo

- [MOSS-Image User Guide](https://github.com/OpenMOSS/MOSS-Image/blob/main/USERGUIDE.md)
- [MOSS-Image Prompt Enhancer](https://github.com/OpenMOSS/MOSS-Image/blob/main/skills/moss-image-prompt-enhancer/SKILL.md)
- [ComfyUI MOSS Image Tutorial](https://github.com/Comfy-Org/docs/blob/main/tutorials/image/moss-image/moss-image.mdx)
