# Mô tả nội dung các bảng SQL — Novel2Anima

- **Database**: `db/novel_anima.db` (chỉ cấu trúc, không kèm dữ liệu DB)
- **Thời điểm dump**: 2026-10-22T09:06:23
- **Git commit**: `e64835f388a5a87a59d5706dd2ca7d15b6187f4f`
- **Git branch**: `main`
- **Số bảng người dùng**: 23 (+ FTS5 shadow tables không liệt kê)

> Các bảng `sqlite_*` và `visual_concept_fts_data/_idx/_docsize/_config` là nội bộ SQLite/FTS5, không đưa vào mô tả. `current_schema.sql` chứa DDL đã dump từ DB hiện tại; `schema_v1.sql` và `migrations/*.sql` là nguồn dựng schema ban đầu.

## Tổng quan

| # | Bảng | Nhóm | Số dòng | Mục đích ngắn |
|---:|---|---|---:|---|
| 1 | `source_snapshot` | Catalog / provenance | 11 | Mỗi lần nhập một nguồn dữ liệu (5 nguồn pinned + các dump local). |
| 2 | `tag` | Catalog / vocabulary | 1,208,773 | Từ điển tag canonical dùng làm cú pháp prompt. |
| 3 | `tag_source` | Catalog / provenance | 1,479,995 | Provenance chi tiết của từng tag theo từng nguồn. |
| 4 | `tag_alias` | Catalog / vocabulary | 149,546 | Alias name trỏ về một tag canonical. |
| 5 | `tag_role` | Catalog / vocabulary | 30,265 | Vai trò của tag khi dựng prompt. |
| 6 | `tag_relation` | Catalog / relations | 213,175 | Quan hệ có hướng giữa hai tag. |
| 7 | `tag_content_label` | Catalog / content metadata | 9,994 | Nhãn nội dung gắn với tag. |
| 8 | `visual_concept` | Catalog / concepts | 583 | Khái niệm thị giác dùng cho planning và retrieval. |
| 9 | `concept_tag` | Catalog / concepts | 9,741 | Map khái niệm sang tag cú pháp. |
| 10 | `concept_relation` | Catalog / concepts | 0 | Quan hệ có hướng giữa hai visual concept. |
| 11 | `visual_concept_fts` | Catalog / search index | 583 | FTS5 virtual table cho visual_concept. |
| 12 | `model_profile` | Runtime / render config | 0 | Cấu hình model và workflow render. |
| 13 | `project` | Runtime / project | 31 | Dự án truyện. |
| 14 | `character_profile` | Runtime / project | 574 | Nhân vật trong một project. |
| 15 | `act` | Runtime / story | 77 | Act trong một project. |
| 16 | `shot` | Runtime / story | 7,099 | Một shot cụ thể trong act. |
| 17 | `generation` | Runtime / history | 0 | Lịch sử render của shot. |
| 18 | `shot_state` | Runtime / continuity | 665 | Continuity state theo shot/axis (experimental). |
| 19 | `act_continuity` | Runtime / continuity | 48 | Continuity gốc của act theo axis. |
| 20 | `shot_finding` | Runtime / QA | 69 | Finding QA cho một shot. |
| 21 | `shot_observation` | Runtime / inference | 0 | Observation suy luận theo shot/axis/source. |
| 22 | `act_observation` | Runtime / inference | 0 | Observation suy luận cấp act/axis/source. |
| 23 | `act_publication` | Runtime / publication | 27 | Outbox publish prompt file cho act/revision. |

## Dữ liệu tự sinh hiện tại

Các con số dưới đây lấy trực tiếp từ DB tại thời điểm đóng gói; chúng giúp phân biệt dữ liệu nguồn/curated với dữ liệu suy diễn (derived).

