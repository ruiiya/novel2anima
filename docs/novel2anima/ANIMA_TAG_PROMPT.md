# Novel2Anima — Hợp đồng Prompt Anima (tag block + câu bổ trợ)

> **Định dạng canonical duy nhất:** Mỗi Shot → **một tag block** (dòng 1, lowercase, cách nhau `, `) + **tối đa 2 câu natural-language** (dòng 2, chỉ để đặt vị trí/quan hệ/ánh sáng mà tag không nói được). Model nhận nguyên văn bản này ở **positive prompt**. Không tạo JSON, bbox, item array, field name, hay `Prompt:` đầu dòng.
>
> Hợp đồng **định dạng/kỹ thuật**, không quyết định nội dung được phép. Nội dung do `docs/novel2anima/CONTENT_POLICY.md` quyết định.

## Model đích

| Thành phần | File |
|---|---|
| diffusion model | `anima-base-v1.0.safetensors` (`models/diffusion_models/`) |
| text encoder | `qwen_3_06b_base.safetensors` (`models/text_encoders/`) |
| VAE | `qwen_image_vae.safetensors` (`models/vae/`) |

`Anima-Base-v1.0` là base thuần: không aesthetic finetune, không merge style LoRA, style mặc định trung tính. Vì vậy **quality tag có tác dụng thật** — prefix khuyến nghị chính thức là `masterpiece, best quality, score_7, safe, `. `Anima-Turbo-v1.1` chỉ dùng để iterate nhanh (CFG 1, 8–12 steps). `Anima-Aesthetic` không còn dùng trong project này.

## Nguồn đối chiếu chính thức

- https://huggingface.co/circlestone-labs/Anima (model card: tag order, safety vocabulary, tag syntax)
- https://civitai.com/articles/35368/the-ultimate-anima-prompting-guidebook-all-you-need (cấu trúc block, camera/lighting/background, weighting)
- https://comfy.org (template `image_anima_base_v1.json`: baseline settings + negative)

## Cấu trúc bắt buộc

```
[quality] , [safety] , [subject count] , [character] , [series] , [@artist] , [appearance] ,
[clothing] , [expression] , [pose/action] , [camera] , [environment] , [lighting]
<2 câu natural language: vị trí chủ thể trong khung, quan hệ actor→target, độ sâu, ánh sáng>
```

Thứ tự trên là thứ tự chính thức của model card: `[quality/meta/year/safety] [1girl…] [character] [series] [artist] [general tags]`. Trong cùng một nhóm, thứ tự tuỳ ý. Tag bắt buộc có mặt:

1. **Quality/meta** (tuỳ chọn, đặt trước safety) — `masterpiece, best quality, score_7`; với Base nên có, vì không có aesthetic tuning.
2. **Safety** — đúng một trong `safe`, `sensitive`, `nsfw`, `explicit`. Đặt ngay sau quality/meta trong positive prompt; **không** đưa `nsfw` vào negative.
3. **Subject count** — `1girl`, `1boy`, `2girls`, `1other`… cộng `solo` khi chỉ một người.
4. **Character + series** — `karin (blue archive)`, Blue Archive. Với biến thể trang phục có tag riêng, dùng tag biến thể (`karin (bunny) (blue archive)`) **và** tag trang phục (`bunny suit`). Không dựa vào mỗi tên.
5. **Artist** (tuỳ chọn) — `@artistname`; style của Base là trung tính nên artist tag là cách chỉnh style mạnh nhất.
6. **Appearance anchors** — tóc, mắt, dấu hiệu nhận diện (halo, mole…), tỷ lệ cơ thể. Đây là thứ giữ identity qua 75 shot; chép từ Visual Bible/catalog, không diễn giải lại.
7. **Camera** — một tag framing + một tag angle, lấy từ danh sách đóng bên dưới.
8. **Environment** — địa điểm + 1–2 vật thể nhận diện + thời điểm/thời tiết.
9. **Lighting** — 1–3 tag ánh sáng vật lý tương thích nhau.

## Quy tắc cú pháp

