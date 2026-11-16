# Novel2Anima V4 — Visual Storytelling

## Nâng cấp từ V3

- Thêm skill storyboard-planner, cập nhật orchestrator, story-planner, blind-cast, character-profile, shot-spec, continuity, natural-language-prompt, fidelity-qa, database. Catalog ingest và render adapter giữ nguyên luồng.
- Visual Bible theo Story: role/casting, location, prop, style/tone; lưu provenance. Không tải ảnh hay dữ liệu bên ngoài.
- Storyboard có order số, purpose, camera, focus, visual moment, branch/predecessor, source coverage.
- Continuity world-space theo nhánh; trước/delta/sau và role ngoài khung. V4 delta set/remove tường minh.
- Migration 008 chỉ thêm 8 bảng; giữ nguyên 001–007 và toàn bộ dữ liệu lịch sử.
- save/get/compare/seal storyboard. Seal pin exact Shot/Prompt/QA cùng hash. Export mới theo seal, legacy Story chưa có storyboard vẫn tương thích.
- Repair cục bộ nhận diện slot thay đổi, hậu duệ cần kiểm tra và ứng viên reuse. Không tự tạo nội dung bằng code; agent vẫn viết prompt và thực hiện semantic QA.
- CONTENT_POLICY.md giữ nguyên byte; installer --upgrade không ghi đè policy đích.

## Cài

```powershell
python install.py --target D:\NGV\novel2anima --mode claude --upgrade
cd D:\NGV\novel2anima
python database/src/n2m_db.py init
python database/src/n2m_db.py stats --detailed
```

Khởi động bằng novel2anima-orchestrator. Xem docs/novel2anima/VISUAL_STORYTELLING.md, JSON mẫu storyboard/ShotSpec/continuity/seal và README.

## Kiểm thử

Chạy `python -m unittest discover -s tests -v` từ thư mục ZIP đã giải nén. Test DB/CLI/migration/installer, Blind/Non-Blind, order, branch, coverage, actor-target, camera/location, state và repair. Các test xác thực hợp đồng dữ liệu; không gọi LLM hoặc renderer MOSS, không đo chất lượng ảnh thật.
