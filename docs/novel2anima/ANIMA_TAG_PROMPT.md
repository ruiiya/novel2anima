# Novel2Anima — Hợp đồng Prompt Anima (tag block + câu bổ trợ)

> **Định dạng canonical duy nhất:** Mỗi Shot → **một tag block** (dòng 1, lowercase, cách nhau `, `) + **tối đa 2 câu natural-language** (dòng 2, chỉ để đặt vị trí/quan hệ/ánh sáng mà tag không nói được). Model nhận nguyên văn bản này ở **positive prompt**. Không tạo JSON, bbox, item array, field name, hay `Prompt:` đầu dòng.
>
> Hợp đồng **định dạng/kỹ thuật**, không quyết định nội dung được phép. Nội dung do `docs/novel2anima/CONTENT_POLICY.md` quyết định.

## Model đích

| Thành phần | File |
|---|---|
| diffusion model | `anima-aesthetic-v1.1.safetensors` (`models/diffusion_models/`) |
| text encoder | `qwen_3_06b_base.safetensors` (`models/text_encoders/`) |
| VAE | `qwen_image_vae.safetensors` (`models/vae/`) |

`Anima-Aesthetic-v1.1` là finetune aesthetic của base v1.0 **đã merge style LoRA**, caption huấn luyện đã bỏ nhãn chất lượng. Vì vậy: **không** quality tag, **không** `score_*` (cả positive lẫn negative), **không** stack thêm style LoRA.

## Nguồn đối chiếu chính thức

- https://huggingface.co/circlestone-labs/Anima (model card: tag order, safety vocabulary, tag syntax)
- https://civitai.com/articles/35368/the-ultimate-anima-prompting-guidebook-all-you-need (cấu trúc block, camera/lighting/background, weighting)
- https://comfy.org (template `image_anima_base_v1.json`: baseline settings + negative)

## Cấu trúc bắt buộc

```
[safety] , [subject count] , [character] , [series] , [@artist] , [appearance] ,
[clothing] , [expression] , [pose/action] , [camera] , [environment] , [lighting]
<2 câu natural language: vị trí chủ thể trong khung, quan hệ actor→target, độ sâu, ánh sáng>
```

Thứ tự trên là thứ tự chính thức của model card. Tag bắt buộc có mặt:

1. **Safety** — đúng một trong `safe`, `sensitive`, `nsfw`, `explicit`. Đặt ở đầu positive prompt; **không** đưa `nsfw` vào negative.
2. **Subject count** — `1girl`, `1boy`, `2girls`, `1other`… cộng `solo` khi chỉ một người.
3. **Character + series** — `karin (blue archive)`, Blue Archive. Với biến thể trang phục có tag riêng, dùng tag biến thể (`karin (bunny) (blue archive)`) **và** tag trang phục (`bunny suit`). Không dựa vào mỗi tên.
4. **Appearance anchors** — tóc, mắt, dấu hiệu nhận diện (halo, mole…), tỷ lệ cơ thể. Đây là thứ giữ identity qua 75 shot; chép từ Visual Bible/catalog, không diễn giải lại.
5. **Camera** — một tag framing + một tag angle, lấy từ danh sách đóng bên dưới.
6. **Environment** — địa điểm + 1–2 vật thể nhận diện + thời điểm/thời tiết.
7. **Lighting** — 1–3 tag ánh sáng vật lý tương thích nhau.

## Quy tắc cú pháp

