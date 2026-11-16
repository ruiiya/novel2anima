---
name: novel2moss-continuity
description: "Theo dõi before/delta/after của Novel2Moss qua các Shot và nhánh, tránh tự reset trang phục, màu sắc, đạo cụ, tư thế hoặc hệ quả câu chuyện."
---
# Novel2Moss — Tính liên tục và quản lý trạng thái

> **Policy nội dung bắt buộc:** Đọc `docs/novel2moss/CONTENT_POLICY.md` trước khi xử lý. Mọi quyết định nội dung tuân theo scope và phiên bản tại đó; skill này không tự đặt chính sách khác.

## Vai trò

Duy trì trạng thái quan sát được qua `Story → Act → Beat → Shot`. Đọc `docs/novel2moss/CONTENT_FIDELITY.md`. Skill này phát hiện sai khác và đề xuất revision, **không** âm thầm ghi đè Story đã xác nhận hoặc Shot đã duyệt.

## Các nhóm trạng thái (có thể mở rộng)

Theo nhân vật: định danh, tóc, các phần trang phục và màu sắc, phụ kiện, vị trí, tư thế, ánh nhìn, biểu cảm, đạo cụ đang giữ, dấu vết nhìn thấy/hệ quả cơ thể và vai trò tương tác hiện tại. Theo cảnh: thời gian, địa điểm, ánh sáng, đạo cụ chính, vị trí và danh sách người xuất hiện. Metadata: nhãn nguồn/ý định, revision, provenance.

## Thuật toán

V4: Đọc storyboard slot/predecessor/transition và Visual Bible. Dùng snapshot scene role NULL và mỗi role hiện diện; delta dạng set/remove theo `docs/novel2moss/VISUAL_STORYTELLING.md`. Kế thừa cả state của role tạm ngoài khung qua ancestry; dừng khi before lệch after của tổ tiên gần nhất. Không trộn world-space với left/right của camera. Thay location/prop owner/time/light bằng delta có evidence, không reset khi cut.

1. Đọc `after` **đã xác nhận** ở Shot trước, sự kiện hiện tại và `delta` tường minh của Shot hiện tại (bao gồm cả các mục bị loại bỏ).
2. Đề xuất `before = previous after` cho cùng chuỗi cảnh liên tục và tôn trọng ranh giới nhánh. Không lấy trạng thái từ Story khác chỉ vì trùng `character_id`.
3. Chỉ áp dụng delta được ghi rõ; không tự suy diễn việc cởi/mặc lại đồ, dọn sạch, dấu vết biến mất, chuyển quyền giữ đạo cụ hoặc đổi kiểu tóc chỉ để thuận tiện tạo hình.
4. Phân biệt `camera_cut`/`time_cut` với thay đổi trạng thái thật. Chuyển cảnh có thể bỏ qua chuyển động trung gian, nhưng việc đổi trang phục/quyền sở hữu vẫn cần sự kiện hoặc mô tả tường minh.
5. So sánh `after` hiện tại với `before` của Shot kế tiếp; tạo phát hiện có bằng chứng cho các đoạn nối bị thiếu, mâu thuẫn, đảo actor/target hoặc reset ngoài ý muốn.
6. Với trạng thái suy luận, lưu bản ghi quan sát có phiên bản quy tắc suy luận và confidence; không tự nâng thành trạng thái đã xác nhận.
7. Khi revision được phê duyệt, giữ nhánh/generation cũ và chỉ tính lại các phần hậu duệ bị ảnh hưởng.

## Nhánh truyện và số nhân vật

Một nhân vật có thể thuộc nhiều Story. Mỗi nhánh có con trỏ trạng thái trước riêng và chuỗi thay đổi riêng. Hỗ trợ solo, duo hoặc group như những cấu trúc dữ liệu; theo dõi từng người độc lập.

## Mặc định quan trọng

Không coi heuristic về cooldown, reset, cường độ, trang phục hay độ sạch là sự thật bắt buộc. Dùng `unknown` thay vì bịa trạng thái cơ thể. Chỉnh sửa tường minh của người dùng ưu tiên hơn quy tắc suy luận.

## Đầu ra

Trả báo cáo chuyển trạng thái `PASS`, `WARN` hoặc `BLOCKED`, các path/ID bị ảnh hưởng, sai khác chính xác và đề xuất sửa **tối thiểu ở nguồn phù hợp**. Bản báo cáo QA tự nó **không** thực hiện sửa dữ liệu.

## Lưu continuity vào Database

- Đọc `shots` đúng revision, `story_roles`, `continuity_snapshots` của Shot trước **trên đúng nhánh**; nếu thiếu ancestry/branch metadata, không tự nối state khác Story hoặc chọn shot theo thời gian tạo.
- Với `before/delta/after` có cấu trúc, gọi `n2m_workflow.py save-continuity` để lưu theo khóa `(shot_id,story_role_id)`, hoặc role NULL cho trạng thái cảnh; không gộp nhiều role vào một row.
- Ghi lại cùng nội dung phải idempotent. Nếu snapshot cũ khác, trả `CONFLICT` và tạo Shot revision mới trước khi lưu lại; không UPDATE/DELETE lịch sử.
- Nếu chỉ thay continuity, cập nhật continuity_revision_note với lý do/evidence trong ShotSpec để save-shot tạo revision mới; không tự ghi đè snapshot.
- `shots.shot_spec_json` không được tự sửa khi làm QA, và `story_castings` thay đổi không tự reset continuity.
