---
name: novel2anima-shot-spec
description: "Chuyển một Beat đã xác nhận thành ShotSpec trực quan chuẩn với vai trò, hành động, trạng thái, biểu cảm, camera và ý định nội dung bất biến."
---
# Novel2Anima — Xây dựng ShotSpec

## V5: khoảnh khắc chính xác và prompt blocks

Đọc `docs/novel2anima/NARRATIVE_CONTINUITY.md`. Lấy approved slot và scene, xác định đúng một visual moment, actor/target, tay/vật đang tiếp xúc, state tại thời điểm chụp, frame visibility và world-space khác screen-space. Nếu cả hai role của Event tương tác đều nhìn thấy, ghi interaction có event_id và action_text khớp Event. Chỉ dùng dynamic `prompt_blocks` prefix/subjects/action/camera/prose; các tag identity/outfit/location/lighting/props/style lấy từ Bible và moment bởi compiler. Dùng ShotSpec revision mới khi chỉnh block. Không thay thế context hash bằng shot_order.

> **Policy nội dung bắt buộc:** Đọc `docs/novel2anima/CONTENT_POLICY.md` trước khi xử lý. Mọi quyết định nội dung tuân theo scope và phiên bản tại đó; skill này không tự đặt chính sách khác.

## Vai trò

Tạo **một đặc tả hình ảnh chuẩn cho mỗi Shot**, không phải prompt cuối. Đọc `docs/novel2anima/CONTENT_FIDELITY.md` và ví dụ `examples/shot_spec.example.json`.

## Thứ tự ưu tiên nguồn

Chỉnh sửa người dùng > ghi đè Shot đã duyệt > Beat đã duyệt > Act > Story/canon > catalog/mặc định > suy luận. Nếu hai nguồn có thẩm quyền mâu thuẫn, báo lỗi; không tự xử lý bằng sáng tác.

## Với mỗi Shot

Trong V4 đọc storyboard đã duyệt bằng get-storyboard; lấy đúng slot, `visual_context_sha256` từ context_sha256, camera, focus, location_key, purpose, role_keys, style và props. Interaction phải có event_id trong coverage của slot và actor/target chính xác. Không tự tạo shot_key khác. Đọc `docs/novel2anima/VISUAL_STORYTELLING.md`. Mẫu mới `examples/shot_spec_v4.example.json` tương thích CLI; mẫu V1 chỉ minh họa semantic fields.

