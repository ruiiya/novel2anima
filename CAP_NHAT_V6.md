# Novel2Anima V6 — Tổng kết thay đổi từ source mới nhất

**Nguồn triển khai:** `novel2anima(1).zip` do người dùng gửi; không suy đoán nhánh/commit. Không push GitHub.

**Phạm vi:** AI ↔ người dùng hoàn thiện Story → Research/Visual Bible → Storyboard & Continuity → Anima Prompt & QA → Prompt Export. **Không gọi ComfyUI hoặc render ảnh.**

## Đã triển khai

1. **Sửa lỗi baseline:** validator Anima phát hiện hai camera azimuth tag `from side` và `three-quarter view` đồng thời; vẫn cho phép một tag trục height cộng một azimuth phù hợp.
2. **Đồng bộ hợp đồng prompt:** tối đa 3 câu bổ trợ (nhiều người: 4), 320 từ, quality/`score_*` hợp lệ theo validator. Không sửa `CONTENT_POLICY.md`.
3. **Migration `011_studio_process.sql`:** bảng `studio_artifacts`, `studio_decisions`, `studio_feedback`, `studio_exports`, không thay migration 001–010.
4. **CLI `database/src/n2a_studio.py`:** `submit-stage`, `decide-stage`, `status`, `list-stories`, `report-feedback`, `resolve-feedback`, `export`.
5. **Approval Gate:** mỗi stage có artifact, revision, digest và quyết định của người dùng. Không có tự duyệt; `decide-stage` bắt buộc `--user-confirmed` và evidence. Khi Story/Storyboard/prompt mới được lưu, approval cũ trở thành stale; các giai đoạn phụ thuộc được kiểm tra xuyên suốt.
6. **Export V6:** ghim seal và prompt SHA/IDs, xuất `studio.manifest.json`. Các lệnh export legacy bị khóa cho Story đã tham gia Studio nhưng chưa được duyệt `PROMPTS`; Story legacy chưa đăng ký vẫn dùng được lệnh cũ.
7. **Manual feedback:** ghi nhận vấn đề trên trang đã xuất và liệt kê Shot phụ thuộc để xem xét; cho phép mở phiên bản storyboard mới để seal prompt sửa cục bộ, không ghi đè bản cũ.
8. **Skills:** bổ sung `novel2anima-studio-process` (13 tổng), cập nhật 10 skill hiện tại để điều phối approval, Story Review/Immersion, Visual Bible, Continuity và prompt-only flow. Giữ skill render cũ cho tương thích, không gọi trong V6.
9. **Documentation + examples:** `docs/novel2anima/STUDIO_V6.md`, review/research JSON mẫu, cập nhật README và tests.

## Tính tương thích

- Giữ nguyên `CONTENT_POLICY.md` byte-for-byte.
- SQLite migration additive 011, không đụng dữ liệu V5 cũ.
- `--force-new-revision` cho `save-storyboard` nhằm tạo edition mới sau sửa prompt; không đổi behavior mặc định của lệnh.
- Project vẫn là Story → Prompt, renderer độc lập và không nằm trong DB.

## Hướng dẫn bắt đầu

```powershell
# Trong thư mục bản source V6
python database/src/n2m_db.py init
python database/src/n2a_studio.py list-stories
python -m unittest discover -s tests -v
```

Xem `docs/novel2anima/STUDIO_V6.md` để chốt từng stage và xuất prompt theo revision đã được duyệt.

## Giới hạn cần biết

- Review và sáng tác nội dung do AI/người dùng thực hiện theo skill; CLI **không** tự dùng LLM để review hoặc sinh prompt.
- `--user-confirmed` là dấu xác nhận được người điều hành cung cấp, không phải chữ ký mật mã.
- Test kiểm tra quy trình, DB và định dạng prompt, **không** kiểm chứng độ giống nhau của ảnh sinh từ Anima.
- Các lỗi prompt bạn thấy sau render sẽ được tiếp nhận bằng **mô tả văn bản**; không có pipeline đọc và phân tích ảnh tự động.
