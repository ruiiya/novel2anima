# Backfill quan hệ V4 (PR-02)

## Phạm vi

PR-02 chỉ đọc dữ liệu legacy và ghi các bảng chiếu additive:

- `project_document_revision` từ `project` (brief revision 1);
- `character_identity_revision` từ `character_profile.identity_json`;
- `outfit_revision` + `outfit_item` từ `character_profile.outfit_json`;
- `shot_spec_revision` từ `shot.shot_spec_json`;
- `shot_participant` từ `shot.character_id` + `participants[].code` rõ ràng;
- `shot_interaction` chỉ từ `interaction` hoặc `sequence` có actor/target/action;
- `shot_outfit_binding` chỉ khi tập tag outfit khớp **chính xác** với một
  `outfit_revision` của đúng nhân vật.

Không suy diễn actor/target cho duo từ thứ tự participant, giới tính, gaze
hay tag. Không đọc/ghi file kế hoạch bên ngoài; phần đó thuộc PR-03.

## Chạy

```powershell
$env:PYTHONPATH = "src"

# Rehearsal: ghi trong transaction rồi rollback
python scripts\migrations\backfill_legacy_v4.py `
  --db db\backup\pr-01\staging_live.db `
  --dry-run `
  --report evidence\pr-02\backfill_dry_run.json

# Apply trên staging copy; backup trước khi ghi
python scripts\migrations\backfill_legacy_v4.py `
  --db db\backup\pr-01\staging_live.db `
  --backup db\backup\pr-02\staging_pre_backfill.db `
  --report evidence\pr-02\backfill_apply.json
```

Runner từ chối `db/novel_anima.db` trừ khi truyền `--allow-live` cho một cutover
drill đã duyệt. Backfill idempotent: lần chạy lại chỉ skip các revision đã có.

## Kết quả staging (2026-10-22)

| Hạng mục | Kết quả |
|---|---:|
| Project documents | 31 |
| Character identities | 574 |
| Outfit revisions / items | 1.142 / 2.805 |
| Shot specs | 7.099 |
| Participants | 10.444 |
| Interactions có nguồn rõ ràng | 1.160 |
| Outfit bindings khớp chính xác | 339 |
| Reconciliation items | 12.506 |

- 1.160 interaction gồm 1.011 từ `interaction` và 149 từ `sequence`.
- 2.413 shot có từ 2 participant trở lên. 1.253 shot trong số đó không có
  actor/target rõ ràng nên bị đưa vào queue, **không tạo** `shot_interaction`.
- 1.138 outfit item chỉ có tên tự do, không có tag ID; 10 tag ID không tồn tại
  trong catalog hiện tại. Cả hai đều được giữ nguyên và đánh dấu. Revision có
  item thiếu tag ID không được dùng để exact-match binding.
- 7.365 participant có outfit tag không khớp chính xác revision nào; 2.740
  participant không có outfit tag trong shot. Đây là dữ liệu chưa đủ để pin
  wardrobe, nên vào queue thay vì tạo revision giả.

## Queue

Bảng `reconciliation_item` (migration `007_reconciliation_queue.sql`) có
`gap_key` duy nhất, domain/severity/rule, FK project/act/shot/character và
`evidence_json`. Trạng thái mặc định là `open`; chưa có bước tự resolve.

Các rule hiện có:

| Rule | Số lượng | Ý nghĩa |
|---|---:|---|
| `outfit_binding_unmatched` | 7.365 | Có outfit tag nhưng không khớp exact revision |
| `outfit_binding_missing` | 2.740 | Shot/participant không có outfit tag |
| `interaction_actor_target_missing` | 1.253 | Duo+ nhưng thiếu actor/target nguồn |
| `outfit_item_tag_missing` | 1.138 | Item outfit không có tag ID |
| `outfit_item_tag_unknown` | 10 | Tag ID không có trong `tag` |

## Kiểm tra

```powershell
python scripts\diagnostics\verify_backfill.py `
  --db db\backup\pr-01\staging_live.db `
  --output evidence\pr-02\backfill_verification.json
```

Diagnostic này chỉ đọc DB và kiểm tra:

- đủ 7.099 shot spec, 10.444 participant, 1.160 interaction, 339 binding;
- mọi participant khớp đúng độ dài `participants[]` và có primary character;
- mọi interaction có actor/target/action từ nguồn rõ ràng;
- mọi binding khớp đúng character và tập tag;
- `quick_check=ok`, `foreign_key_check=[]`;
- `gap_key` không trùng.

## Giới hạn

- Chưa backfill `shot_prompt_revision`, prompt tag/spec (PR-03/06).
- Chưa backfill `continuity_assertion` từ `shot_state` (PR-05).
- Chưa import tài liệu `765/`, plan/review/wardrobe bên ngoài (PR-03).
- `asset_blob` và render/reference image vẫn hoãn.
- Live DB `db/novel_anima.db` không bị ghi; mọi thao tác chạy trên staging copy.
