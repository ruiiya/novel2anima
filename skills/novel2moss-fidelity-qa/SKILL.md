---
name: novel2moss-fidelity-qa
description: "QA bảo toàn Story/ShotSpec khi chuyển thành natural-language prompt MOSS-Image; kiểm tra actor/target, identity/outfit, continuity và chữ trong ảnh, không làm QA render trong DB."
---
# Novel2Moss — Fidelity QA (Natural Prompt)

> Đọc `docs/novel2moss/CONTENT_POLICY.md` và `docs/novel2moss/CONTENT_FIDELITY.md`, `docs/novel2moss/MOSS_NATURAL_PROMPT.md`. Quy tắc phân loại thuộc duy nhất policy trung tâm.

## Công việc

- V4: đọc `docs/novel2moss/VISUAL_STORYTELLING.md`; đối chiếu mọi Event nguồn với coverage, mọi slot với ShotSpec, purpose/moment/camera, Visual Bible, thứ tự và predecessor đúng nhánh. Kiểm tra action/reaction không bị mất hoặc gộp sai thời điểm, location/prop không tự đổi; reverse shot không đảo actor/target.
- Mã lỗi bổ sung: SOURCE_COVERAGE_MISSING, STALE_VISUAL_CONTEXT, BRANCH_PREDECESSOR_MISMATCH, CONTINUITY_BREAK, SHOT_DIRECTION_MISMATCH. Không biến trạng thái unresolved/unsupported thành context-only để seal.
- QA prompt V4 phải có report.policy_decision xác định đúng shot_id, scope PROMPT_DERIVATION, decision, policy_version, evidence, policy_ref. Sequence QA PASS chỉ sau đối chiếu xuyên Shot; ghi evidence cụ thể trong seal.json. Chỉ kiểm tra cấu trúc không đủ chứng minh fidelity.

- Kiểm tra từ `story_sources` → Plan/Act/Beat/Event → `shots`/ShotSpec → `continuity_snapshots` → `shot_prompts` và bản `.txt` sắp export.
- So sánh **số người**, tên/đặc điểm nhân vật, outfit và màu, tay/cử chỉ/đạo cụ, vai trò actor→target, biểu cảm/phản ứng, bối cảnh, vị trí tương đối, camera, ánh sáng, state before/delta/after, và chữ cần xuất hiện nguyên văn.
- Cảnh phải **độc lập khi render**; báo lỗi khi prompt chỉ nói “as before”, “the same outfit” mà không có chi tiết cần thiết hoặc dùng tên không rõ danh tính.
- Kiểm tra prompt là **văn xuôi tự nhiên** (không JSON/layout/bbox/code fence/metadata). Cấu trúc `PASS` không đủ để kết luận ngữ nghĩa `PASS`.
- Kiểm tra camera: đúng **một** mệnh đề lens + góc + framing, khớp ShotSpec, không lặp và không trộn hai họ góc; lệch hoặc mâu thuẫn → `CAMERA_CONTRADICTION`, không `PASS`. Validator trả `CAMERA_CONFLICT`/`BBOX_IN_PROMPT` thì sửa prompt hoặc tạo revision.
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
