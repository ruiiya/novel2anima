# Novel2Moss — Acceptance V4 Visual Storytelling

1. Story/ShotSpec giữ nguyên nguồn, nhãn và provenance. Chỉ policy trung tâm xử lý quyết định nội dung, không đổi nguồn để vượt kiểm tra.
2. Blind Story/Shot có thể tồn tại trước casting; Non-Blind chọn identity/outfit trước. Cả hai cùng dùng `shot_prompts`.
3. Mỗi Shot hiện hành có đúng một **natural prompt canonical** tại revision được chọn; văn bản mô tả hình ảnh hoàn chỉnh, không có Layout JSON, bbox hoặc code fences.
4. Hai người: giữ actor, target, vị trí tương đối, ngoại hình, outfit/màu, pose, biểu cảm, camera và tương tác.
5. Một người: không tự thêm nhân vật/đồ vật không có nguồn.
6. Trạng thái continuity/đạo cụ/trang phục chỉ thay khi có `delta` hoặc cut rõ ràng.
7. Văn bản cần xuất hiện trong hình được giữ nguyên; không tự chèn lời thoại nguồn thành chữ visible.
8. Prompt phải tự đủ ngữ cảnh để render Shot riêng; không chỉ nói “same as previous image” mà thiếu mô tả.
9. Dữ liệu Layout V2 vẫn còn sau migration 007; không phát sinh bản Layout mới từ các lệnh V3.
10. `save-natural-prompt` idempotent, khác text tăng revision; prompt và QA lịch sử không được sửa/xóa.
11. `export-bundle` tạo `natural.prompt.txt`, `prompt.manifest.json`, `fidelity_report.json`, hash khớp byte của `.txt`.
12. `export-story-prompts` V4 dùng exact sealed Shot/Prompt/QA revision; legacy chưa có storyboard dùng current Shot. File JSONL có prompt string và một dòng trống giữa record.
13. Không có `render_jobs`/`render_assets`/`qa_reports` chủ đề `RENDER`; có thể render bằng file khi SQLite đóng.
14. Kiểm tra standalone trên project trống và nâng cấp V2 bằng migration mới, không mượn code/DB dự án khác.
15. Kiểm tra cấu trúc prompt **không đồng nghĩa** kiểm tra fidelity hoặc chất lượng ảnh. Báo rõ những phần chưa chạy/ngoài phạm vi.
16. Mọi materialized Event có coverage/tình trạng/evidence, không được mất Event.
17. Thứ tự Shot dạng số, predecessor đúng nhánh; camera cut không làm đổi world state. Role ngoài frame giữ state.
18. Context hash phản ánh source, visual direction, casting và Bible. Thay casting hoặc sửa slot không được reuse artifact stale.
19. Seal từ chối thiếu QA, coverage chưa giải quyết, sai actor/target, delta hoặc continuity break. Không export storyboard chưa seal.
20. Migration 008 giữ dữ liệu V3; repair chỉ tạo revision mới, có báo cáo impacted descendants; không thay seal trước.
