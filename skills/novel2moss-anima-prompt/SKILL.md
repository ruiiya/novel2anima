---
name: novel2moss-anima-prompt
description: "Skill canonical: biên soạn positive prompt Anima (tag block + tối đa 2 câu bổ trợ) trực tiếp từ ShotSpec, character catalog, casting và continuity; không đi qua JSON Layout/bbox."
---
# Novel2Moss — Anima Prompt (canonical)

> **Policy:** Luôn đọc `docs/novel2moss/CONTENT_POLICY.md`. Quy tắc nội dung do policy trung tâm quyết định; skill này chỉ điều phối tính chính xác và định dạng.
>
> **Hợp đồng định dạng:** `docs/novel2moss/ANIMA_TAG_PROMPT.md`. Model đích: `Anima-Aesthetic-v1.1` (Qwen-3 0.6B text encoder, Qwen-Image VAE).

## Khi sử dụng

Sau khi Story/ShotSpec và Continuity đã có phiên bản rõ ràng, trước QA và export prompt. Áp dụng cho cả Blind và Non-Blind. Đây là **prompt engine duy nhất** của Novel2Moss.

## Đầu vào

- ShotSpec/revision đã lưu (`shots`, `shot_participants`, `shot_interactions`), Story Event, vai trò actor/target.
- Profile nhân vật, outfit và casting **đang có hiệu lực tại revision**; nếu Blind chưa cast thì dùng mô tả vai trò có căn cứ, không tự bịa danh tính.
- `continuity_snapshots` của Shot; `catalog_tags`/`character_tags`/`outfit_tags` đã review — đây là **nguồn tag chính**, không tự đặt tag mới.
- Style, camera, scene, visible-text và các ràng buộc đã chốt.
- V4: storyboard slot, purpose, context hash, Visual Bible, state đúng predecessor. Đọc `docs/novel2moss/VISUAL_STORYTELLING.md`.

## Dựng prompt theo 7 block

Dòng 1 — tag block, đúng thứ tự chính thức của Anima:

1. **Safety:** `safe` / `sensitive` / `nsfw` / `explicit`. Album adult dùng `nsfw`/`explicit`; không bao giờ đưa tag này vào negative.
2. **Subject count:** `1girl`, `solo` (hoặc `2girls`, `multiple boys`…).
3. **Character + series:** tag nhân vật kèm biến thể trang phục nếu có (`karin (bunny) (blue archive)`), rồi series. Không dựa vào mỗi tên.
4. **Appearance anchors:** tóc (màu + kiểu + độ dài), mắt, dấu nhận diện (halo, mole, tai thú), tỷ lệ cơ thể. Chép từ profile/catalog, giữ **nguyên văn** qua mọi Shot.
5. **Clothing + expression:** trang phục đang mặc ở Shot này (kể cả trạng thái đã cởi/đang cởi), biểu cảm canonical.
6. **Pose/action:** tư thế + cử chỉ, tag Danbooru khi có (`arms crossed`, `kneeling`, `looking at viewer`).
7. **Camera:** một framing + một angle từ danh sách đóng — `close-up` / `upper body` / `cowboy shot` / `full body` / `wide shot`, × `from above` / `from below` / `eye level` / `from side` / `three-quarter view`.
8. **Environment + lighting:** địa điểm, 1–2 vật thể nhận diện, thời điểm; 1–3 tag ánh sáng vật lý tương thích.

Dòng 2 (tuỳ chọn, **tối đa 2 câu**) — chỉ chứa thứ tag không nói được: chủ thể nằm ở đâu trong khung, quan hệ actor→target, độ sâu, hướng sáng. Không kể chuyện, không lời thoại, không lệnh “create/generate”.

## Quy tắc bắt buộc

