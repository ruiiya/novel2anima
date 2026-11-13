---
name: novel2moss-fidelity-qa
description: "QA bảo toàn Story/ShotSpec khi chuyển thành natural-language prompt MOSS-Image; kiểm tra actor/target, identity/outfit, continuity và chữ trong ảnh, không làm QA render trong DB."
---
# Novel2Moss — Fidelity QA (Natural Prompt)

> Đọc `docs/novel2moss/CONTENT_POLICY.md` và `docs/novel2moss/CONTENT_FIDELITY.md`, `docs/novel2moss/MOSS_NATURAL_PROMPT.md`. Quy tắc phân loại thuộc duy nhất policy trung tâm.

## Công việc

- Kiểm tra từ `story_sources` → Plan/Act/Beat/Event → `shots`/ShotSpec → `continuity_snapshots` → `shot_prompts` và bản `.txt` sắp export.
- So sánh **số người**, tên/đặc điểm nhân vật, outfit và màu, tay/cử chỉ/đạo cụ, vai trò actor→target, biểu cảm/phản ứng, bối cảnh, vị trí tương đối, camera, ánh sáng, state before/delta/after, và chữ cần xuất hiện nguyên văn.
- Cảnh phải **độc lập khi render**; báo lỗi khi prompt chỉ nói “as before”, “the same outfit” mà không có chi tiết cần thiết hoặc dùng tên không rõ danh tính.
- Kiểm tra prompt là **văn xuôi tự nhiên** (không JSON/layout/bbox/code fence/metadata). Cấu trúc `PASS` không đủ để kết luận ngữ nghĩa `PASS`.
- Kiểm tra quyết định `PROMPT_DERIVATION` và `policy_version` đã có; không tự kết luận từ nhãn NSFW, không đổi Story để tránh kết quả kiểm tra.

## Phát hiện

Mỗi finding: `{shot_id, rule, status, source_pointer, target_pointer, evidence, suggestion, autofix:false}`. Các mã điển hình: `ACTOR_TARGET_MISMATCH`, `PARTICIPANT_LOSS`, `WARDROBE_COLOR_CHANGED`, `STATE_RESET_UNEXPLAINED`, `VISIBLE_TEXT_CHANGED`, `SCENE_MISMATCH`, `CAMERA_CONTRADICTION`, `PROMPT_NOT_NATURAL`, `PROVENANCE_MISSING`.

- `PASS`: Đã kiểm tra và không phát hiện sai lệch theo phạm vi được nêu; không bảo đảm model vẽ đúng.
- `WARN`: Cần người duyệt thêm chi tiết không chắc chắn.
- `BLOCKED`: Có mâu thuẫn nguồn/prompt hoặc lỗi nghiêm trọng đã xác nhận.
- `SKIP`: Chưa chạy một kiểm tra bắt buộc; **không** mặc định PASS.

## Ghi DB

```powershell
python database/src/n2m_workflow.py save-qa --kind PROMPT --subject-id PROMPT_ID --verdict PASS --file report.json
```

`qa_reports` append-only, không sửa bản cũ. Các record `LAYOUT` cũ chỉ là lịch sử trước migration 007; lệnh ghi mới chỉ nhận `STORY/SHOT/PROMPT`. Image/render QA là downstream độc lập, không ghi DB Novel2Moss.