- Gắn `shot_id`, `story_id`, `act_id`, `beat_id`, `event_id`, `source_refs`.
- Liệt kê từng người bằng **character ID ổn định**, kèm điểm nhận diện và vai trò. Không suy tuổi trưởng thành, tên, franchise hay danh tính từ tag ảnh bất kỳ.
- Xác định `interaction.actor_id → primary_action → interaction.target_id`, người giữ đạo cụ (nếu có) và biểu cảm/phản ứng của người nhận. Dùng `target_id: null` khi thực sự không có đối tượng nhận; không đảo chiều.
- Mô tả độc lập tư thế, hướng nhìn, biểu cảm, tay/cử chỉ và quan hệ không gian của mỗi người. Không để nhân vật này tự kế thừa mô tả của nhân vật khác.
- Viết tư thế theo **cơ học cơ thể**: hướng thân, vị trí tay/chân, điểm tiếp xúc, ai tác động lên ai. Caption phải nêu hành động nhìn thấy trong khung; nếu cận mặt không thấy hành động, ghi rõ bộ phận/điểm tiếp xúc đang được crop.
- Lấy định danh/outfit từ profile; ghi **màu chính xác của từng món đồ** hoặc báo chưa xác định. Việc thay đổi có chủ đích là state delta, không phải mâu thuẫn cần xóa.
- Kế thừa trạng thái đã xác nhận từ trước, áp dụng delta tường minh rồi suy ra `after`; phân biệt cut với mutation. Trạng thái chưa rõ/suy luận phải có nhãn tương ứng.
- Ghi cảnh nhìn thấy, background cụ thể (loại phòng, đồ vật, chất liệu, nguồn sáng), camera, ánh sáng, composition; không để góc quay lạ làm mất hành động quan trọng.
- Camera ghi thành **hai tag chuẩn Anima**: một framing (`close-up` / `upper body` / `cowboy shot` / `full body` / `wide shot`) + một angle (`from above` / `from below` / `eye level` / `from side` / `three-quarter view`); thêm lens feeling (`wide angle`, `telephoto`, `shallow depth of field`) chỉ khi cần. Không dùng số mm, không dùng cụm mờ kiểu `dynamic angle`, không ghép hai framing hoặc hai angle cùng trục, và không đặt framing mâu thuẫn với pose (`close-up` nhưng hành động nằm ở hông). Nếu góc cắt mất hành động chính, đổi framing và ghi rõ bộ phận đang bị crop. Danh sách đóng: `docs/novel2anima/ANIMA_TAG_PROMPT.md`.
- Phân biệt vị trí world-space và screen-space: camera reverse có thể đổi trái/phải trên ảnh, nhưng không đổi tay trái/phải cơ thể, người thực hiện hoặc người nhận. Áp dụng các anchor cố định của Location/Prop/Style Bible; không copy nguyên cả Bible vào frame nếu chi tiết khuất.
- Giữ `intent.raw_labels`, `intent.content_profile`, văn bản nguồn và các ràng buộc trong sidecar; không đổi phân loại nhạy cảm sang loại khác.
- Nếu một khung hình không thể biểu diễn trung thực hành động, báo điểm chưa rõ hoặc đề xuất tách Shot, nhưng **không tự bịa thêm sự kiện truyện**.

## Hợp đồng ShotSpec

`examples/shot_spec.example.json` là minh họa, **không** khẳng định ứng dụng có các cột DB cùng tên. Có thể ánh xạ sang cấu trúc lưu trữ thật nếu giữ nguyên ý nghĩa, khả năng truy vết và trạng thái. Các yếu tố ngữ nghĩa bắt buộc từ nguồn tới prompt nằm trong hợp đồng chung.

## Các hành vi bị cấm

- Gộp nhiều hành động khác thời điểm thành một cử chỉ đồng thời gây nhầm chiều tương tác.
- Bịa nhân vật thứ hai, đổi tay/đạo cụ đang hoạt động, thay outfit khác hoặc âm thầm xóa trạng thái cơ thể tích lũy.
- Chép ID/nhãn phân loại nội bộ của ứng dụng trực tiếp vào Anima positive prompt.
- Coi nhãn NSFW chung chung là đủ chứng cứ về tuổi hoặc điều kiện nội dung.

## Bàn giao

Trả `ShotSpec` kèm các phát hiện `UNRESOLVED` hoặc `CONFLICT` nếu có. Skill này không tự phân loại điều kiện render; việc đó thuộc scope `PROMPT_DERIVATION` của policy. Tiếp theo là Continuity Check và Anima Prompt.

## Shot persistence trong Database

- Đọc `beats`, `story_events`, `story_roles`, `story_castings`, `characters/outfits`, `vocabulary` và trạng thái Shot trước. `actor_role_key/target_role_key` ánh xạ sang `story_role_id` cùng Story.
- Ghi `shots.shot_spec_json` và tạo đồng thời `shot_participants`, `shot_interactions` bằng `n2m_workflow.py save-shot`. Không ghi đè Shot cũ: thay đổi nội dung phải tăng revision và đặt `supersedes_shot_id`.
- Gắn `source_event_id` nếu Shot được tạo từ một Event cụ thể; CLI yêu cầu Event thuộc chính Beat đó. Tránh tự tạo mã nhân vật và outfit chưa có trong Catalog.
- Không ghi `character_id` trực tiếp vào quan hệ hành động; lưu danh tính thật ở `story_castings`. `ShotSpec` được phép giữ role tạm trong Blind Mode.
