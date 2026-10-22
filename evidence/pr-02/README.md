# PR-02 - Data relational backfill

- **Trạng thái:** COMPLETE
- **Ngày:** 2026-10-22
- **Branch:** `rebuild/v4`
- **Tiền đề:** PR-01 commit `646dd7e`

**Phạm vi:** backfill additive trên **staging copy**; live DB không bị ghi.

## 1. Kết quả

| Hạng mục | Kết quả |
|---|---|
| Migration mới | `007_reconciliation_queue.sql` |
| Apply 007 trên staging | **1 applied**, 5 skipped, 0 failed |
| Dry-run backfill | thành công, rollback sạch |
| Apply backfill | **ok**, `quick_check=ok`, 0 FK violation |
| Chạy lại | **idempotent**, 0 row insert mới |
| Baseline PR-00 | 23/23 bảng giữ nguyên row count |
| Bảng mới sau PR-02 | 34 (33 của 005/006 + `reconciliation_item`) |
| Test suite | **95 pass**, 0 fail |
| V4 bundle tests | **14 pass**, 0 fail |
| Live DB | không đổi size/mtime/hash |

## 2. Dữ liệu đã backfill

| Bảng | Rows | Nguồn / quy tắc |
|---|---:|---|
| `project_document_revision` | 31 | `project` → brief revision 1, lifecycle `draft` |
| `character_identity_revision` | 574 | `character_profile.identity_json` |
| `outfit_revision` | 1.142 | Outfit list + `variants` dict; bỏ metadata `source`/`assumed` |
| `outfit_item` | 2.805 | Từng item được giữ nguyên raw + tag ID nếu có |
| `shot_spec_revision` | 7.099 | `shot.shot_spec_json`, revision 1 |
| `shot_participant` | 10.444 | `shot.character_id` + `participants[].code` rõ ràng |
| `shot_interaction` | 1.160 | Chỉ `interaction` hoặc `sequence` có actor/target/action |
| `shot_outfit_binding` | 339 | Chỉ exact tag-set match với revision cùng character |
| `reconciliation_item` | 12.506 | Gap queue, `gap_key` duy nhất |

### Participant / interaction

- 7.099 shot có participant list; tổng cộng **10.444** participant.
- Per-shot parity: `actual == len(participants[])` cho tất cả shot.
- Không có primary character bị thiếu khỏi `shot_participant`.
- **2.413** shot có từ 2 participant trở lên.
- **1.160** interaction có actor/target/action rõ ràng:
  - 1.011 từ `interaction`;
  - 149 từ `sequence`.
- **1.253** shot duo+ không có actor/target rõ ràng:
  - không tạo `shot_interaction`;
  - đưa vào queue rule `interaction_actor_target_missing`.
- Không có row interaction nào thiếu nguồn explicit; không suy diễn từ thứ tự
  participant, gaze, giới tính hay tag.

### Outfit

- 1.142 outfit revision khớp đúng 1.142 spec list trong legacy JSON.
- 2.805 item khớp đúng số item nguồn (sau khi bỏ variant-name lists và metadata).
- 204 `variants` list chỉ là tên identity variant, không phải outfit item; được
  đếm riêng và không tạo revision giả.
- 1.138 item không có tag ID (tên tự do); vẫn giữ trong `outfit_item`, queue
  `outfit_item_tag_missing`.
- 10 tag ID không có trong bảng `tag`; queue `outfit_item_tag_unknown`.
- 7.365 participant có outfit tag nhưng không khớp exact revision; queue
  `outfit_binding_unmatched`.
- 2.740 participant không có outfit tag trong shot; queue
  `outfit_binding_missing`.
- 0 ambiguous binding.

## 3. Reconciliation queue

Migration 007 thêm `reconciliation_item`:

- `gap_key` unique;
- `domain`, `severity`, `rule_code`;
- FK tùy chọn tới project/act/shot/character;
- `evidence_json` (JSON object);
- `status` mặc định `open`.

| Rule | Rows | Severity |
|---|---:|---|
| `outfit_binding_unmatched` | 7.365 | blocked |
| `outfit_binding_missing` | 2.740 | warning |
| `interaction_actor_target_missing` | 1.253 | blocked |
| `outfit_item_tag_missing` | 1.138 | warning |
| `outfit_item_tag_unknown` | 10 | warning |

Tổng: **12.506 open**, **8.618 blocked**, **3.888 warning**, 0 gap key trùng.