| Hạng mục | Giá trị |
|---|---:|
| `visual_concept` derived (POSE_/TG_/WC_) | 583 / 583 |
| `tag_relation` compatible (posts co-occurrence) | 24,526 |
| `tag_content_label` derived từ posts rating | 9,446 |
| `tag` category NULL (thêm từ posts) | 20,562 |
| `tag` post_count=0 | 95,196 |
| `project` / `act` / `shot` | 31 / 77 / 7,099 |

## Chi tiết từng bảng

### `source_snapshot`

- **Nhóm**: Catalog / provenance
- **Số dòng**: 11
- **Mục đích**: Mỗi lần nhập một nguồn dữ liệu (5 nguồn pinned + các dump local).
- **Nội dung**: Lưu source_key, source_url, revision/commit, license_note, sha256 và thời điểm import. Đây là gốc của mọi provenance; các bảng tag_source/tag_relation tham chiếu source_id về đây.
- **Ghi chú**: UNIQUE(source_key, revision) giúp import idempotent.

| Cột | Kiểu | NOT NULL | PK | Default |
|---|---|---:|---:|---|
| `id` | INTEGER |  | yes |  |
| `source_key` | TEXT | yes |  |  |
| `source_url` | TEXT | yes |  |  |
| `revision` | TEXT | yes |  |  |
| `license_note` | TEXT |  |  |  |
| `sha256` | TEXT |  |  |  |
| `imported_at` | TEXT | yes |  | CURRENT_TIMESTAMP |

### `tag`

- **Nhóm**: Catalog / vocabulary
- **Số dòng**: 1,208,773
- **Mục đích**: Từ điển tag canonical dùng làm cú pháp prompt.
- **Nội dung**: Một dòng cho mỗi canonical_name (dạng underscore, ví dụ looking_back). search_name là dạng có khoảng trắng; danbooru_category là general/artist/copyright/character/meta; post_count là độ phổ biến; taxonomy_status là trạng thái review của nguồn taxonomy.
- **Ghi chú**: Không chứa quan hệ hay concept. Tag thêm từ posts có thể có category NULL và taxonomy_status='unreviewed'.
- **Hiện trạng dữ liệu**: Trong DB hiện tại: 20,562 tag có danbooru_category NULL (thêm từ posts) và 95,196 tag có post_count=0.

| Cột | Kiểu | NOT NULL | PK | Default |
|---|---|---:|---:|---|
| `id` | INTEGER |  | yes |  |
| `canonical_name` | TEXT | yes |  |  |
| `search_name` | TEXT | yes |  |  |
| `danbooru_category` | TEXT |  |  |  |
| `post_count` | INTEGER | yes |  | 0 |
| `taxonomy_status` | TEXT | yes |  | 'unreviewed' |

### `tag_source`

- **Nhóm**: Catalog / provenance
- **Số dòng**: 1,479,995
- **Mục đích**: Provenance chi tiết của từng tag theo từng nguồn.
- **Nội dung**: Mỗi dòng nối tag_id với source_snapshot và source_ref; source_metadata là JSON giữ field gốc của nguồn (ví dụ category/slot/confidence, wiki body, observed_posts).
- **Ghi chú**: Khóa chính (tag_id, source_id, source_ref). Dùng để trả lời tag này đến từ đâu và giữ metadata gốc.

| Cột | Kiểu | NOT NULL | PK | Default |
|---|---|---:|---:|---|
| `tag_id` | INTEGER | yes | yes |  |
| `source_id` | INTEGER | yes | yes |  |
| `source_ref` | TEXT | yes | yes | '' |
| `source_metadata` | TEXT | yes |  | '{}' |

**Khóa ngoại**:

| Cột | Bảng đích | Cột đích | ON DELETE |
|---|---|---|---|
| `source_id` | `source_snapshot` | `id` | CASCADE |
| `tag_id` | `tag` | `id` | CASCADE |

### `tag_alias`