- **Lowercase** cho mọi tag: `blue hair`, `upper body`, `looking at viewer`. Proprietary noun trong câu natural language giữ hoa bình thường.
- **Dùng space, không underscore**: `blue hair`, không `blue_hair`. Ngoại lệ duy nhất là `score_*` — nhưng Aesthetic không dùng `score_*` nên prompt đúng **không có underscore nào**.
- **Có space sau dấu phẩy**: `1girl, solo, dark skin`. Không `1girl,solo,dark skin`.
- Canonical spelling/punctuation giữ nguyên khi tag vốn có ký tự đặc biệt (`>_<`, `:3`); không normalize chúng.
- Danh từ riêng/tag nhân vật: giữ đúng dạng tag gốc, kể cả ngoặc — `karin (bunny) (blue archive)`.
- Artist tag **bắt buộc prefix `@`** (`@artistname`). Bỏ trống cũng hợp lệ; không bịa tên artist.
- **Không tag mọi thứ nhìn thấy.** Model train với tag dropout; ưu tiên theo thứ tự: subject count → identity/series → appearance định danh → action/pose → camera → environment → lighting.
- **Không tag tự mâu thuẫn**: `short hair` + `very long hair`, `solo` + `2girls`, `closed mouth` + `shouting`, `close-up` + `full body`. Anima cố thỏa cả hai và tạo lỗi giải phẫu/bố cục thay vì bỏ qua một cái.
- Weight `(tag:1.5)` chỉ dùng khi concept lặp lại bị mất, và thang 1.5 → 1.8 → 2.0; không dùng weight để vá prompt vô lý. Mặc định **không** weight.

## Danh sách đóng

| Nhóm | Giá trị hợp lệ |
|---|---|
| safety | `safe`, `sensitive`, `nsfw`, `explicit` |
| meta (tuỳ chọn) | `highres`, `absurdres`, `anime screenshot`, `official art` |
| era (tuỳ chọn) | `year 2025`, `newest`, `recent`, `mid`, `early`, `old` |
| framing | `close-up`, `upper body`, `cowboy shot`, `full body`, `wide shot` |
| angle | `from above`, `from below`, `eye level`, `from side`, `three-quarter view` |
| lens/composition (tuỳ chọn) | `wide angle`, `telephoto`, `shallow depth of field`, `centered composition`, `asymmetrical composition`, `dynamic composition` |
| style (tuỳ chọn) | `anime coloring`, `clean lineart`, `flat colors`, `soft cel shading`, `official art` |
| negative (renderer, không nằm trong file prompt) | `worst quality, low quality, artist name, blurry, jpeg artifacts, chromatic aberration` |

`highres`/`absurdres` là **meta tag**, không phải quality tag — baseline Aesthetic chính thức là `safe, highres`. Cấm trong positive chỉ gồm `masterpiece`, `best quality`, `worst quality`, `ultra detailed`, `8k`, `4k` và mọi `score_*`. `year 2025`/`newest`… là aesthetic control, đổi riêng khỏi artist/medium tag.

Chỉ một framing và một angle trong một prompt. `close-up` loại trừ `full body`; `from above` loại trừ `from below`.

## Ngân sách token (không phải gợi ý)

Anima tokenize hai lần (Qwen-3 0.6B + T5); ngưỡng quan sát thực tế: **≤ 280 từ / ~480 T5 token**. Vượt ~512 token bắt đầu mất chi tiết (chất liệu vải, phụ kiện, cử động tay); ~1000 token thì mặt/tay/chân vỡ. Prompt chuẩn của dự án ~40–70 tag + 2 câu ⇒ 120–200 từ. Validator chặn ở 280 từ.

## Ví dụ hợp lệ

```
sensitive, 1girl, solo, karin (blue archive), dark skin, black hair, very long hair, ponytail, yellow eyes, large breasts, rabbit tail, halo, bunny suit, black leotard, blue bow, wrist cuffs, fake animal ears, fishnet pantyhose, high heels, standing, arms crossed, from side, full body, looking away, backstage, green room, closed door, bright lighting, cel shading
Karin stands sideways in the left third of the frame with her arms folded under her chest. The empty green room recedes behind her, and flat daylight from the ceiling keeps every surface evenly lit.
```

- Dòng 1 là tag block; dòng 2 tối đa **2 câu** (nhóm cảnh 2 người trở lên: tối đa **4 câu**, mỗi chủ thể một câu có vị trí), chỉ chứa thông tin tag không diễn đạt được (vị trí trong khung, quan hệ, độ sâu). Prompt thuần natural language (không dùng ở đây) cần **tối thiểu 2 câu** theo model card; câu quá ngắn dễ sinh nội dung ngoài ý.
- Câu natural language **không** được thêm/bớt người, đổi trang phục, đổi actor→target hay đổi mức nội dung.

