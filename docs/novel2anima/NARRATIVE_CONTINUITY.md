# V5 — Narrative & Visual Continuity

Một pipeline duy nhất Story → Storyboard → ShotSpec → Continuity → Anima Prompt → QA → seal/export. Blind/Non-Blind là casting mode; tuyệt đối không thêm chế độ Album/Comic. Phân loại quan hệ ở từng shot. V4 giữ nguyên khi không có `schema_version: 5`; story mới sử dụng V5. Đọc `CONTENT_POLICY.md` và `ANIMA_TAG_PROMPT.md` như trước.

## 1. Storyboard và nhịp kể

Lập kế hoạch toàn bộ scene trước khi viết shot. Materialize Event theo nguồn đã duyệt; một shot thể hiện một khoảnh khắc. Chọn `narrative_role` theo nhu cầu (ESTABLISH, INITIATE, PROLONG, PEAK, REACTION, RESOLUTION, TRANSITION, DETAIL); không ép đủ loại hoặc số shot. Shot độc lập có thể null. Giữ source coverage V4; không tạo Event ngoài nguồn. `story_time` là mốc tương đối nguyên không âm, khác `shot_order` (thứ tự đọc). Các mốc ngang nhau biểu thị cùng khoảnh khắc nếu chọn SAME_MOMENT.

| transition | predecessor | hợp đồng |
|---|---|---|
| START | null, shot đầu | baseline rõ ràng |
| INDEPENDENT | null | không kế thừa world state, vẫn lấy Bible/casting |
| CONTINUOUS / CAMERA_CUT | branch tail | cùng scene, before = after của predecessor |
| TIME_CUT / LOCATION_CUT | branch tail | giữ trạng thái cũ đến khi delta tường minh đổi nó |
| SAME_MOMENT | branch tail | cùng scene và story_time, cùng before/at/after, góc nhìn có thể khác |
| BRANCH | shot thuộc nhánh khác | fork đúng trạng thái cuối predecessor |
| FLASHBACK | shot lịch sử đã lập, nhánh mới | cùng scene/time/before/at/after với mốc lịch sử; quay về nhánh chính bằng tail cũ |

Flashback chưa có mốc lịch sử: lập một baseline INDEPENDENT có bằng chứng nguồn trong nhánh riêng, không lấy state hiện tại giả làm quá khứ. Không tự thêm event để tạo bridge.

## 2. Scene Lock và Bible

Trong approved storyboard, `schema_version: 5`, thêm `scenes` map theo stable key. Mỗi scene có `location_key`, `style_key`, `time_key`, `role_keys` gồm cả nhân vật không nhìn thấy trong shot, `lighting_tags`. Shot trỏ `scene_key`, `story_time`, `narrative_role`, `visible_location_tags` (subset tag của location). `role_keys` và `prop_keys` của shot chỉ gồm những gì xuất hiện trong frame. Tất cả role đang thuộc scene phải có snapshot, kể cả ngoài khung. Đọc `examples/storyboard_v5.example.json` (installer: dưới `examples/novel2anima`).

Trong Visual Bible, mỗi character, location, prop, style có `prompt_tags` danh sách tag lowercase đã đối chiếu nguồn/catalog. Character/style cần tag anchor không rỗng. Character có thể thêm `outfits` map `outfit_key` → `prompt_tags`; nếu có, moment và after của role phải chọn đúng outfit version. Không tự suy ra màu/nhận diện chưa biết. Mang cùng các anchor từ shot này sang shot khác, không viết lại từ đồng nghĩa.

Ghi description location về danh mốc và tương quan vật lý, nguồn sáng, hướng đi, camera axis. Khi chuyển góc máy, world-space giữ nguyên; screen-space có thể thay đổi. Chọn landmark nhìn thấy theo camera; không đưa cả phòng vào ảnh cận. Quy tắc 180° là hướng dẫn dàn dựng, có thể vượt trục nếu chủ đích và QA giải thích. Không lưu tọa độ canvas hoặc layout prompt.

## 3. Continuity / World State

Giữ `before`, `delta`, `after` của V4. Mỗi snapshot thêm `moment`:

```json
{"at_shot":{"holding":"notebook"},"at_delta":{"set":{"holding":"notebook"},"remove":[]},"after_delta":{"set":{"holding":null},"remove":[]}}
```