- **Nhóm**: Catalog / vocabulary
- **Số dòng**: 149,546
- **Mục đích**: Alias name trỏ về một tag canonical.
- **Nội dung**: alias_name là khóa chính; tag_id là tag đích; source_id là nguồn ghi nhận alias.
- **Ghi chú**: Xung đột alias được xử lý first-writer-wins; alias thua không được lưu thành dòng riêng.

| Cột | Kiểu | NOT NULL | PK | Default |
|---|---|---:|---:|---|
| `alias_name` | TEXT |  | yes |  |
| `tag_id` | INTEGER | yes |  |  |
| `source_id` | INTEGER |  |  |  |

**Khóa ngoại**:

| Cột | Bảng đích | Cột đích | ON DELETE |
|---|---|---|---|
| `source_id` | `source_snapshot` | `id` | NO ACTION |
| `tag_id` | `tag` | `id` | CASCADE |

### `tag_role`

- **Nhóm**: Catalog / vocabulary
- **Số dòng**: 30,265
- **Mục đích**: Vai trò của tag khi dựng prompt.
- **Nội dung**: Một tag có thể có nhiều role: identity, outfit, action, expression, pose, motion, camera, composition, background, style, interaction, other. confidence và source_id cho biết độ tin cậy/nguồn.
- **Ghi chú**: Dùng cho retrieval theo role; không phải mọi tag đều có role.

| Cột | Kiểu | NOT NULL | PK | Default |
|---|---|---:|---:|---|
| `tag_id` | INTEGER | yes | yes |  |
| `role` | TEXT | yes | yes |  |
| `confidence` | REAL | yes |  | 1.0 |
| `source_id` | INTEGER |  |  |  |

**Khóa ngoại**:

| Cột | Bảng đích | Cột đích | ON DELETE |
|---|---|---|---|
| `source_id` | `source_snapshot` | `id` | NO ACTION |
| `tag_id` | `tag` | `id` | CASCADE |

### `tag_relation`

- **Nhóm**: Catalog / relations
- **Số dòng**: 213,175
- **Mục đích**: Quan hệ có hướng giữa hai tag.
- **Nội dung**: relation gồm implies, conflicts, compatible, recommends. weight là trọng số; source_id và note giữ nguồn/giải thích. IMPLIES lấy từ implication graph; compatible có thể là dữ liệu derived từ co-occurrence posts.
- **Ghi chú**: Khóa chính (from_tag_id, to_tag_id, relation); CHECK cấm self-relation.
- **Hiện trạng dữ liệu**: Trong DB hiện tại: implies=102,535, recommends=82,820, compatible=24,526 (derived từ posts co-occurrence), conflicts=3,294.

| Cột | Kiểu | NOT NULL | PK | Default |
|---|---|---:|---:|---|
| `from_tag_id` | INTEGER | yes | yes |  |
| `to_tag_id` | INTEGER | yes | yes |  |
| `relation` | TEXT | yes | yes |  |
| `weight` | REAL | yes |  | 1.0 |
| `source_id` | INTEGER |  |  |  |
| `note` | TEXT |  |  |  |

**Khóa ngoại**:

| Cột | Bảng đích | Cột đích | ON DELETE |
|---|---|---|---|
| `source_id` | `source_snapshot` | `id` | NO ACTION |
| `to_tag_id` | `tag` | `id` | CASCADE |
| `from_tag_id` | `tag` | `id` | CASCADE |

### `tag_content_label`

- **Nhóm**: Catalog / content metadata
- **Số dòng**: 9,994
- **Mục đích**: Nhãn nội dung gắn với tag.
- **Nội dung**: scope gồm neutral, adult, contextual, unreviewed, blocked; confidence, rationale, reviewed_at. blocked thường lấy từ banned_tags; adult/contextual có thể được suy ra từ rating histogram của posts.
- **Ghi chú**: Nhãn nguồn là dữ liệu tham khảo, không tự quyết định quyền render của model.
- **Hiện trạng dữ liệu**: Trong DB hiện tại: adult=4,994, contextual=4,452, blocked=548; 9,446 dòng là derived từ posts rating.

