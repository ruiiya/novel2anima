---
name: novel2anima-catalog-ingest
description: "Nhập dữ liệu catalog nhân vật, universe, alias, tag, trang phục, pose, action vào SQLite với provenance, license và idempotency."
---
# Novel2Anima — Catalog Ingestion

> Đọc `docs/novel2anima/DATABASE_CONTRACT.md`, `DATABASE_SOURCES.md`, `CONTENT_FIDELITY.md` và `docs/novel2anima/CONTENT_POLICY.md`.

## Phạm vi

Phục vụ dữ liệu tái sử dụng độc lập Story: nhân vật, trang phục có text/tags, từ vựng pose/action/expression/camera/spatial và metadata nguồn. Skill này **không** tạo truyện, không suy diễn canon không có chứng cứ, không thu thập ảnh/portrait/skeleton/render state và không render.

## Quy trình

1. Xác định **consumer** trước khi import: skill nào đọc, bảng/cột nào, bước Story/Shot/Natural Prompt nào bị ảnh hưởng. Manifest phải có `consumer_skill`, `target_fields`, `used_in_step`; nếu thiếu thì không import.
2. Chỉ chọn nguồn có dữ liệu thực sự thay đổi quyết định Story/Shot/Natural Prompt. V2 giữ DeepGHS, Danbooru tag **lọc theo core tags**, và outfit generic có text/tags; loại e621, portrait, COCO, OpenPose, Grounded SAM, skeleton và render state.
3. Đăng ký nguồn trong `source_registry` (URL, loại, license/terms tại thời điểm kiểm tra). Tạo `import_runs`, lưu payload gốc, `external_key`, SHA256 và `source_record_versions`; ghi số đã nhập/đã có/lỗi.
4. Bản ghi trùng khóa `(source_id, external_key)` phải upsert có kiểm soát và lưu bản nguồn mới nếu hash thay đổi. Không tự merge hai nhân vật khác nhau do gần giống tên; alias phải có nguồn.
5. Phân biệt **character identity** và **outfit**. DeepGHS/Danbooru chủ yếu là tag ứng viên, không chứng minh origin outfit, màu trang phục hoặc tuổi. Chỉ gắn `VERIFIED` theo chứng cứ rõ. Outfit generic phải `GENERIC/UNVERIFIED`, `character_id=NULL`.
6. Với pose gallery, chỉ import khi có caption tiếng Anh đã review và consumer test; nếu chưa, để `enabled:false` trong manifest và báo `SKIP`.
7. Thử chạy import lần thứ hai và so sánh số bản ghi/key/hash; lưu lịch sử thay đổi nhưng không tạo bản ghi trùng.
8. Tạo báo cáo provenance, số liệu theo từng bảng và các trường chưa xác minh. Không coi nguồn bên ngoài tự động là dữ liệu canonical đã duyệt.

## Công cụ được triển khai

```powershell
python database/src/n2m_db.py seed
python database/src/collect_sources.py fetch --source deepghs
python database/src/collect_sources.py fetch --source ai_pose_gallery
python database/src/collect_sources.py fetch --source dbr_e621_lists
python database/src/collect_sources.py fetch --source storyaura_danbooru_csv
python database/src/collect_sources.py verify
python database/src/n2m_db.py import-deepghs-md database/imports/deepghs/blue_archive.md
python database/src/n2m_db.py import-tags-csv database/imports/dbr-e621-lists-archive/danbooru/danbooru_2026-10-01_pt20-ia-dd.csv --namespace danbooru --from-character-core-tags
python database/src/n2m_db.py import-storyaura-characters database/imports/storyaura-danbooru-csv/danbooru_character_tags_corrected.csv --source-revision 2026-10-29-corrected
python database/src/n2m_db.py import-storyaura-appearance database/imports/storyaura-danbooru-csv/danbooru_character_appearance_corrected.csv --source-revision 2026-10-29-corrected
python database/src/n2m_db.py import-costume-gallery-json database/imports/ai-pose-gallery/data/costume-zh.json --source-id ai_pose_gallery
python database/src/n2m_db.py import-costume-gallery-json database/imports/ai-pose-gallery/data/costume-anime-zh.json --source-id charadb
python database/src/n2m_db.py import-tag-relations-json data/aliases.json --namespace danbooru --kind alias
python database/src/n2m_db.py search-catalog character asuna
python database/src/n2m_db.py search-catalog action head_pat
python database/src/n2m_db.py search-catalog outfit sailor
python database/src/n2m_db.py stats --detailed
python database/src/catalog_report.py
```

Collector chỉ tải metadata đã khai báo trong `database/collect/source_manifest.json`, từ chối ảnh và ghi SHA256/checkpoint. Các importer đọc file có sẵn; không tự crawl. Thay Python bằng ETL khác được phép nếu vẫn bảo toàn provenance, version, license và định danh.

## Bàn giao

Số bản ghi được nhập/cập nhật/bỏ qua với `import_run_id`, nguồn chính xác, hạn chế giấy phép, `UNVERIFIED`/`REVIEWED`/`VERIFIED`, các kết quả kiểm thử idempotency, **consumer query/test**, và danh sách vấn đề cần curate thủ công. Không báo thành công chỉ vì số record tăng.
