---
name: novel2moss-natural-language-prompt
description: "Skill canonical: sinh natural-language positive prompt trực tiếp từ ShotSpec, character catalog, casting và continuity cho MOSS-Image; không đi qua JSON Layout/bbox."
---
# Novel2Moss — Natural-Language Prompt (canonical)

> **Policy:** Luôn đọc `docs/novel2moss/CONTENT_POLICY.md`. Quy tắc nội dung do policy trung tâm quyết định; skill này chỉ điều phối tính chính xác và định dạng.

## Khi sử dụng

Sau khi Story/ShotSpec và Continuity đã có phiên bản rõ ràng, trước QA và export prompt. Áp dụng cho cả Blind và Non-Blind. Đây là **prompt engine duy nhất** của Novel2Moss, không phải bước chuyển tiếp từ Layout.

## Đầu vào

- ShotSpec/revision đã lưu (`shots`, `shot_participants`, `shot_interactions`), Story Event, vai trò actor/target.
- Profile nhân vật, outfit và casting **đang có hiệu lực tại revision**; nếu Blind chưa cast thì dùng mô tả vai trò có căn cứ, không tự bịa danh tính.
- `continuity_snapshots` của Shot, catalog `vocabulary`/`catalog_captions`/tag đã được review.
- Style, camera, scene, visible-text và các ràng buộc đã chốt.
- V4: storyboard slot, purpose, context hash, Visual Bible và state đúng predecessor. Đọc `docs/novel2moss/VISUAL_STORYTELLING.md`. Ưu tiên mô tả visual moment cụ thể; giữ art style nhất quán và tone phù hợp với beat. Dùng mô tả character/loc/prop đã duyệt, không lặp những vật thể ngoài frame.
- `docs/novel2moss/MOSS_NATURAL_PROMPT.md` là hợp đồng định dạng.

## Các bước bắt buộc

1. **Đối chiếu nguồn:** Tải đúng revision, ghi lại source_refs và các điểm chưa rõ. Không tự gán thông tin thiếu trong catalog thành canon.
2. **Lập visual checklist nội bộ:** Số người, identity, outfit, chủ thể hành động, target, tay/cử chỉ, phản ứng, bố cục tương đối, background, camera, light và chữ thực sự nhìn thấy. Checklist chỉ phục vụ QA, không chèn vào positive prompt.
3. **Viết một đoạn mô tả cảnh hoàn chỉnh** bằng tiếng Anh mặc định. Bắt đầu bằng medium/cảnh/hành động chính, sau đó định danh và mô tả từng nhân vật, tương tác và vị trí trái/phải; kết thúc với các chi tiết không gian/camera/ánh sáng cần thiết. Không có thứ tự cứng nếu thứ tự khác làm câu tự nhiên và rõ hơn.
4. **Không kể chuyện thay vì tả hình:** Không viết nguyên diễn biến nhiều bước, lời thoại không hiện trên ảnh, động cơ tâm lý không thể nhìn thấy, hay lệnh kiểu “create/generate”. Không bỏ trạng thái hay vật thể quan trọng đang xuất hiện trong frame.
5. **Không dùng Layout:** Không có `summary`, `items`, bbox, tọa độ pixel, JSON wrapper, Danbooru tag chain hay lời dẫn `Prompt:`. Câu như “on the left” là mô tả trực quan, không phải Layout JSON.
6. **QA:** Đọc lại ShotSpec và prompt. Gọi `novel2moss-fidelity-qa`; chỉ ghi `PASS` khi thực sự đã đối chiếu; không coi validator cấu trúc là bằng chứng đủ.
7. **Lưu bản nháp được duyệt:** Ghi file UTF-8 `natural.prompt.txt`, chạy `n2m_workflow.py save-natural-prompt --shot-id SHOT_ID --file natural.prompt.txt`; lưu prompt ID/revision rồi `save-qa --kind PROMPT`.
8. **Bàn giao:** `n2m_db.py export-bundle --prompt-id PROMPT_ID --out-dir ...` cho Shot đã đủ điều kiện; V4 export cả Story qua `export-story-prompts` sau khi seal storyboard, không tự lấy prompt mới nhất chưa duyệt. Sửa wording cục bộ, tạo revision và QA lại; không tự đổi moment hoặc source.

## Blind và Non-Blind

- **Blind:** role `LEAD`/`PARTNER_A` ổn định ở Story/Shot; nếu chưa có ngoại hình cụ thể, chỉ mô tả phần đã biết. Có thể yêu cầu bổ sung chi tiết ngoại hình trực quan trước khi sinh prompt chất lượng cao, nhưng không tự chọn franchise/canon.
- **Non-Blind:** kiểm tra nhân vật, universe, identity tags, outfit **đã xác minh** và trạng thái; tránh chỉ dùng tên ngắn khó phân biệt.
- Thay casting/outfit cần tạo prompt revision mới và QA lại, không tái sử dụng mô tả cũ làm canon.

## Camera trong prompt

Camera là **một mệnh đề duy nhất**, đủ ba phần: lens + góc + framing, đặt sát câu bố cục và trước hoặc cạnh câu nhân vật.

- Ví dụ đúng: `shot at 35mm from a low angle, full body head to feet`, `shot at 85mm at eye level, upper body`.
- Dùng literal, không dùng ẩn dụ mờ: `directly overhead, looking straight down` (không `top-down view from above`), `low angle, looking up` (không `low-angle view from below`), `shot from behind at a rear three-quarter angle`.
- Không lặp camera ở câu khác, không trộn hai góc trong một prompt, không nhét framing mâu thuẫn (`face close-up` mà vẫn còn hông/đùi trong khung).
- Framing phải khớp phần cơ thể thực sự nhìn thấy; nếu góc cắt mất hành động chính thì đổi framing hoặc ghi rõ bộ phận đang bị crop.
- `tools/novel2moss/validate_natural_prompt.py` trả `CAMERA_CONFLICT` khi prompt chứa hai họ góc cùng lúc; sửa prompt hoặc tạo revision, không vá output sau export.

## Lệnh mẫu

```powershell
python tools/novel2moss/validate_natural_prompt.py drafts/S01.txt
python database/src/n2m_workflow.py save-natural-prompt --shot-id SHOT_ID --file drafts/S01.txt
python database/src/n2m_workflow.py save-qa --kind PROMPT --subject-id PROMPT_ID --verdict PASS --file reports/S01.qa.json
python database/src/n2m_db.py export-bundle --prompt-id PROMPT_ID --out-dir exports/STORY_ID/S01/1
```

## Điều không được làm

- Không tự động flatten/convert prompt từ JSON Layout rồi coi đó là source of truth.
- Không gửi sidecar, JSON metadata hoặc lệnh cho agent vào positive prompt.
- Không dùng LLM để bịa danh tính, đảo actor/target, xóa continuity hay biến cảnh thành storyboard/grid nếu Shot yêu cầu một ảnh.
- Không đưa render job/ảnh/model state vào Novel2Moss DB.

**Đầu ra:** Một file `.txt` natural prompt cho mỗi Shot; JSON manifest/QA là sidecar **không gửi cho model**.