| Cột | Kiểu | NOT NULL | PK | Default |
|---|---|---:|---:|---|
| `tag_id` | INTEGER |  | yes |  |
| `scope` | TEXT | yes |  |  |
| `confidence` | REAL | yes |  | 1.0 |
| `rationale` | TEXT |  |  |  |
| `reviewed_at` | TEXT |  |  |  |

**Khóa ngoại**:

| Cột | Bảng đích | Cột đích | ON DELETE |
|---|---|---|---|
| `tag_id` | `tag` | `id` | CASCADE |

### `visual_concept`

- **Nhóm**: Catalog / concepts
- **Số dòng**: 583
- **Mục đích**: Khái niệm thị giác dùng cho planning và retrieval.
- **Nội dung**: code là định danh duy nhất; kind gồm action, expression, pose, motion, camera, interaction, other. name/description/search_terms phục vụ FTS; energy là cường độ; content_scope và review_status là metadata review; metadata_json giữ nguồn và cấu trúc gốc.
- **Ghi chú**: Gồm concept curated và concept derived (ví dụ POSE_*, TG_*, WC_*). Cần đọc provenance trước khi coi là curated.
- **Hiện trạng dữ liệu**: Trong DB hiện tại: 583/583 concept là derived (POSE_=297, TG_=48, WC_=238); chưa có concept curated tay.

| Cột | Kiểu | NOT NULL | PK | Default |
|---|---|---:|---:|---|
| `id` | INTEGER |  | yes |  |
| `code` | TEXT | yes |  |  |
| `kind` | TEXT | yes |  |  |
| `name` | TEXT | yes |  |  |
| `description` | TEXT | yes |  | '' |
| `search_terms` | TEXT | yes |  | '' |
| `energy` | INTEGER |  |  |  |
| `content_scope` | TEXT | yes |  | 'contextual' |
| `review_status` | TEXT | yes |  | 'draft' |
| `prompt_template` | TEXT |  |  |  |
| `metadata_json` | TEXT | yes |  | '{}' |

### `concept_tag`

- **Nhóm**: Catalog / concepts
- **Số dòng**: 9,741
- **Mục đích**: Map khái niệm sang tag cú pháp.
- **Nội dung**: concept_id + tag_id + usage (primary/optional/alternative) + priority. Một concept có thể có nhiều tag; một tag có thể thuộc nhiều concept.
- **Ghi chú**: Đây là cầu nối giữa visual_concept (ngữ nghĩa) và tag (cú pháp model).

| Cột | Kiểu | NOT NULL | PK | Default |
|---|---|---:|---:|---|
| `concept_id` | INTEGER | yes | yes |  |
| `tag_id` | INTEGER | yes | yes |  |
| `usage` | TEXT | yes | yes |  |
| `priority` | INTEGER | yes |  | 100 |

**Khóa ngoại**:

| Cột | Bảng đích | Cột đích | ON DELETE |
|---|---|---|---|
| `tag_id` | `tag` | `id` | CASCADE |
| `concept_id` | `visual_concept` | `id` | CASCADE |

### `concept_relation`

- **Nhóm**: Catalog / concepts
- **Số dòng**: 0
- **Mục đích**: Quan hệ có hướng giữa hai visual concept.
- **Nội dung**: relation gồm compatible, recommends, conflicts, subtype_of; weight và note giữ giải thích.
- **Ghi chú**: Hiện bảng chưa có dữ liệu; retrieval phải coi đây là curation gap nếu cần quan hệ concept.
- **Hiện trạng dữ liệu**: Trong DB hiện tại chưa có dòng; đây là curation gap nếu planning cần quan hệ concept.

