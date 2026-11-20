# Novel2Anima V1 — Hợp đồng bảo toàn nội dung nghiêm ngặt

**Hiệu lực:** Bắt buộc với mọi skill Novel2Anima. Đây là hợp đồng **dữ liệu và phép biến đổi**, không phải cam kết mọi đầu vào đều có thể được mọi model/dịch vụ sinh ảnh.

## Nguồn dữ liệu chuẩn

1. Văn bản truyện ban đầu, ghi chú, tên riêng và các chỉnh sửa tường minh của người dùng là nguồn gốc. Lưu bản nguồn bất biến kèm xuất xứ và revision (hoặc content hash bất biến nếu nguồn nằm bên ngoài).
2. Story/Act/Beat/ShotSpec đã xác nhận là dữ liệu chuẩn trong phạm vi tương ứng. Prompt, ảnh, nhận định suy luận và metadata renderer là kết quả phía sau, **không** được thay thế nguồn chuẩn.
3. Giữ **nguyên văn** các nhãn phân loại và ý định của nguồn, gồm nhãn người lớn/NSFW, mức độ, thể loại, quan hệ, mức độ thô bạo, khỏa thân và metadata nhạy cảm khác. Không tự đổi `nsfw` thành `sfw`, `explicit` thành `romance` hoặc sửa thang phân loại. Nhập, tra cứu, lưu và xuất dữ liệu khác với việc nội dung có đủ điều kiện render hay không.
4. Blind Mode, Story Planner và các bước dẫn xuất tuân theo scope được quy định trong `docs/novel2anima/CONTENT_POLICY.md`; hợp đồng fidelity không tự đặt điều kiện nội dung.

## Những yếu tố ngữ nghĩa không được tự ý thay đổi

Qua mọi phép chuyển `Story → Act → Beat → ShotSpec → Natural Prompt`, theo dõi:

- Thứ tự và ID sự kiện; người thực hiện → hành động → người nhận; số lượng, danh tính người tham gia; ai chủ động và ai phản ứng.
- Trạng thái cơ thể, trang phục, màu từng món đồ, tư thế, hướng nhìn, biểu cảm, quyền sở hữu vật thể và quan hệ không gian của từng nhân vật.
- Hệ quả sự kiện trước, trạng thái kế thừa/thay đổi (`carry/delta`), chuyển trạng thái/chuyển cảnh tường minh và revision.
- Ý định cốt truyện, thể loại, sắc thái, cường độ và mọi nhãn nguồn (bao gồm NSFW) đúng như được cung cấp.
- Ràng buộc phải có/không được có, chữ được trích hoặc cần xuất hiện trong ảnh, và các thông tin cố ý để chưa xác định.

V4 bổ sung storyboard làm bước giữa Beat và ShotSpec, source coverage cho toàn bộ Event và sequence QA. Mọi cut, nhánh và slot đều truy vết về nguồn; Visual Bible và seal không được thay thế Story gốc. Xem `VISUAL_STORYTELLING.md`.

**Cấm** tự làm nhẹ, tăng nặng, đảo chiều, gộp, bỏ, bịa hoặc đổi chủ thể các yếu tố trên chỉ để hình đẹp hơn. Caption có thể diễn đạt **phần nhìn thấy** bằng ngôn ngữ tự nhiên; thông tin phân loại không trực quan vẫn phải ở sidecar và không được mất khỏi metadata chuẩn. Positive prompt gửi renderer chỉ là một phép chiếu phần trực quan, không phải toàn bộ cốt truyện.

## Thứ tự ưu tiên khi có mâu thuẫn

1. Chỉnh sửa tường minh mới nhất của người dùng cho chi tiết liên quan (phải ghi revision).
2. Ghi đè Shot đã phê duyệt, có sự kiện hoặc chuyển trạng thái tương ứng.
3. Beat/Act đã xác nhận.
4. Story và danh tính/phong cách nhân vật chuẩn đã xác nhận.
5. Profile mặc định của dự án và dữ liệu tra cứu có nguồn gốc.
6. Suy luận của LLM (bắt buộc đánh dấu `inferred`, không tự nâng thành dữ liệu đã xác nhận).

Nếu hai thông tin cùng cấp đã xác nhận mâu thuẫn, tạo phát hiện `CONFLICT` và yêu cầu quyết định khi thực sự cần. Không tự chọn cách hiểu thuận tiện hơn.

## Sổ đối chiếu nội dung

Mỗi ShotSpec được duyệt **nên có**:

- `source_refs`: ID tài liệu/Act/Beat/Event và hash nguồn.
- `intent.raw_labels`: danh sách nhãn nguyên văn kèm nguồn gốc; `intent.content_profile` nếu có.
- `intent.constraints`: chi tiết bắt buộc và bị loại trừ trong hình ảnh/nội dung.
- `participants[]`: `character_id` ổn định, thông tin tuổi nếu đã xác nhận, vai trò và định danh riêng.
- `interaction`: `actor_id`, `action`, `target_id`, `recipient_reaction`, `event_id`.
- `continuity`: `before`, `delta`, `after`, `cut` và nguồn xác nhận.
- `fidelity_decisions`: ánh xạ và phần cố ý không đưa vào prompt Anima.

Lưu trong sidecar như `shot_spec.json`, `prompt.manifest.json`; không đưa các trường của ứng dụng vào positive prompt dạng text.

## Các dạng sai khác

- `PRESERVED`: Giữ nguyên ý nghĩa; chỉ thay cách diễn đạt.
- `VISUALIZED`: Ý nghĩa được thể hiện bằng hình ảnh; chỉ rõ câu/cụm mô tả trong `natural.prompt.txt`.
- `NON_VISUAL_SIDECAR`: Metadata có ý nghĩa được giữ trong sidecar, cố ý không đưa vào prompt ảnh.
- `UNRESOLVED`: Chưa đủ bằng chứng; không được tự tạo dữ kiện.
- `CONFLICT`: Các yêu cầu đầu nguồn mâu thuẫn.
- `LOSS`: Ý nghĩa bắt buộc từ nguồn bị mất hoặc bị đổi.
- Quyết định nội dung (`REVIEW_REQUIRED`, `POLICY_BLOCKED`) và lỗi backend (`BACKEND_REJECTED`) được quy định thống nhất trong `docs/novel2anima/CONTENT_POLICY.md`.

`LOSS` và `CONFLICT` ngăn phát hành artifact sai ngữ nghĩa cho tới khi khắc phục. Kết quả về chính sách được xử lý riêng theo scope trong `CONTENT_POLICY.md`; QA không tự ghi đè dữ liệu chuẩn.

## Ví dụ các thay đổi ngầm bị cấm

- A xoa đầu B → B xoa đầu A.
- Trang phục xanh → đen chỉ vì trông đẹp hơn.
- Nội dung nguồn được phân loại explicit → tự đổi thành nhãn SFW mơ hồ khi chưa được yêu cầu.
- Ba nhân vật có danh tính → hai nhân vật vô danh để dễ bố cục.
- Dấu vết thể chất đã xác nhận → cảnh sau tự trở về sạch sẽ/nguyên trạng mà không có sự kiện chuyển tiếp.
