---
name: novel2moss-orchestrator
description: "Điều phối Story → Act → Beat → ShotSpec → Natural Prompt MOSS-Image → QA → export, cho Blind/Non-Blind; database kết thúc sau export."
---
# Novel2Moss — Orchestrator (Natural Prompt)

> **Policy:** Phải đọc `docs/novel2moss/CONTENT_POLICY.md` trước khi xử lý. Không tự đặt quy tắc nội dung riêng trong skill. Phạm vi kỹ thuật đọc `docs/novel2moss/MOSS_NATURAL_PROMPT.md`, `docs/novel2moss/CONTENT_FIDELITY.md`, `docs/novel2moss/DATABASE_CONTRACT.md`.

## Khởi động

1. Kiểm tra repository, migration hiện hành, DB và source. Project độc lập, không tham chiếu DB/CLI của project khác.
2. **Story Brief phải được người dùng chốt trước khi commit dữ liệu mới.** Dùng `novel2moss-story-planner` cho Story/Act/Beat/roles; dừng với `WAITING_FOR_STORY_APPROVAL` nếu chưa chốt.
3. Sau khi chốt, lưu Story/Act/Beat/Event, đúng revision; không tự tạo cảnh/sự kiện ngoài kế hoạch.
4. **Blind:** Role cố định từ đầu, `novel2moss-blind-cast` gán nhân vật sau khi cần. **Non-Blind:** `novel2moss-character-profile` chọn identity/outfit trước khi hoàn thiện Story/Shot. Cả hai dùng một schema.
5. `novel2moss-shot-spec` + `novel2moss-continuity`: ShotSpec bao gồm số người, hành động actor→target, biểu cảm, outfit, pose, cảnh, góc máy, source refs và `before/delta/after`.
6. **Sinh natural prompt trực tiếp** bằng `novel2moss-natural-language-prompt`: tra catalog và ShotSpec, viết cảnh bằng văn xuôi (mặc định tiếng Anh). **Không** tạo Layout draft/JSON, bbox hoặc `render.prompt.json`.
7. `novel2moss-fidelity-qa` đối chiếu source→Story→ShotSpec→natural prompt trong bản nháp; quyết định `PROMPT_DERIVATION` phải theo policy. Nếu phát hiện sai lệch, sửa bản nháp, không tự ghi `PASS`.
8. Lưu prompt text bằng `n2m_workflow.py save-natural-prompt` để nhận `PROMPT_ID`, sau đó lưu QA `subject_kind=PROMPT` cùng bằng chứng/policy version (`SKIP` nếu chưa QA). Cuối cùng gọi `n2m_db.py export-bundle --prompt-id ...` hoặc `export-story-prompts --story-id ...`; cần đủ prompt cho tất cả Shot hiện hành.
9. Renderer (nếu được yêu cầu) chạy **ngoài DB** từ `natural.prompt.txt` hoặc các record gộp có `prompt` là **string**. Không lưu trạng thái render, seed, model hoặc ảnh vào SQLite Novel2Moss.

## Cấu trúc bàn giao

```text
exports/<story>/
  prompts.all.jsonl            # Mỗi record = 1 dòng JSON; có 1 dòng trống giữa record
  prompts/A01.jsonl            # Chỉ Shot hiện hành trong Act A01
  bundles/A01/B01/<shot_id>/<prompt_revision>/
    natural.prompt.txt         # Nội dung positive prompt gửi MOSS trực tiếp
    prompt.manifest.json       # revision, hash, ID (không gửi model)
    fidelity_report.json       # Kết quả QA (không gửi model)
```

Trong `prompts.all.jsonl`, trường `prompt` là **natural-language text string**, không có `summary`, `items`, `bbox` hoặc JSON Layout. Đây là JSONL chứa metadata để quản lý batch, không phải JSON đem nguyên dòng gửi model. Renderer chỉ lấy giá trị `prompt`.

## Cơ sở dữ liệu

- `001..006`: migration lịch sử; `007_natural_prompts` bổ sung `shot_prompts` và QA loại `PROMPT`.
- Các bảng Layout cũ chỉ giữ cho tương thích/dữ liệu lịch sử, **không ghi thêm** và không dùng làm nguồn prompt.
- Mỗi thay đổi ShotSpec hoặc casting phải được đối chiếu để sinh prompt revision phù hợp. Không render lại từ prompt cũ khi nội dung đã thay đổi.

## Tiêu chí hoàn thành

Một prompt thuần văn bản cho từng Shot hiện hành; bảo toàn nội dung và kiểm soát revision; QA được ghi trung thực; export có hash kiểm tra được; DB không liên quan đến render downstream. Không gọi `WAITING_FOR_STORY_APPROVAL` thành `PASS` và không nói đã render nếu mới export.