| Cột | Kiểu | NOT NULL | PK | Default |
|---|---|---:|---:|---|
| `from_concept_id` | INTEGER | yes | yes |  |
| `to_concept_id` | INTEGER | yes | yes |  |
| `relation` | TEXT | yes | yes |  |
| `weight` | REAL | yes |  | 1.0 |
| `note` | TEXT |  |  |  |

**Khóa ngoại**:

| Cột | Bảng đích | Cột đích | ON DELETE |
|---|---|---|---|
| `to_concept_id` | `visual_concept` | `id` | CASCADE |
| `from_concept_id` | `visual_concept` | `id` | CASCADE |

### `visual_concept_fts`

- **Nhóm**: Catalog / search index
- **Số dòng**: 583
- **Mục đích**: FTS5 virtual table cho visual_concept.
- **Nội dung**: Index name/description/search_terms của visual_concept, dùng cho tìm kiếm toàn văn. Các bảng visual_concept_fts_data/_idx/_docsize/_config là shadow table nội bộ của SQLite, không đưa vào mô tả.
- **Ghi chú**: Trigger trên visual_concept tự đồng bộ FTS; verify kiểm tra số dòng FTS khớp số concept.

| Cột | Kiểu | NOT NULL | PK | Default |
|---|---|---:|---:|---|
| `name` | (any) |  |  |  |
| `description` | (any) |  |  |  |
| `search_terms` | (any) |  |  |  |

### `model_profile`

- **Nhóm**: Runtime / render config
- **Số dòng**: 0
- **Mục đích**: Cấu hình model và workflow render.
- **Nội dung**: code, model_name, lora_name, steps, cfg, sampler, workflow_version, config_json.
- **Ghi chú**: Hiện chưa có dòng; dữ liệu này sẽ được dùng khi ghi generation.
- **Hiện trạng dữ liệu**: Trong DB hiện tại chưa có dòng.

| Cột | Kiểu | NOT NULL | PK | Default |
|---|---|---:|---:|---|
| `id` | INTEGER |  | yes |  |
| `code` | TEXT | yes |  |  |
| `model_name` | TEXT | yes |  |  |
| `lora_name` | TEXT |  |  |  |
| `steps` | INTEGER | yes |  | 4 |
| `cfg` | REAL | yes |  | 1.0 |
| `sampler` | TEXT | yes |  | 'er_sde' |
| `workflow_version` | TEXT |  |  |  |
| `config_json` | TEXT | yes |  | '{}' |

### `project`

- **Nhóm**: Runtime / project
- **Số dòng**: 31
- **Mục đích**: Dự án truyện.
- **Nội dung**: title, idea, content_profile (sfw/nsfw/mixed), style_json, created_at.
- **Ghi chú**: Là gốc của character_profile và act. Dữ liệu runtime không thuộc catalog dùng chung.

| Cột | Kiểu | NOT NULL | PK | Default |
|---|---|---:|---:|---|
| `id` | INTEGER |  | yes |  |
| `title` | TEXT | yes |  |  |
| `idea` | TEXT | yes |  | '' |
| `content_profile` | TEXT | yes |  | 'mixed' |
| `style_json` | TEXT | yes |  | '{}' |
| `created_at` | TEXT | yes |  | CURRENT_TIMESTAMP |

### `character_profile`

- **Nhóm**: Runtime / project
- **Số dòng**: 574
- **Mục đích**: Nhân vật trong một project.
- **Nội dung**: code, identity_json (identity_tags, attributes, adult...), outfit_json (default, variants, assumed...). UNIQUE(project_id, code).
- **Ghi chú**: identity_json/outfit_json là dữ liệu runtime do người dùng/plan cung cấp, không phải tag catalog.

| Cột | Kiểu | NOT NULL | PK | Default |
|---|---|---:|---:|---|
| `id` | INTEGER |  | yes |  |
| `project_id` | INTEGER | yes |  |  |
| `code` | TEXT | yes |  |  |
| `identity_json` | TEXT | yes |  | '{}' |
| `outfit_json` | TEXT | yes |  | '{}' |

