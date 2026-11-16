---
name: novel2moss-blind-cast
description: "Lập kế hoạch Novel2Moss với vai trò tạm thời khi chưa chọn nhân vật; gán nhân vật sau mà không đổi ý nghĩa sự kiện hoặc mất nhãn nội dung."
---
# Novel2Moss — Vai trò tạm thời và gán nhân vật sau (Blind Cast)

> **Policy nội dung bắt buộc:** Đọc `docs/novel2moss/CONTENT_POLICY.md` trước khi xử lý. Mọi quyết định nội dung tuân theo scope và phiên bản tại đó; skill này không tự đặt chính sách khác.

## Khi nào sử dụng

Đã có nội dung Story nhưng danh tính một hoặc nhiều nhân vật được chủ ý để trống. Đây là skill tùy chọn, bổ trợ cho Story Planner, ShotSpec và Continuity.

## Quy trình

V4: Khi lập storyboard, Visual Bible characters dùng role_key ổn định, description có provenance, character_id/outfit_id null nếu chưa cast. Gán casting về sau làm thay story_revision và context hash của slot liên quan; kiểm tra lại các Shot đó, không thay Event hoặc nhãn nguồn. Đọc `docs/novel2moss/VISUAL_STORYTELLING.md`.

1. Cấp ID vai trò ổn định (`LEAD`, `PARTNER_A`, `OTHER_1`) và duy nhất trong Story. **Không** bịa tên nhân vật canon, thương hiệu/tác phẩm, tuổi hoặc người thật.
2. Lưu nguyên truyện ở cấp vai trò cùng nhãn phân loại nguồn. Chưa biết danh tính **không đồng nghĩa** được quyền tự gán tuổi trưởng thành hoặc mặc định yêu cầu render đủ điều kiện.
3. Nếu cần hình dung để lập bố cục, dùng **visual placeholder chung** và đánh dấu rõ là tạm thời; chỉ thêm các đặc điểm ngoại hình đã được xác nhận. Không nhận đó là nhân vật canon.
4. Theo dõi riêng actor/target, phản ứng, hướng nhìn, tư thế, trang phục và trạng thái theo từng vai trò. Blind cast không đồng nghĩa chỉ có một nhân vật.
5. Khi một profile thật được chấp thuận, gắn vai trò với `character_id`, cập nhật đồng bộ toàn bộ tham chiếu và điểm nhận diện phụ thuộc **theo transaction** hoặc trong một tập artifact revision mới; kiểm tra mọi xung đột.
6. Sinh prompt revision mới thay vì ghi đè những ảnh đã duyệt ở revision placeholder trước.

## Blind Mode — tiếp nhận và gán vai trò

- **Blind Mode chấp nhận mọi story** để lưu và lập cấu trúc ở scope `SOURCE_INGEST`/`STORY_ANALYSIS`, không tự kiểm tra điều kiện sinh prompt ngay khi nhập.
- Giữ mọi nhãn, provenance và thông tin chưa rõ theo đúng nguồn; không làm biến dạng truyện.
- Khi chuyển sang bước tạo prompt, chuyển quyền đánh giá `PROMPT_DERIVATION` cho policy trung tâm; không tự suy ra `UNSUPPORTED_CONTENT` từ tag hoặc danh tính chưa gán.

## QA

Sau khi gán profile, caption biên dịch không được còn placeholder mồ côi, không đổi chiều tương tác, không tăng/giảm số nhân vật, không mất nhãn Story và vẫn truy xuất được revision cũ.

## Database và casting revision

- `stories.cast_mode=BLIND` là dấu hiệu chọn nhánh. Tạo role trong `story_roles` ngay khi tạo Story, cho phép `story_castings` rỗng khi Story/Shot được lập.
- Actor, target trong `story_events`/`shot_interactions` **luôn** trỏ `story_role_id` cùng Story, không lưu trực tiếp `character_id`; vì thế gán nhân vật sau không thay nội dung sự kiện cũ.
- Sau khi người dùng chọn catalog profile thật, gọi `n2m_db.py bind-role`, lưu `character_id/outfit_id/from_revision`; bản cũ có `until_revision`. Tạo natural prompt revision mới nếu điểm nhận diện thay đổi; giữ nguyên Shot và export lịch sử.
- Không tự tạo nhân vật giả để lấp FK, không coi chưa casting là lỗi dữ liệu; báo `UNASSIGNED_ROLE` cho những bước thực sự cần identity. Đọc `DATABASE_CONTRACT.md`.
