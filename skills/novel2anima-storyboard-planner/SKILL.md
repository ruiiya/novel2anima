---
name: novel2anima-storyboard-planner
description: "Biến Story/Act/Beat/Event đã duyệt thành storyboard có nhịp kể, Shot purpose, Visual Bible, thứ tự/nhánh, coverage nguồn và kế hoạch sửa cục bộ cho Novel2Anima; dùng cho Blind và Non-Blind trước ShotSpec."
---
# Novel2Anima — Storyboard Planner

## V5: scene lock và kế hoạch shot liên kết

Đọc `docs/novel2anima/NARRATIVE_CONTINUITY.md` và `examples/storyboard_v5.example.json`. Dùng `schema_version: 5` cho storyboard mới. Kế hoạch toàn bộ scene trước khi viết slot: narrative_role, story_time, scene_key, danh sách role cả ngoài frame, ánh sáng, location landmarks, outfit version, canonical prompt_tags. Chọn `INDEPENDENT` (không predecessor) cho pose độc lập, `SAME_MOMENT` cho góc khác cùng thời điểm, `FLASHBACK` cho nhánh lịch sử có anchor; giữ các transition V4. Tại mỗi slot chọn visible_location_tags, role_keys, prop_keys đúng camera; đừng nhét toàn bộ scene vào close-up. Giữ trục không gian, eyeline, hướng di chuyển và nhịp kể hợp lý. Các quy tắc V5 này bổ sung/thay thế quy tắc transition V4 ở dưới; storyboard lịch sử giữ nguyên.

Đọc `docs/novel2anima/CONTENT_POLICY.md` và `docs/novel2anima/VISUAL_STORYTELLING.md`. Chỉ lập kế hoạch hình ảnh; không tạo prompt cuối hoặc render.

## Điều kiện vào

- Story Brief đã được người dùng chốt; materialize Act, Beat, Event và role theo Story Planner.
- Non-Blind: khóa casting/outfit đã xác nhận. Blind: giữ role ổn định, có visual description và provenance đủ dùng; chưa biết đặc điểm nào thì ghi unknown, không tự đoán canon.
- Đọc nguồn, plan revision, các lựa chọn của người dùng và Visual Bible hiện có. Nếu sửa, đọc storyboard cũ và seal.

## Quy trình

1. Lập danh sách Event nguồn, nguyên nhân → hành động → phản ứng → hệ quả. Ghi những gì có thể nhìn thấy, những gì chỉ là ngữ cảnh. Không tạo thêm plot, sửa nhãn gốc hoặc bỏ Event để dễ vẽ.
2. Tạo Visual Bible có scope trong Story: nhân vật/role, location, props, style/tone. Mỗi entry có stable key, description, provenance; ghi chính xác những gì đã khóa và phần chưa rõ. Danh tính canonical lấy từ Character Profile, không ghi đè catalog.
3. Chọn khoảnh khắc hình ảnh theo từng Event. Mỗi Shot là một thời điểm, một focal intent và một camera. Có thể tách preparation/action/reaction/aftermath nếu cần thể hiện đầy đủ; không áp quota Shot/Act hoặc dùng mọi loại Shot một cách máy móc.
4. Chọn purpose: ESTABLISHING, ACTION, REACTION, DETAIL, TRANSITION, CLIMAX hoặc AFTERMATH. Định hướng focus, camera, visual moment, role_keys, location_key, prop_keys, style_key. Chọn camera nhìn được hành động cần thể hiện; giữ đủ đặc điểm nhân vật biết được trong frame.
5. Đặt thứ tự số tăng dần, shot_key không phụ thuộc thứ tự. Dùng START cho Shot đầu, CONTINUOUS/CAMERA_CUT/TIME_CUT/LOCATION_CUT cho chuỗi; BRANCH khi tạo nhánh có predecessor tường minh. Không nối trạng thái từ Shot cuối của nhánh khác chỉ vì gần nhau trong danh sách.
6. Đối chiếu từng Event với coverage VISUALIZED (một hoặc nhiều Shot), CONTEXT_ONLY (có lý do), UNRESOLVED hoặc UNSUPPORTED_CONTENT (chỉ khi có quyết định policy có căn cứ). Một Shot có thể ánh xạ nhiều Event cùng Beat nếu thật sự cùng khoảnh khắc. Mọi trạng thái đều có evidence, không bỏ nguồn.
7. Trình storyboard ngắn dạng bảng số thứ tự, purpose, moment, role, góc máy, coverage và vấn đề chưa giải quyết. Chờ xác nhận rõ ràng trước khi lưu. Không tự coi Story approval là storyboard approval.
8. Lưu storyboard bằng `save-storyboard`; đọc lại `get-storyboard` để lấy slot và context_sha256. Bàn giao cho ShotSpec/Continuity. JSON chỉ là dữ liệu kế hoạch nội bộ, tuyệt đối không phải prompt gửi model, và camera phải dùng tag chuẩn Anima (`docs/novel2anima/ANIMA_TAG_PROMPT.md`).
9. Sau QA prompt và sequence, `seal-storyboard` ghim chính xác Shot ID, Prompt ID, QA ID, continuity hash. Nếu bất kỳ Event chưa giải quyết, không seal/xuất toàn bộ như đã hoàn thành. Các Shot hợp lệ có thể bàn giao riêng theo policy.

## Sửa cục bộ

- Xác định lỗi thuộc Story, Visual Bible, slot direction, state, hay wording của prompt.
- Giữ Shot key khi sửa cùng khoảnh khắc. Tạo storyboard revision mới (thêm revision_note nếu chỉ đổi wording/prompt binding; giữ nguyên slot không ảnh hưởng).
- So context_sha256 và predecessor state: chỉ tái tạo ShotSpec/prompt cần thiết; không tái sử dụng nếu source/casting/Bible liên quan đã đổi. Chạy lại coverage và sequence QA.
- Dùng seal cũ để đối chiếu, không sửa lịch sử. Không yêu cầu runtime cụ thể, hình reference, ComfyUI, bbox hay gộp panel.

## Đọc/ghi DB

Đọc `story_revisions`, `story_events`, `story_roles`, `story_castings`, catalog và storyboard hiện hành. Ghi bằng CLI trong `docs/novel2anima/VISUAL_STORYTELLING.md`; schema 008 lưu storyboard, slot, location/prop/style, dependencies, coverage, seal. Dùng `--expected-revision` để tránh cập nhật dựa trên bản cũ.
