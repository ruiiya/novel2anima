---
name: novel2anima-fidelity-qa
description: "QA bảo toàn Story/ShotSpec khi chuyển thành prompt Anima (tag block + câu bổ trợ); kiểm tra actor/target, identity/outfit, continuity, camera tag và chữ trong ảnh, không làm QA render trong DB."
---
# Novel2Anima — Fidelity QA (Anima Prompt)

## V5: cross-shot QA

Đọc `docs/novel2anima/NARRATIVE_CONTINUITY.md`. Kiểm tra toàn bộ chuỗi, không chỉ từng prompt. Mỗi slot kiểm tra continuity graph, before/at/after, role ngoài frame, outfit/prop ownership, hướng nhìn, camera, đúng nhân vật và actor→target; kiểm tra tag lock, loại tag thực sự không nhìn thấy theo frame, mâu thuẫn tag/prose và nhịp kể. Với shot độc lập chỉ kiểm tra thông tin chung đã khóa, không ép pose liên tục. Ghi `sequence_qa.shot_checks` mỗi slot verdict/evidence cụ thể và `sequence_qa` tổng thể. Chỉ seal khi đánh giá thật; sửa đúng tầng, kiểm tra lại descendant liên quan. Đây là QA prompt, không phải QA ảnh render.

> Đọc `docs/novel2anima/CONTENT_POLICY.md` và `docs/novel2anima/CONTENT_FIDELITY.md`, `docs/novel2anima/ANIMA_TAG_PROMPT.md`. Quy tắc phân loại thuộc duy nhất policy trung tâm.

## Công việc

- V4: đọc `docs/novel2anima/VISUAL_STORYTELLING.md`; đối chiếu mọi Event nguồn với coverage, mọi slot với ShotSpec, purpose/moment/camera, Visual Bible, thứ tự và predecessor đúng nhánh. Kiểm tra action/reaction không bị mất hoặc gộp sai thời điểm, location/prop không tự đổi; reverse shot không đảo actor/target.
- Mã lỗi bổ sung: SOURCE_COVERAGE_MISSING, STALE_VISUAL_CONTEXT, BRANCH_PREDECESSOR_MISMATCH, CONTINUITY_BREAK, SHOT_DIRECTION_MISMATCH. Không biến trạng thái unresolved/unsupported thành context-only để seal.
- QA prompt V4 phải có report.policy_decision xác định đúng shot_id, scope PROMPT_DERIVATION, decision, policy_version, evidence, policy_ref. Sequence QA PASS chỉ sau đối chiếu xuyên Shot; ghi evidence cụ thể trong seal.json. Chỉ kiểm tra cấu trúc không đủ chứng minh fidelity.

- Kiểm tra từ `story_sources` → Plan/Act/Beat/Event → `shots`/ShotSpec → `continuity_snapshots` → `shot_prompts` và bản `.txt` sắp export.
- So sánh **số người**, tên/đặc điểm nhân vật, outfit và màu, tay/cử chỉ/đạo cụ, vai trò actor→target, biểu cảm/phản ứng, bối cảnh, vị trí tương đối, camera, ánh sáng, state before/delta/after, và chữ cần xuất hiện nguyên văn.
- Cảnh phải **độc lập khi render**; báo lỗi khi prompt chỉ nói “as before”, “the same outfit” mà không có chi tiết cần thiết hoặc dùng tên không rõ danh tính.
- Kiểm tra prompt đúng **hợp đồng Anima**: dòng 1 là tag block lowercase, space không underscore, cách nhau `, `; có **safety tag** và **subject count**; không quality/`score_*`; không JSON/layout/bbox/code fence/metadata. Thiếu identity anchor bắt buộc (tóc/mắt/dấu nhận diện khi nhân vật đã cast) → finding, không `PASS`. Cấu trúc `PASS` không đủ để kết luận ngữ nghĩa `PASS`.
- Kiểm tra camera: đúng **một** framing tag + **một** angle tag trong danh sách đóng, khớp ShotSpec, không trộn hai trục góc; lệch hoặc mâu thuẫn → `CAMERA_CONTRADICTION`, không `PASS`. Validator trả `CAMERA_CONFLICT`/`FRAMING_TAG_MISSING`/`TAG_UPPERCASE`/`QUALITY_TAG_FORBIDDEN`/`TOKEN_BUDGET_EXCEEDED` thì sửa prompt hoặc tạo revision.
- Kiểm tra ngân sách: prompt ≤ 280 từ; vượt ngưỡng thì tag chi tiết sẽ bị mất khi render → cắt tag ưu tiên thấp, không cắt identity anchor.
- Kiểm tra quyết định `PROMPT_DERIVATION` và `policy_version` đã có; không tự kết luận từ nhãn NSFW, không đổi Story để tránh kết quả kiểm tra.

## Phát hiện

Mỗi finding: `{shot_id, rule, status, source_pointer, target_pointer, evidence, suggestion, autofix:false}`. Các mã điển hình: `ACTOR_TARGET_MISMATCH`, `PARTICIPANT_LOSS`, `WARDROBE_COLOR_CHANGED`, `STATE_RESET_UNEXPLAINED`, `VISIBLE_TEXT_CHANGED`, `SCENE_MISMATCH`, `CAMERA_CONTRADICTION`, `FRAMING_TAG_MISSING`, `SAFETY_TAG_MISSING`, `TAG_GRAMMAR_INVALID`, `QUALITY_TAG_PRESENT`, `IDENTITY_ANCHOR_MISSING`, `PROMPT_OVER_BUDGET`, `PROVENANCE_MISSING`.

- `PASS`: Đã kiểm tra và không phát hiện sai lệch theo phạm vi được nêu; không bảo đảm model vẽ đúng.
- `WARN`: Cần người duyệt thêm chi tiết không chắc chắn.
- `BLOCKED`: Có mâu thuẫn nguồn/prompt hoặc lỗi nghiêm trọng đã xác nhận.
- `SKIP`: Chưa chạy một kiểm tra bắt buộc; **không** mặc định PASS.

## Ghi DB

```powershell
python database/src/n2m_workflow.py save-qa --kind PROMPT --subject-id PROMPT_ID --verdict PASS --file report.json
```

`qa_reports` append-only, không sửa bản cũ. Các record `LAYOUT` cũ chỉ là lịch sử trước migration 007; lệnh ghi mới chỉ nhận `STORY/SHOT/PROMPT`. Image/render QA là downstream độc lập, không ghi DB Novel2Anima.
