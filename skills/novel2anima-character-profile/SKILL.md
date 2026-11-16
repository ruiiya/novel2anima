---
name: novel2anima-character-profile
description: "Quản lý định danh và trang phục của nhân vật Novel2Anima có thể tái sử dụng, kèm màu sắc và bằng chứng, không thay đổi trạng thái theo Story hoặc nhãn nội dung."
---
# Novel2Anima — Thư viện nhân vật và trang phục

> **Policy nội dung bắt buộc:** Đọc `docs/novel2anima/CONTENT_POLICY.md` trước khi xử lý. Mọi quyết định nội dung tuân theo scope và phiên bản tại đó; skill này không tự đặt chính sách khác.

## Vai trò

Quản lý profile nhân vật **độc lập với từng Story** và cung cấp **identity packet tag** ổn định cho ShotSpec và Anima Prompt. Đọc `docs/novel2anima/CONTENT_FIDELITY.md` và `docs/novel2anima/TOOL_FLEXIBILITY.md`.

## Truy xuất thông tin

1. Kiểm tra bằng chứng đang có: `character_profile` cục bộ, danh sách JSON, catalog SQLite, ghi chú tham chiếu đã xác minh hoặc nguồn kết nối khác. Trong V2, đọc database Novel2Anima đã khởi tạo làm nguồn chuẩn; không phụ thuộc tag engine hoặc Internet cụ thể. Có thể thay storage sau này theo DATABASE_CONTRACT.md.
2. Giữ `character_id`, tác phẩm/nguồn nếu biết, đặc điểm nhận diện đã xác nhận (tóc, mắt, hình dáng, phụ kiện), biến thể trang phục, màu từng món, nguồn dữ liệu do người dùng/tác giả cung cấp và mọi điểm chưa chắc chắn.
3. Phân biệt `canon identity` với `story/act outfit` và `shot physical state`. Một nhân vật có thể xuất hiện trong nhiều Story và dùng nhiều outfit, nhưng các đặc điểm canon không được thay đổi ngẫu nhiên.
4. Quy tắc ưu tiên trang phục: chỉ định tường minh ở Shot > ở Act > outfit profile đã chọn > mặc định dự án. Nếu màu bị thiếu hay mâu thuẫn, báo `UNRESOLVED`/`CONFLICT`, không chọn đại.
5. Các concept kiểu Danbooru chỉ được dùng để hỗ trợ tra cứu nếu phù hợp. Novel2Anima **không** bắt buộc có kho tag lớn, không được bịa ID và không xuất prompt cuối chỉ gồm tag.
6. Giữ nguyên nhãn phân loại nguồn trong metadata; không lấy nhãn catalog để suy ra tuổi hoặc quyết định của policy.
7. Xuất *visual anchor* ngắn gọn cho caption ngôn ngữ tự nhiên, có tham chiếu tới bằng chứng gốc. Thuộc tính canon chưa rõ phải giữ là chưa rõ.

## Định danh trong prompt (bắt buộc)

- Với nhân vật lấy từ một tác phẩm/parody cụ thể, prompt phải ghi **tên + tác phẩm trong ngoặc**, ví dụ `Asuna (Blue Archive)`, `Rias Gremory (High School DxD)`. Chỉ viết tên trần (`Asuna`, `Rias`) là **không đủ**: tên trùng giữa nhiều nguồn nên không xác định được nhân vật, và catalog có nhiều biến thể cùng tên.
- Nếu là biến thể trong cùng tác phẩm, ghi cả biến thể: `Asuna (bunny) (Blue Archive)`, `Asuna (school uniform) (Blue Archive)`; trang phục của Story vẫn mô tả riêng, không thay bằng tên biến thể.
- Chỉ nhân vật **original/không thuộc tác phẩm nào** mới được bỏ phần ngoặc; khi đó dùng mô tả nhận diện đầy đủ và `character_id` curated làm bằng chứng.
- Dạng chuẩn lấy từ `characters.display_name` (đã có hậu tố tác phẩm) hoặc `universes.slug`; không tự bịa tên tác phẩm, không dịch tên tác phẩm.
- Kiểm QA: mỗi nhân vật có nguồn tác phẩm trong natural prompt phải chứa định danh đầy đủ; thiếu thì `NEEDS_REVIEW` với issue `IDENTITY_NOT_DISAMBIGUATED`.

## Visual Lock (V4)

Chuyển identity anchors và trang phục đã duyệt thành `visual_bible.characters` theo role, gắn provenance, character_id/outfit_id hiện hành. Khóa khuôn mặt, màu/kiểu tóc, mắt, dấu hiệu nhận diện, tỷ lệ cơ thể đã biết; biến thể trang phục/biểu cảm/tư thế theo Shot. Nếu chưa rõ thuộc tính, ghi unknown, không tự gán tuổi hay chi tiết canon. Mỗi role giữ một **identity packet tag** (lowercase, space không underscore, đúng Danbooru/Anima) và dùng **nguyên văn** packet đó trong mọi prompt nơi nhân vật nhìn thấy; consistency đến từ character LoRA khi có, không đến từ việc lặp câu. Đọc `docs/novel2anima/VISUAL_STORYTELLING.md` và `docs/novel2anima/ANIMA_TAG_PROMPT.md`.

## Xử lý xung đột

Nếu nguồn profile mâu thuẫn chi tiết Shot đã xác nhận, tạo `PROFILE_CONFLICT`; không tự sửa nguồn hay diễn giải lại trang phục. Việc thay đồ có chủ đích phải lưu như một sự kiện.

## Kết quả

Profile chuẩn và revision, outfit đã chọn theo Shot, cùng `unresolved[]`. Có thể thay đổi nơi lưu và công cụ truy xuất miễn giữ nguyên hợp đồng.

## Character Catalog trong Database

- Tra cứu `characters` (đúng `universe_id`), `character_aliases`, `character_traits` (confidence/is_locked), `outfits`, `outfit_parts`, `source_records` và `source_record_versions` trước khi tạo profile. Dùng `search-characters` để tìm ứng viên, không coi fuzzy match là danh tính đúng.
- Catalog tách khỏi Story. Outfit mặc định/canon được xác minh theo `outfits.verification` và `source_record_id`, không suy từ `character_tags`/`catalog_tags`; dùng `novel2anima-catalog-ingest` để import metadata có provenance.
- Tra `story_castings` theo role/revision để biết profile đang áp dụng; shot outfit override theo `shot_participants.outfit_override_id` chỉ có hiệu lực tại Shot. Không cập nhật canon khi người dùng thay outfit trong Story.
- Khi lưu profile/traits/outfit mới, dùng transaction, unique key, provenance và trạng thái `UNVERIFIED/REVIEWED/VERIFIED`; giữ thuộc tính đã khóa và báo `PROFILE_CONFLICT` nếu mâu thuẫn.
