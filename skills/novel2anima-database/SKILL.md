---
name: novel2anima-database
description: "Quản lý SQLite migration, Story/Shot revisions, catalog và export prompt Anima; DB kết thúc ở prompt, không liên quan render."
---
# Novel2Anima — Database Manager

> Đọc `docs/novel2anima/CONTENT_POLICY.md`, `docs/novel2anima/DATABASE_CONTRACT.md`, `docs/novel2anima/DATABASE_SKILL_MAPPING.md` và `docs/novel2anima/DATABASE_OPERATIONS.md`.

## Khi dùng

Khởi tạo/migrate DB, kiểm tra integrity, truy vấn catalog, lưu Story/Act/Beat/Event/Shot/Continuity, lưu natural prompt revisions, QA trước export.

## Thực thi

1. Chỉ sử dụng repo và DB Novel2Anima, không phụ thuộc project khác.
2. `python database/src/n2m_db.py init`: áp dụng migration 001–008. Migration 008 bổ sung storyboard/bible/coverage/dependency/seal, không sửa migration cũ hoặc dữ liệu lịch sử.
3. `python database/src/n2m_db.py seed`: seed vocabulary và đăng ký các nguồn catalog; **không** thêm layout templates và không tải dataset ngoài mạng.
4. `PRAGMA integrity_check; PRAGMA foreign_key_check;` và kiểm tra lịch sử revision trước/sau ghi.
5. Lưu ShotSpec qua `n2m_workflow.py save-shot`, continuity qua `save-continuity`; lưu natural prompt text qua `save-natural-prompt` (idempotent, append-only khi đổi nội dung).
6. V4: `save-storyboard`, `get-storyboard`, `compare-storyboards` theo `docs/novel2anima/VISUAL_STORYTELLING.md`. Giữ snapshot plan và context hash. Lưu QA `PROMPT` trước `seal-storyboard`; export cả Story chỉ từ seal hiện hành. V3 chưa có storyboard vẫn tương thích.
7. DB dừng tại `natural.prompt.txt` + sidecar. Không ghi render job, seed, checkpoint, ảnh, hậu render QA.

## Nguyên tắc

Không sửa migrations cũ hoặc layout lịch sử. Không tự chuyển bbox cũ sang prompt mới để thay thế ShotSpec. Mọi dữ liệu có nguồn rõ ràng; transaction/foreign key/sha256/revision phải chính xác. Không tuyên bố `PASS` khi chỉ mới chạy kiểm tra cấu trúc.