## Lưu trữ và xuất file

- DB: `shot_prompts` (`shot_id`, `revision`, `language`, `prompt_text`, hash, SHA của ShotSpec). Append-only.
- Tạo: `n2m_workflow.py save-natural-prompt --shot-id ... --file ...` (tên lệnh và bảng giữ nguyên để không phá bundle cũ; nội dung là prompt Anima).
- Kiểm tra: `tools/novel2anima/validate_anima_prompt.py` chỉ xác nhận **định dạng** (tag line, lowercase, safety tag, framing tag, mâu thuẫn camera, ngân sách từ, hash). Không chứng minh fidelity — phải QA đối chiếu ShotSpec.
- QA: `n2m_workflow.py save-qa --kind PROMPT --subject-id PROMPT_ID`.
- Export: `n2m_db.py export-bundle` tạo `natural.prompt.txt` (tên file giữ nguyên), `prompt.manifest.json` với `format: anima-tag-v1`, `fidelity_report.json`.
- Xuất cả Story: `n2m_db.py export-story-prompts` tạo bundle, `prompts.all.jsonl`, `prompts/A01.jsonl`. Trường `prompt` là **Anima prompt string**, không phải JSON/JSONL gửi model.

## Renderer (ngoài DB)

| Tham số | Anima-Aesthetic v1.1 | Anima-Base v1.0 | Anima-Turbo v1.1 |
|---|---|---|---|
| steps | 30–40 | 35–50 | 8–12 |
| CFG | 3.5–4.5 | 4.5–5 | 1 |
| sampler / scheduler | `er_sde` / `simple` | `er_sde` / `simple` | `euler`, hoặc sampler đã test với Turbo |
| resolution | 896×1152 portrait, 1024×1024 vuông; 1–1.5 MP; bội số 16 (dải chính thức 512–1536) | | |
| negative | `worst quality, low quality, artist name, blurry, jpeg artifacts, chromatic aberration` | thêm `score_1, score_2, score_3` | CFG 1 làm negative gần như vô hiệu — sửa positive trước |

Với Aesthetic: `masterpiece, best quality` không bắt buộc và có thể làm phẳng style; `score_*` bị cấm cả positive lẫn negative. Muốn so sánh công bằng phải cố định seed, model, sampler, CFG, resolution, steps — đổi đúng một block mỗi lần.

Workflow API mẫu của dự án: `exports/cnc_bunny/workflow/anima_bunny_all.json` (9 node, không LoRA, không quality tag). Seed, checkpoint, sampler, negative, ảnh ra thuộc renderer — không thuộc DB.

## QA trước export

- So khớp số nhân vật (tag count), identity anchors, outfit, màu, framing/angle, sự kiện đang thể hiện, chiều actor→target.
- So khớp continuity: anchor nào giữ nguyên, delta nào có chủ đích.
- Chữ cần hiển thị: Anima render chữ kém; đặt trong ngoặc kép ở câu natural language, và chấp nhận phải lettering hậu kỳ nếu là chữ dài.
- `PASS` định dạng **không** đồng nghĩa QA ngữ nghĩa `PASS` hay ảnh render đúng.
- Không tuyên bố cấu hình inference “tốt nhất” khi chưa benchmark trên workflow thực tế.

## Migration từ MOSS natural-language

- Prompt MOSS cũ (văn xuôi liền mạch, mô tả outfit bằng câu, camera bằng “shot at 85mm…”) **không** tự convert: viết lại từ ShotSpec + profile + continuity, QA lại, rồi lưu revision mới.
- `shot_layouts`, `layout_exports`, `qa_reports` lịch sử vẫn chỉ đọc.
- Không dùng `summary`, `items`, `bbox`, `bbox_format`, `compile_layout.py` — MOSS layout không có tương đương trong Anima; bố cục do tag + câu vị trí quyết định.