- **Lowercase** cho mọi tag: `blue hair`, `upper body`, `looking at viewer`. Proprietary noun trong câu natural language giữ hoa bình thường.
- **Dùng space, không underscore**: `blue hair`, không `blue_hair`. Ngoại lệ duy nhất là `score_*` (`score_1`…`score_9`) — đó là tag duy nhất có underscore, dùng ở quality prefix hoặc negative.
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
| quality (tuỳ chọn) | `masterpiece`, `best quality`, `good quality`, `normal quality`, `score_9`…`score_1` |
| meta (tuỳ chọn) | `highres`, `absurdres`, `anime screenshot`, `official art` |
| era (tuỳ chọn) | `year 2025`, `newest`, `recent`, `mid`, `early`, `old` |
| framing | `close-up`, `upper body`, `cowboy shot`, `full body`, `wide shot` |
| angle | `from above`, `from below`, `eye level`, `from side`, `three-quarter view` |
| lens/composition (tuỳ chọn) | `wide angle`, `telephoto`, `shallow depth of field`, `centered composition`, `asymmetrical composition`, `dynamic composition` |
| style (tuỳ chọn) | `anime coloring`, `clean lineart`, `flat colors`, `soft cel shading`, `official art` |
| negative (renderer, không nằm trong file prompt) | `worst quality, low quality, score_1, score_2, score_3, artist name, blurry, jpeg artifacts, chromatic aberration` |

Prefix khuyến nghị cho Base: `masterpiece, best quality, score_7, safe, ` — nhưng safety tag của dự án do `CONTENT_POLICY` quyết định (`sensitive`/`nsfw`/`explicit`), nên chỉ giữ `masterpiece, best quality, score_7` rồi tới safety tag thật. `highres`/`absurdres` là meta tag, dùng tự do. Cấm trong positive: `worst quality`, `low quality` (tự mâu thuẫn), `ultra detailed`, `8k`, `4k` (không có trong vocab train, chỉ làm nhiễu). `year 2025`/`newest`… là aesthetic control, đổi riêng khỏi artist/medium tag.

Chỉ một framing và một angle trong một prompt. `close-up` loại trừ `full body`; `from above` loại trừ `from below`.

## Ngân sách token (không phải gợi ý)

Anima tokenize hai lần (Qwen-3 0.6B + T5); ngưỡng quan sát thực tế: **≤ 280 từ / ~480 T5 token**. Vượt ~512 token bắt đầu mất chi tiết (chất liệu vải, phụ kiện, cử động tay); ~1000 token thì mặt/tay/chân vỡ. Prompt chuẩn của dự án ~40–70 tag + 2 câu ⇒ 120–200 từ. Validator chặn ở 280 từ.

## Ví dụ hợp lệ

```
masterpiece, best quality, score_7, sensitive, 1girl, solo, karin (blue archive), dark skin, black hair, very long hair, ponytail, yellow eyes, large breasts, rabbit tail, halo, bunny suit, black leotard, blue bow, wrist cuffs, fake animal ears, fishnet pantyhose, high heels, standing, arms crossed, from side, full body, looking away, backstage, green room, closed door, bright lighting, cel shading
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

| Tham số | Anima-Base v1.0 (chuẩn) | Anima-Turbo v1.1 (iterate) |
|---|---|---|
| steps | 30–50 | 8–12 |
| CFG | 4–5 | 1 |
| sampler / scheduler | `er_sde` / `simple` (mặc định), hoặc `euler_a`, `dpmpp_2m_sde_gpu`, `euler` | `euler`, hoặc sampler đã test với Turbo |
| resolution | 896×1152 portrait, 1024×1024 vuông; 1–1.5 MP; bội số 16 (dải chính thức 512–1536) | |
| negative | `worst quality, low quality, score_1, score_2, score_3, artist name, blurry, jpeg artifacts, chromatic aberration` | CFG 1 làm negative gần như vô hiệu — sửa positive trước |

Base có style mặc định trung tính: thiếu artist/quality tag thì ảnh ra "plain". Vì vậy quality prefix + `anime coloring, cel shading, clean lineart` là bắt buộc trên thực tế, và character LoRA (nếu có) weight 0.7–0.9. Muốn so sánh công bằng phải cố định seed, model, sampler, CFG, resolution, steps — đổi đúng một block mỗi lần.

Workflow API mẫu của dự án: `pipeline/workflows/anima_base_v10.json` (9 node, không LoRA, không quality tag trong file — prompt đã mang quality prefix). Seed, checkpoint, sampler, negative, ảnh ra thuộc renderer — không thuộc DB.

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