- Lowercase cho tag; **space không underscore** (`blue hair`, không `blue_hair`). Prompt đúng không có underscore nào.
- Space sau dấu phẩy: `1girl, solo, dark skin`.
- **Không quality tag, không `score_*`** (Aesthetic đã bỏ nhãn chất lượng khi train) — cả positive lẫn negative.
- Không tag tự mâu thuẫn: hai framing, hai angle cùng trục, `short hair` + `very long hair`, `solo` + `2girls`.
- Không tag mọi thứ nhìn thấy; ưu tiên đúng thứ tự trên, bỏ tag không chắc tác dụng.
- Ngân sách: **≤ 280 từ** (~480 T5 token). Vượt ~512 token bắt đầu mất chi tiết vải/phụ kiện/cử động tay.
- Weight `(tag:1.5)` chỉ khi tag cần thiết lặp lại bị mất, thang 1.5 → 1.8 → 2.0. Mặc định không weight.
- Artist tag nếu có phải prefix `@`; không bịa tên artist từ style label.
- Mỗi Shot tự đủ ngữ cảnh: không “same woman as previous image”, không “continue the last scene”.
- Không chèn sidecar, field name, `Prompt:`, JSON, bbox hay tọa độ pixel.

## Các bước

1. **Đối chiếu nguồn:** tải đúng revision, ghi source_refs, không tự gán thông tin thiếu thành canon.
2. **Visual checklist nội bộ:** số người, identity anchors, outfit, actor/target, tay/cử chỉ, phản ứng, framing, background, light, chữ thật sự nhìn thấy. Checklist chỉ để QA, không vào prompt.
3. **Tra tag:** lấy tag appearance/clothing/pose từ catalog và Visual Bible; chỉ tạo tag mới khi catalog thiếu, và ghi lý do.
4. **Viết tag block** theo 7 block; **rồi** viết tối đa 2 câu bổ trợ cho vị trí/quan hệ nếu Shot cần.
5. **Validate:** `tools/novel2moss/validate_anima_prompt.py` phải PASS (kiểm tra cú pháp, safety tag, framing, mâu thuẫn camera, ngân sách từ).
6. **QA:** gọi `novel2moss-fidelity-qa`; chỉ ghi `PASS` khi thực sự đã đối chiếu ShotSpec.
7. **Lưu:** `n2m_workflow.py save-natural-prompt --shot-id SHOT_ID --file drafts/S01.txt`, rồi `save-qa --kind PROMPT`.
8. **Bàn giao:** `n2m_db.py export-bundle` hoặc `export-story-prompts` sau khi seal storyboard; sửa cục bộ thì tạo revision mới và QA lại.

## Blind và Non-Blind

- **Blind:** role `LEAD`/`PARTNER_A` ổn định; chưa có ngoại hình cụ thể thì chỉ tag phần đã biết, dùng identity packet trung tính thay cho tên franchise.
- **Non-Blind:** kiểm tra character/universe/identity tags/outfit **đã xác minh**; nếu nhân vật có nhiều biến thể, dùng đúng tag biến thể đang cast.
- Đổi casting/outfit ⇒ prompt revision mới + QA lại, không tái dùng mô tả cũ làm canon.

## Lệnh mẫu

```powershell
python tools/novel2moss/validate_anima_prompt.py drafts/S01.txt
python database/src/n2m_workflow.py save-natural-prompt --shot-id SHOT_ID --file drafts/S01.txt
python database/src/n2m_workflow.py save-qa --kind PROMPT --subject-id PROMPT_ID --verdict PASS --file reports/S01.qa.json
python database/src/n2m_db.py export-bundle --prompt-id PROMPT_ID --out-dir exports/STORY_ID/S01/1
```

## Điều không được làm

- Không convert prompt MOSS natural-language cũ thành tag block bằng máy rồi coi là source of truth — phải viết lại từ ShotSpec.
- Không dùng JSON Layout/bbox (Anima không có layout conditioning).
- Không stack style LoRA: `anima-aesthetic-v1.1` đã merge style LoRA; chỉ character LoRA khi có, weight 0.7–0.9.
- Không đưa render job/ảnh/model state vào Novel2Moss DB.

**Đầu ra:** Một file `.txt` Anima prompt cho mỗi Shot; JSON manifest/QA là sidecar **không gửi cho model**.
