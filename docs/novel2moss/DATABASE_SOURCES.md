# Novel2Moss — Nguồn dữ liệu và yêu cầu nhập Catalog V2

Nguồn được khai báo trong `source_registry` và manifest `database/collect/source_manifest.json`. Mỗi nguồn **enabled** phải có `consumer_skill`, `target_fields`, `used_in_step`. Collector/import là metadata-first; **kiểm tra lại license/terms** trước khi dùng dữ liệu ngoài. Không tải/đóng gói ảnh, portrait hoặc skeleton.

## Quyết định phạm vi

| Nguồn / dữ liệu | Quyết định | Chỉ lấy phần nào | Consumer |
|---|---|---|---|
| DeepGHS Character Index | **Giữ — P0** | Series, character, core tags, post count | `character-profile`, `blind-cast`, `shot-spec` |
| DraconicDragon Danbooru CSV | **Giữ có chọn lọc — P1** | Chỉ Danbooru tag gắn với `character_tags` đã import + aliases | `catalog-ingest`, `character-profile` |
| AI Pose Gallery outfit JSON | **Giữ có chọn lọc — P1** | `costume-zh.json`, `costume-anime-zh.json`: tên/tags/keywords | `character-profile`, `shot-spec`, `continuity` |
| AI Pose Gallery pose JSON | **Pilot sau — P1** | Chỉ sau khi caption tiếng Anh đã review; hiện `enabled:false` | `shot-spec`, `anima-prompt` |
| Danbooru API aliases/implications | **P1, thủ công** | Export có sẵn; không bypass Cloudflare | `catalog-ingest` |
| Wikidata | **Để sau — P2** | ID/alias/series khi cần | `character-profile` |
| PoseScript | **Để sau — P2** | Caption pose nếu pose gallery chưa đủ | `shot-spec` |
| e621 namespace | **Loại** | Không nhập | Không có consumer MVP |
| Portrait catalog | **Loại** | Không tải/không import | Không có consumer |
| COCO | **Loại** | Không collect | Không có runtime consumer |
| Grounded SAM | **Loại** | Không collect | Tool ảnh, không phải catalog |
| OpenPose / skeleton | **Loại** | Không collect | Không có runtime consumer |
| Render job/ảnh/output | **Loại khỏi DB** | File/DB riêng của renderer | Ngoài Novel2Moss DB |

## Thứ tự import V2

1. `seed` vocabulary/source registry.
2. DeepGHS `blue_archive.md` → characters/core tags `UNVERIFIED`.
3. Danbooru CSV với `--from-character-core-tags` → canonical tags + aliases; không e621.
4. Outfit generic JSON → `outfits/outfit_parts/catalog_captions`, `GENERIC/UNVERIFIED`, không ảnh.
5. Chỉ bật pose gallery sau khi có English caption review + consumer test.
6. Alias/implication/Wikidata/PoseScript chỉ khi có export hợp lệ và consumer rõ.

## Lệnh mẫu

```powershell
python database/src/collect_sources.py fetch --source deepghs
python database/src/collect_sources.py fetch --source ai_pose_gallery
python database/src/collect_sources.py fetch --source dbr_e621_lists
python database/src/collect_sources.py verify

python database/src/n2m_db.py import-deepghs-md database/imports/deepghs/blue_archive.md
python database/src/n2m_db.py import-tags-csv database/imports/dbr-e621-lists-archive/danbooru/danbooru_2026-10-01_pt20-ia-dd.csv --namespace danbooru --from-character-core-tags
python database/src/n2m_db.py import-costume-gallery-json database/imports/ai-pose-gallery/data/costume-zh.json --source-id ai_pose_gallery
python database/src/n2m_db.py import-costume-gallery-json database/imports/ai-pose-gallery/data/costume-anime-zh.json --source-id charadb
```

## Yêu cầu chống mất dữ liệu và suy diễn

- Không tự đổi `UNKNOWN` thành tuổi/giới tính/quan hệ/outfit canon đã xác minh.
- Khóa uniqueness theo `(source_id, external_key)`; nhập lại cùng nội dung không tạo duplicate. Nếu nguồn đổi, ghi `source_record_versions`.
- Không coi post_count là độ tin cậy ngữ nghĩa; không coi tag là caption.
- Alias tag không phải alias nhân vật; variant character không tự merge.
- Chỉ nhập dữ liệu có consumer thật; số record không phải KPI.
- `source_registry.license_label` chỉ là ghi chú vận hành, không phải chứng nhận pháp lý.
- Không tạo record/số liệu không có thật; `seed` chỉ là dữ liệu local nhỏ.
