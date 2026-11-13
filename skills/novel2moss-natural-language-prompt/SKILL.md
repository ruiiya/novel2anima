---
name: novel2moss-natural-language-prompt
description: "Chuyển layout.prompt.json đã export của Novel2Moss thành một prompt ngôn ngữ tự nhiên cho backend chỉ nhận text; giữ nguyên sự kiện, vai trò và trang phục, không sửa layout canonical."
---
# Novel2Moss — Chuyển Layout sang prompt ngôn ngữ tự nhiên

> **Policy nội dung bắt buộc:** Đọc `docs/novel2moss/CONTENT_POLICY.md` trước khi xử lý. Mọi quyết định nội dung tuân theo scope và phiên bản tại đó; skill này không tự đặt chính sách khác.

## Vai trò

Đây là **projection dẫn xuất**, không phải định dạng canonical. `layout.prompt.json` vẫn là source of truth; file NL chỉ là bản đọc được cho renderer text-only (API không nhận bbox) hoặc để người kiểm tra đọc nhanh. Không thay `render.prompt.json`, không đổi schema DB, không đổi nội dung truyện.

Chỉ chạy trên bundle đã export và đã có QA trước export. Nếu `fidelity_report.json` là `BLOCKED`, không chuyển.

## Vị trí pipeline

```text
ShotSpec → Layout draft → layout.prompt.json (canonical)
         → QA → export-bundle
         → Natural Language Converter (skill này) → natural.prompt.txt
         → renderer chỉ nhận text
```

## Đầu vào

- `layout.prompt.json`: `summary.caption`, `summary.meta`, `items[]` (`label`, `caption`, `bbox`, `text`).
- Tùy chọn: `prompt.manifest.json` (hash/kích thước), `fidelity_report.json`, `shot_spec.json` để đối chiếu actor/target.
- Không đọc SQLite, không yêu cầu DB/CLI còn sống.

## Đầu ra

```text
natural.prompt.txt        # một đoạn prose, tiếng Anh
natural.prompt.json       # sidecar: status, hash nguồn/đích, danh sách nhân vật, text item, lỗi
```

Ngoài bundle, xuất bản gộp để paste/render hàng loạt: `prompts.all.nl.txt` (toàn bộ Shot hiện hành) và `prompts_nl/<act_id>.txt` (mỗi Act một file), **mỗi prompt cách nhau đúng một dòng trống**, không header/metadata, kết thúc bằng một `\n`.

Không ghi đè `layout.prompt.json` hay lịch sử export. Cùng input phải cho cùng output (byte-identical).

## Quy trình

1. Kiểm tra bundle: `layout.prompt.json` đúng schema, có `summary.caption` và `items` không rỗng.
2. Chạy flattener tất định:

```bash
python tools/novel2moss/flatten_layout.py \
  exports/<story_id>/<shot_key>/<rev>/layout.prompt.json \
  --output exports/<story_id>/<shot_key>/<rev>/natural.prompt.txt \
  --sidecar exports/<story_id>/<shot_key>/<rev>/natural.prompt.json
```

3. Nếu cần câu mượt hơn, chỉ được sửa **ngữ pháp**: nối câu, bỏ đại từ mơ hồ, thay bằng tên. Cấm đổi danh từ, động từ, màu, trạng thái, số người, chiều actor→target.
4. Đọc lại output, đối chiếu danh sách nhân vật và `text` item; nếu sai, sửa layout rồi export revision mới — không vá tay output.

## Luật lọc bắt buộc

Flattener và người viết phải bỏ khỏi prose:

1. Negative prompt: `no panels`, `no split screen`, `no comic grid`, `no extra limbs`, `no duplicate characters`, `no spectators`, `no crew`, `no text`, `no watermark`, `no underexposure`, `no low-key falloff`, `not a grid or collage`.
2. Chỉ dẫn layout: `overlap shoulders`, `stagger head heights`, `heads and torsos fill their boxes`.
3. Nhãn phân loại đứng riêng: `explicit`, `nsfw`, `adult`, `consensual`, `bdsm`, `yuri`, `straight`, câu `all participants are adults`.
4. Token nội bộ: `SET_A/B/C`, `SET_C_TORN`, `role_key`, `character:...`, ID, revision, width/height.
5. Trùng lặp: summary lặp lại item, cụm lặp trong cùng caption, object item trùng setting.
6. Outfit rút gọn: `X is school uniform` → dùng mô tả trang phục đầy đủ trong item; không xuất `uniform` trơ.
7. Camera: gộp `Camera:`/`Framing:`/focus rải rác thành **một** câu `Camera: <lens>, <angle>, <framing>.` đặt ngay trước câu nhân vật; xoá mọi bản sao ở giữa prompt. Chuẩn hoá cụm yếu thành literal: `top-down view from above` → `directly overhead, looking straight down`, `low-angle view from below` → `low angle, looking up`. Framing trùng thì giữ mức cụ thể nhất (detail > close-up > face/shoulders > upper body > full body).

Giữ nguyên: danh tính, tuổi đã xác nhận, trang phục/màu, biểu cảm, pose, vị trí tương đối, chiều hành động, chữ cần hiển thị (verbatim). Với nhân vật thuộc tác phẩm cụ thể, giữ nguyên định danh kèm tác phẩm, ví dụ `Asuna (Blue Archive)`; không rút gọn thành tên trần vì sẽ mất khả năng xác định nhân vật.

## Cổng kiểm

- `PASS`: có prose, đủ mọi `character` item, mọi `text` item verbatim, không còn bbox/số tọa độ, không còn negative/nhãn.
- `NEEDS_REVIEW`: không có `character` và không có `text` item; hoặc thiếu dữ kiện để diễn đạt trung thực.
- `BLOCKED`: không tạo được prose, layout sai schema, hoặc mất `text` bắt buộc.

`issues`: `NO_CHARACTER_ITEM`, `TEXT_ITEM_LOST`, `TEXT_VERBATIM_LOST`, `BBOX_IN_PROSE`.

Kiểm nhanh: `python -m unittest tests.test_flatten_layout -v`.

## Không làm

- Không tạo bbox, không đổi bố cục, không thêm nhân vật/vật/mood/ánh sáng.
- Không chuyển sang tag-only, không ghép `render.prompt.json` elements vào prose.
- Không ghi DB, không lưu lịch sử render, không tuyên bố đã render.
- Không coi prompt NL là tương đương Layout: mất kiểm soát vị trí bbox; ghi rõ khi bàn giao.

## Bàn giao

`natural.prompt.txt`, `natural.prompt.json` (status, `source_layout_sha256`, `natural_prompt_sha256`, `characters`, `text_items`, `issues`), và ghi chú `SPATIAL_CONTROL_DEGRADED` khi backend không nhận bbox.