Lưu ý: báo cáo apply ghi `reconciliation.inserted=12.506` và
`existing=20`. Hai mươi attempt bị ignore là cùng `catalog:tag_unknown:<id>`
được tham chiếu bởi nhiều outfit item; bảng chỉ có 10 row cho rule này.

## 4. Migration 007

- File: `sql/migrations/007_reconciliation_queue.sql`
- SHA-256: `4e1131bee95f397a7c0211106edac49ed2c09e05a2431e0f409742ba817ee3f1`
- Apply trên staging:
  `db/backup/pr-01/staging_live.db`
- Backup trước apply:
  `db/backup/pr-02/staging_pre_007.db` (362.307.584 bytes)
- Backup trước backfill:
  `db/backup/pr-02/staging_pre_backfill.db` (362.328.064 bytes)
- Staging sau backfill:
  393.494.528 bytes
  SHA-256: `32ccf2a642e6b6f93b25a31d6b7e7acb6f7ea1fcde0b3300cd2fd59d0d329956`
- Cả hai backup đã mở read-only và kiểm tra: `quick_check=ok`, 0 FK violation.
  `staging_pre_007` có ledger 002→006 và chưa có bảng queue;
  `staging_pre_backfill` có ledger 002→007, các bảng backfill đều 0 row.

## 5. Kiểm tra

`scripts/diagnostics/verify_backfill.py` chạy read-only và trả về `status=ok`:

- 31/31 project document;
- 574/574 identity;
- 7.099/7.099 shot spec;
- 10.444/10.444 participant;
- 1.160 interaction, tất cả có explicit source;
- 339 binding, tất cả đúng character + exact tag set;
- 1.142/1.142 outfit spec, 2.805/2.805 item;
- 12.506 queue row, 12.506 distinct `gap_key`;
- `quick_check=ok`, `foreign_key_check=[]`.

Staging verification so với baseline PR-00:

- 23 baseline tables present;
- 0 baseline table row-count changes;
- 34 new tables;
- `quick_check=ok`, 0 FK violation;
- migration ledger có 6 dòng (002 → 007).

## 6. Tests

- `tests/test_migrations.py`: thêm test migration 007 và cập nhật discovery.
- `tests/test_backfill.py`:
  - backfill đủ identity/outfit/spec/participant/interaction;
  - duo thiếu actor/target → không tạo interaction, có queue;
  - primary participant không bị coi là duplicate;
  - exact outfit binding + unmatched/missing queue;
  - cross-project participant bị chặn;
  - project subset lọc đúng mọi stage;
  - outfit revision thiếu tag ID không được dùng để bind exact;
  - `shot.character_id=NULL` được queue nhưng participant explicit vẫn giữ;
  - dry-run rollback toàn bộ;
  - JSON sai shape bị queue, không tạo row một phần;
  - live DB bị từ chối.
- Full suite: **95 pass**.
- V4 bundle: **14 pass**.

## 7. An toàn live DB

- Live DB: `db/novel_anima.db`
  - size: 360.968.192 bytes
  - SHA-256: `2cd296ce9be953a85d77acc4d18d46ca7f1531121b4a2d3645e76461fe3b0eac`
  - khớp baseline PR-00.
- `db/novel_anima.db-wal` và `-shm` không đổi size/mtime.
- Không chạy migration/backfill trên live path; mọi thao tác trên staging copy.

## 8. Giới hạn / bước tiếp theo

- Chưa backfill prompt (`shot_prompt_revision`, `shot_prompt_tag`,
  `shot_prompt_spec`) — PR-03/06.
- Chưa backfill `continuity_assertion` từ `shot_state` — PR-05.
- Chưa import `765/`, plan/review/wardrobe ngoài DB — PR-03.
- Chưa lưu render/reference image; `asset_blob` vẫn hoãn.
- Queue 12.506 item là dữ liệu thật chưa đủ để pin; PR-05/curation sẽ resolve.

## 9. Artifacts

- `evidence/pr-02/migration_007_dry_run.json`
- `evidence/pr-02/migration_007_apply.json`
- `evidence/pr-02/backfill_dry_run.json`
- `evidence/pr-02/backfill_apply.json`
- `evidence/pr-02/backfill_rerun.json`
- `evidence/pr-02/backfill_verification.json`
- `evidence/pr-02/staging_verification_after_backfill.json`
- `evidence/pr-02/backup_verification.json`
- `evidence/pr-02/tests.txt`
- `evidence/pr-02/v4_bundle_tests.txt`
- `evidence/pr-02/checksums.txt`