**Khóa ngoại**:

| Cột | Bảng đích | Cột đích | ON DELETE |
|---|---|---|---|
| `project_id` | `project` | `id` | CASCADE |

### `act`

- **Nhóm**: Runtime / story
- **Số dòng**: 77
- **Mục đích**: Act trong một project.
- **Nội dung**: act_no, title, outline, revision, status (draft/planned/approved/locked). UNIQUE(project_id, act_no, revision).
- **Ghi chú**: Revision tăng khi thay đổi act đã có generation history; không ghi đè lịch sử cũ.

| Cột | Kiểu | NOT NULL | PK | Default |
|---|---|---:|---:|---|
| `id` | INTEGER |  | yes |  |
| `project_id` | INTEGER | yes |  |  |
| `act_no` | INTEGER | yes |  |  |
| `title` | TEXT | yes |  |  |
| `outline` | TEXT | yes |  | '' |
| `revision` | INTEGER | yes |  | 1 |
| `status` | TEXT | yes |  | 'draft' |

**Khóa ngoại**:

| Cột | Bảng đích | Cột đích | ON DELETE |
|---|---|---|---|
| `project_id` | `project` | `id` | CASCADE |

### `shot`

- **Nhóm**: Runtime / story
- **Số dòng**: 7,099
- **Mục đích**: Một shot cụ thể trong act.
- **Nội dung**: shot_no, character_id, các concept FK (action/expression/pose/camera), signature, shot_spec_json, content_mode, status. UNIQUE(act_id, shot_no).
- **Ghi chú**: shot_spec_json là nguồn chi tiết cho prompt/QA; các cột concept FK chỉ là con trỏ tóm tắt.
- **Hiện trạng dữ liệu**: Trong DB hiện tại: 7,099 shot, tất cả status='planned', content_mode='nsfw'.

| Cột | Kiểu | NOT NULL | PK | Default |
|---|---|---:|---:|---|
| `id` | INTEGER |  | yes |  |
| `act_id` | INTEGER | yes |  |  |
| `shot_no` | INTEGER | yes |  |  |
| `character_id` | INTEGER |  |  |  |
| `action_concept_id` | INTEGER |  |  |  |
| `expression_concept_id` | INTEGER |  |  |  |
| `pose_concept_id` | INTEGER |  |  |  |
| `camera_concept_id` | INTEGER |  |  |  |
| `signature` | TEXT |  |  |  |
| `shot_spec_json` | TEXT | yes |  | '{}' |
| `content_mode` | TEXT | yes |  | 'sfw' |
| `status` | TEXT | yes |  | 'planned' |
| `created_at` | TEXT | yes |  | CURRENT_TIMESTAMP |

**Khóa ngoại**:

| Cột | Bảng đích | Cột đích | ON DELETE |
|---|---|---|---|
| `camera_concept_id` | `visual_concept` | `id` | NO ACTION |
| `pose_concept_id` | `visual_concept` | `id` | NO ACTION |
| `expression_concept_id` | `visual_concept` | `id` | NO ACTION |
| `action_concept_id` | `visual_concept` | `id` | NO ACTION |
| `character_id` | `character_profile` | `id` | NO ACTION |
| `act_id` | `act` | `id` | CASCADE |

### `generation`

- **Nhóm**: Runtime / history
- **Số dòng**: 0
- **Mục đích**: Lịch sử render của shot.
- **Nội dung**: model_profile_id, prompt, seed, image_path, image_sha256, evaluation_json, decision (pending/approved/rejected), created_at.
- **Ghi chú**: Không lưu bytes ảnh; chỉ lưu đường dẫn/hash và đánh giá. Rejected vẫn giữ làm bằng chứng chẩn đoán.
- **Hiện trạng dữ liệu**: Trong DB hiện tại chưa có dòng render nào.