`apply_delta(before, at_delta) == at_shot`; `apply_delta(at_shot, after_delta) == after`; tổng `delta` cũng phải cho after. Dùng set/remove top-level, không thay đổi ngầm. Scene snapshot (`role_key:null`) tại moment và after phải có location_key/time_key khớp scene. Mỗi role dùng state như outfit_key, pose, vị trí vật lý, hướng, biểu cảm, đồ đang giữ; scene có thể ghi prop ownership/placement. Chọn trường liên quan truyện và giữ schema nhất quán. Đối tượng/role ngoài frame không reset. Đối chiếu quyền sở hữu đạo cụ giữa các role và scene; Python kiểm tra delta/kế thừa, agent kiểm tra ngữ nghĩa.

## 4. Prompt compiler

Các file mẫu đồng bộ với storyboard: `examples/shot_spec_v5.example.json` và `examples/continuity_v5.example.json`. Thay ID và nội dung theo source; không coi mẫu là kết quả QA.

ShotSpec giữ nguyên các trường V4 và context hash, thêm `prompt_blocks` gồm chính xác:

```json
{"prefix":["masterpiece","best quality","safe"],"subjects":["1girl","1boy"],"action":["holding book"],"camera":["upper body","eye level"],"prose":"The man on the left offers the blue notebook to the woman on the right."}
```

LLM chọn các block động theo nguồn và policy hiện hành, viết câu mô tả rõ vai trò, vị trí/mối tương tác. Không chép các tag khóa sang action/camera để đổi chúng. Compiler lấy đúng context hash, state tại moment, identity/outfit của visible roles, location subset, lighting, visible props và style. Loại tag trùng giữ thứ tự, chặn tag khóa từ entity không hoạt động, chạy validator Anima. Không tự thêm semantic, không tự ghi QA PASS. Kiểm tra nghĩa, đồng âm trái/phải, gán đặc điểm đúng người và mâu thuẫn các tag ngoài Bible bằng QA thủ công/LLM. Khi cần chỉnh wording/prompt_blocks, tạo ShotSpec revision mới và lưu continuity tương ứng; không chỉnh file prompt thành nguồn chuẩn.

```bash
python database/src/n2m_workflow.py compile-prompt --shot-id SHOT_ID
python database/src/n2m_workflow.py compile-prompt --shot-id SHOT_ID --save
```

Lệnh trả JSON gồm prompt, khi --save có ID/revision. `save-natural-prompt` từ chối prompt khác compiler nếu Shot thuộc V5. Đầu ra vẫn một text Anima, không gửi scene, moment, JSON hoặc sidecar cho renderer.

## 5. QA và export

Sau QA từng prompt, lập `sequence_qa.shot_checks` map mỗi shot_key → `{verdict: PASS, evidence: ...}`. Evidence thật phải nêu predecessor, moment, khóa đang hiệu lực, action/actor/target, camera, continuity các đối tượng ngoài frame và lý do các thay đổi. Với independent, kiểm tra Bible, không ép nối pose. Đừng coi syntax PASS là semantic PASS. Chặn seal nếu thiếu bất kỳ review, sai prompt compiler, sai trạng thái hoặc coverage. Seal/export giữ V4 provenance và thêm scene/time/narrative_role/transition. Sửa một shot: compare storyboard, QA lại hậu duệ thật sự phụ thuộc; shot độc lập không bị lan truyền nếu Bible không đổi.

## 6. Migration và giới hạn

Migration 009 thêm moment_json nullable và mở rộng dependency transition, giữ các row và seal V4. Schema scene/Bible/prompt blocks nằm trong JSON revision bất biến hiện có, không tạo kho dữ liệu song song. Dùng installer --upgrade và `n2m_db.py init`; sao lưu DB production trước khi nâng cấp. Story V4 đã seal vẫn đọc/export theo hợp đồng V4; muốn dùng V5 thì tạo storyboard version mới, không sửa lịch sử. Không thêm renderer, reference-image workflow, GPU, seed hoặc image QA vào Story DB.

## 7. Nguồn nghiên cứu

- [Agentic Comic Drama Studio](https://github.com/siyuan-liu31/agentic-comic-drama-studio): location and identity locks, connected shot direction.
- [TT AutoManga](https://github.com/TTDiang2/TT_AutoManga): reusable prompt blocks.
- [Baoyu Comic](https://github.com/JimLiu/baoyu-skills/tree/main/skills/baoyu-comic): review gates and targeted revision.
- [Visual Narrative Grammar](https://doi.org/10.1111/cogs.12016): narrative roles and pacing.
- [Anima model card](https://huggingface.co/circlestone-labs/Anima): native text format.
- [Story2Board](https://daviddinkevich.github.io/Story2Board/) and [StoryDiffusion](https://storydiffusion.github.io/): image-level consistency is a different problem, not an implementation dependency.
