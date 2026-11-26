---
name: novel2anima-orchestrator
description: "Điều phối Story → Act → Beat → Visual Storyboard → ShotSpec → Continuity → Anima Prompt → QA → seal/export, cho Blind/Non-Blind; database kết thúc sau export."
---
# Novel2Anima — Orchestrator (Anima Prompt)
## Studio V6 — áp dụng khi Story được quản lý theo quy trình Studio

Đọc `docs/novel2anima/STUDIO_V6.md` và dùng `novel2anima-studio-process` để kiểm tra giai đoạn trước/sau công việc. Không tự ghi nhận người dùng đã chốt chỉ từ JSON hay sự im lặng. **CONTENT_POLICY** vẫn ở `docs/novel2anima/CONTENT_POLICY.md`; skill này không tự tạo quy tắc mới. V6 kết thúc tại prompt export; không tự gửi ảnh tới renderer.

**Chuỗi bắt buộc:** trò chuyện chốt toàn Story → review/chốt `STORY` → nghiên cứu, Visual Bible → review/chốt `RESEARCH_VISUAL` → phân trang/Continuity → review/chốt `STORYBOARD` → Anima prompt và QA toàn chuỗi, seal → review/chốt `PROMPTS` → `n2a_studio.py export`. Không tự chuyển bước, không dùng `export-story-prompts` để né gate; mỗi Story tiến độ riêng. Nếu user báo lỗi trang, ghi `report-feedback`, so sánh các phụ thuộc, tạo revision và xin duyệt lại. Không gọi skill render-adapter trong đường chạy V6.


## V5 (mặc định cho storyboard mới)

Đọc `docs/novel2anima/NARRATIVE_CONTINUITY.md` trước workflow. Dùng một pipeline cho mọi story, phân biệt quan hệ từng shot, không hỏi Album/Comic. Chốt narrative + scene Bible trước shot, lưu state tại moment, gọi `compile-prompt --shot-id SHOT_ID --save`, QA từng shot và sequence với evidence cho từng slot rồi seal. Storyboard lịch sử V4 vẫn dùng contract cũ. Không thay đổi renderer.

> **Policy:** Phải đọc `docs/novel2anima/CONTENT_POLICY.md` trước khi xử lý. Không tự đặt quy tắc nội dung riêng trong skill. Phạm vi kỹ thuật đọc `docs/novel2anima/ANIMA_TAG_PROMPT.md`, `docs/novel2anima/CONTENT_FIDELITY.md`, `docs/novel2anima/DATABASE_CONTRACT.md`.

## Khởi động

1. Kiểm tra repository, migration hiện hành, DB và source. Project độc lập, không tham chiếu DB/CLI của project khác.
2. **Story Brief phải được người dùng chốt trước khi commit dữ liệu mới.** Dùng `novel2anima-story-planner` cho Story/Act/Beat/roles; dừng với `WAITING_FOR_STORY_APPROVAL` nếu chưa chốt.
3. Sau khi chốt, lưu Story/Act/Beat/Event, đúng revision; không tự tạo cảnh/sự kiện ngoài kế hoạch.
4. **Blind:** Role cố định từ đầu, `novel2anima-blind-cast` gán nhân vật sau khi cần. **Non-Blind:** `novel2anima-character-profile` chọn identity/outfit trước khi hoàn thiện Story/Shot. Cả hai dùng một schema.
5. `novel2anima-storyboard-planner`: đọc `docs/novel2anima/VISUAL_STORYTELLING.md`; lập Visual Bible, shot order, mục đích kể chuyện, liên kết Event và predecessor đúng nhánh. Trình và chờ duyệt storyboard riêng trước khi lưu.
6. `novel2anima-shot-spec` + `novel2anima-continuity`: mỗi slot đã chốt tạo ShotSpec, gắn context hash, hành động actor→target, trạng thái, camera, source refs và `before/delta/after`. Không tự bịa thêm slot.
7. **Sinh prompt Anima trực tiếp** bằng `novel2anima-anima-prompt`: tra catalog tag, Visual Bible và ShotSpec, dựng tag block + tối đa 3 câu bổ trợ (cảnh nhiều người: 4 câu) (mặc định tiếng Anh). **Không** tạo Layout/JSON, bbox, `render.prompt.json`, và cho phép quality/`score_*` tag theo hợp đồng Anima.
8. `novel2anima-fidelity-qa` đối chiếu source→Story→ShotSpec→Anima prompt (tag + câu), coverage Event và sequence; quyết định `PROMPT_DERIVATION` phải theo policy. Nếu sai lệch, sửa đúng tầng, không tự ghi `PASS`.
9. Lưu prompt text bằng `n2m_workflow.py save-natural-prompt`, ghi QA `PROMPT` có bằng chứng và policy decision. Sau QA toàn chuỗi, dùng `seal-storyboard` ghim Shot/Prompt/QA revision rồi `export-story-prompts --story-id ...`. Không xuất cả Story chưa seal, không rơi về revision cũ.
10. Renderer (nếu được yêu cầu) chạy **ngoài DB** từ `natural.prompt.txt` hoặc các record gộp có `prompt` là **string** Anima. Không lưu trạng thái render, seed, model hoặc ảnh vào SQLite Novel2Anima.

## Cấu trúc bàn giao

```text
exports/<story>/
  prompts.all.jsonl            # Mỗi record = 1 dòng JSON; có 1 dòng trống giữa record
  prompts/A01.jsonl            # Chỉ Shot hiện hành trong Act A01
  bundles/A01/B01/<shot_id>/<prompt_revision>/
    natural.prompt.txt         # Anima prompt: tag block + tối đa 3 câu bổ trợ (cảnh nhiều người: 4 câu)
    prompt.manifest.json       # revision, hash, format anima-tag-v1 (không gửi model)
    fidelity_report.json       # Kết quả QA (không gửi model)
```

Trong `prompts.all.jsonl`, trường `prompt` là **Anima prompt string** (dòng 1 tag block, dòng 2 câu bổ trợ), không có `summary`, `items`, `bbox` hay JSON Layout. Đây là JSONL metadata để quản lý batch, không phải JSON đem nguyên dòng gửi model. Renderer chỉ lấy giá trị `prompt`.

## Cơ sở dữ liệu

- `001..006`: migration lịch sử; `007_natural_prompts` bổ sung `shot_prompts` và QA loại `PROMPT`.
- `008_visual_storytelling`: storyboard, Visual Bible, coverage, predecessor, seal append-only. Story cũ chưa có storyboard vẫn export dạng legacy, không tự giả định V4.
- Các bảng Layout cũ chỉ giữ cho tương thích/dữ liệu lịch sử, **không ghi thêm** và không dùng làm nguồn prompt.
- Mỗi thay đổi ShotSpec hoặc casting phải được đối chiếu để sinh prompt revision phù hợp. Không render lại từ prompt cũ khi nội dung đã thay đổi.

## Tiêu chí hoàn thành

Một prompt Anima (tag block + câu bổ trợ) cho từng Shot hiện hành; bảo toàn nội dung và kiểm soát revision; QA được ghi trung thực; export có hash kiểm tra được; DB không liên quan đến render downstream. Không gọi `WAITING_FOR_STORY_APPROVAL` thành `PASS` và không nói đã render nếu mới export.