| Cột | Kiểu | NOT NULL | PK | Default |
|---|---|---:|---:|---|
| `id` | INTEGER |  | yes |  |
| `shot_id` | INTEGER | yes |  |  |
| `model_profile_id` | INTEGER | yes |  |  |
| `prompt` | TEXT | yes |  |  |
| `seed` | INTEGER |  |  |  |
| `image_path` | TEXT |  |  |  |
| `image_sha256` | TEXT |  |  |  |
| `evaluation_json` | TEXT | yes |  | '{}' |
| `decision` | TEXT | yes |  | 'pending' |
| `created_at` | TEXT | yes |  | CURRENT_TIMESTAMP |

**Khóa ngoại**:

| Cột | Bảng đích | Cột đích | ON DELETE |
|---|---|---|---|
| `model_profile_id` | `model_profile` | `id` | NO ACTION |
| `shot_id` | `shot` | `id` | CASCADE |

### `shot_state`

- **Nhóm**: Runtime / continuity
- **Số dòng**: 665
- **Mục đích**: Continuity state theo shot/axis (experimental).
- **Nội dung**: axis, value_tag_id, severity, since_shot_no, cause_shot_no, source. PK(shot_id, axis).
- **Ghi chú**: Là dữ liệu suy luận/placeholder, không phải nguồn chân lý; thiếu dòng không chứng minh trạng thái vắng mặt.

| Cột | Kiểu | NOT NULL | PK | Default |
|---|---|---:|---:|---|
| `shot_id` | INTEGER | yes | yes |  |
| `axis` | TEXT | yes | yes |  |
| `value_tag_id` | INTEGER |  |  |  |
| `severity` | REAL | yes |  | 0.5 |
| `since_shot_no` | INTEGER | yes |  |  |
| `cause_shot_no` | INTEGER | yes |  |  |
| `source` | TEXT | yes |  | 'inferred:v0' |

**Khóa ngoại**:

| Cột | Bảng đích | Cột đích | ON DELETE |
|---|---|---|---|
| `value_tag_id` | `tag` | `id` | NO ACTION |
| `shot_id` | `shot` | `id` | CASCADE |

### `act_continuity`

- **Nhóm**: Runtime / continuity
- **Số dòng**: 48
- **Mục đích**: Continuity gốc của act theo axis.
- **Nội dung**: axis, initial_tag_id, notes. PK(act_id, axis).
- **Ghi chú**: Dùng làm mốc continuity cấp act; observation suy luận nằm ở bảng riêng.

| Cột | Kiểu | NOT NULL | PK | Default |
|---|---|---:|---:|---|
| `act_id` | INTEGER | yes | yes |  |
| `axis` | TEXT | yes | yes |  |
| `initial_tag_id` | INTEGER |  |  |  |
| `notes` | TEXT | yes |  | '' |

**Khóa ngoại**:

| Cột | Bảng đích | Cột đích | ON DELETE |
|---|---|---|---|
| `initial_tag_id` | `tag` | `id` | NO ACTION |
| `act_id` | `act` | `id` | CASCADE |

### `shot_finding`

- **Nhóm**: Runtime / QA
- **Số dòng**: 69
- **Mục đích**: Finding QA cho một shot.
- **Nội dung**: rule_id, source, axis, value_tag_id, severity, evidence_json, status, created_at. UNIQUE(shot_id, rule_id, source).
- **Ghi chú**: Tách rule engine (qa:v1) và LLM review (qa:llm:v1) để không ghi đè nhau. Finding là bằng chứng, không tự sửa prompt.

| Cột | Kiểu | NOT NULL | PK | Default |
|---|---|---:|---:|---|
| `id` | INTEGER |  | yes |  |
| `shot_id` | INTEGER | yes |  |  |
| `rule_id` | TEXT | yes |  |  |
| `source` | TEXT | yes |  |  |
| `axis` | TEXT |  |  |  |
| `value_tag_id` | INTEGER |  |  |  |
| `severity` | REAL | yes |  | 0.5 |
| `evidence_json` | TEXT | yes |  | '{}' |
| `status` | TEXT | yes |  | 'open' |
| `created_at` | TEXT | yes |  | CURRENT_TIMESTAMP |

**Khóa ngoại**:

| Cột | Bảng đích | Cột đích | ON DELETE |
|---|---|---|---|
| `value_tag_id` | `tag` | `id` | NO ACTION |
| `shot_id` | `shot` | `id` | CASCADE |

### `shot_observation`

- **Nhóm**: Runtime / inference
- **Số dòng**: 0
- **Mục đích**: Observation suy luận theo shot/axis/source.
- **Nội dung**: value_tag_id, severity, since_shot_no, cause_shot_no, source. PK(shot_id, axis, source).
- **Ghi chú**: Không authoritative; infer_state chỉ được ghi/xóa dòng do chính nó tạo.

| Cột | Kiểu | NOT NULL | PK | Default |
|---|---|---:|---:|---|
| `shot_id` | INTEGER | yes | yes |  |
| `axis` | TEXT | yes | yes |  |
| `value_tag_id` | INTEGER |  |  |  |
| `severity` | REAL | yes |  | 0.5 |
| `since_shot_no` | INTEGER | yes |  |  |
| `cause_shot_no` | INTEGER | yes |  |  |
| `source` | TEXT | yes | yes |  |

**Khóa ngoại**:

| Cột | Bảng đích | Cột đích | ON DELETE |
|---|---|---|---|
| `value_tag_id` | `tag` | `id` | NO ACTION |
| `shot_id` | `shot` | `id` | CASCADE |

### `act_observation`

- **Nhóm**: Runtime / inference
- **Số dòng**: 0
- **Mục đích**: Observation suy luận cấp act/axis/source.
- **Nội dung**: initial_tag_id, notes, source. PK(act_id, axis, source).
- **Ghi chú**: Không authoritative; dùng để tham khảo trước khi chốt act_continuity.

| Cột | Kiểu | NOT NULL | PK | Default |
|---|---|---:|---:|---|
| `act_id` | INTEGER | yes | yes |  |
| `axis` | TEXT | yes | yes |  |
| `initial_tag_id` | INTEGER |  |  |  |
| `notes` | TEXT | yes |  | '' |
| `source` | TEXT | yes | yes |  |

**Khóa ngoại**:

| Cột | Bảng đích | Cột đích | ON DELETE |
|---|---|---|---|
| `initial_tag_id` | `tag` | `id` | NO ACTION |
| `act_id` | `act` | `id` | CASCADE |

### `act_publication`

- **Nhóm**: Runtime / publication
- **Số dòng**: 27
- **Mục đích**: Outbox publish prompt file cho act/revision.
- **Nội dung**: prompt_path, prompt_sha256, negative_path, negative_sha256, pending, updated_at. PK(act_id, revision).
- **Ghi chú**: pending=1 trong khoảng giữa commit DB và thay file; rerun cùng plan sẽ reconcile và clear.

| Cột | Kiểu | NOT NULL | PK | Default |
|---|---|---:|---:|---|
| `act_id` | INTEGER | yes | yes |  |
| `revision` | INTEGER | yes | yes |  |
| `prompt_path` | TEXT | yes |  |  |
| `prompt_sha256` | TEXT | yes |  |  |
| `negative_path` | TEXT |  |  |  |
| `negative_sha256` | TEXT |  |  |  |
| `pending` | INTEGER | yes |  | 1 |
| `updated_at` | TEXT | yes |  |  |

**Khóa ngoại**:

| Cột | Bảng đích | Cột đích | ON DELETE |
|---|---|---|---|
| `act_id` | `act` | `id` | CASCADE |

