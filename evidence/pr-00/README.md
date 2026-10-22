# PR-00 — Baseline, backup và inventory

**Trạng thái:** COMPLETE  
**Ngày:** 2026-10-22  
**Branch:** `rebuild/v4`  
**Base commit:** `e64835f388a5a87a59d5706dd2ca7d15b6187f4f`  
**Phạm vi:** chỉ đọc / lưu trữ; không migrate DB thật, không sửa logic hiện hữu.

## 1. Kết quả tổng hợp

| Hạng mục | Kết quả |
|---|---|
| Repo tests | **79 pass**, 0 fail |
| V4 bundle tests | **14 pass**, 0 fail |
| V4 static validation | **PASS** (121 mapping, 11 stage, 33 prompt file) |
| DB audit | `quick_check=ok`, **0 FK violations**, 23 bảng dự kiến |
| DB backup + restore rehearsal | **OK**, source không đổi |
| Inventory | **352 file / 400,31 MiB**, gồm cả `765/` |
| Master mapping | **121/121**, 0 missing |
| Live DB writes | **0** |

## 2. Baseline DB

- File: `db/novel_anima.db`
- Kích thước: **360.968.192 bytes**
- SHA-256: `2cd296ce9be953a85d77acc4d18d46ca7f1531121b4a2d3645e76461fe3b0eac`
- 23 bảng nghiệp vụ; `generation=0`, `model_profile=0`
- `quick_check=ok`; `foreign_key_check` rỗng
- 0 shot sai project; 0 shot thiếu `character_id`
- `tag=1.208.773`; `tag_source=1.479.995`; `tag_relation=213.175`
- `project=31`; `character_profile=574`; `act=77`; `shot=7.099`
- Legacy còn lại: `act_publication=27`; `shot_finding=69`
- Chi tiết: `db_audit.json`, `db_audit_stdout.txt`

## 3. Backup và restore

- Backup: `db/backup/pr-00/pr-00_20261022T034615Z.db`
- Kích thước: **361.881.600 bytes**
- SHA-256: `8f2335e8643b1b02d75ed92a128cd866a41f172b2299fa77cab28605dcd9fabb`
- Nguồn mở **read-only**; SHA-256 trước/sau backup giống nhau
- `integrity_check=ok`, `foreign_key_check` rỗng
- Restore rehearsal: copy backup sang thư mục tạm, kiểm tra integrity/FK/counts, **OK**, sau đó xóa bản tạm
- Chi tiết: `db_backup_report.json`

## 4. Inventory

- **352 file**, **419.750.731 bytes** (400,31 MiB)
- 72 tracked, 280 untracked, 137 ignored
- Đã bao gồm các vùng trước đây bị bỏ sót:
  - `765/`: 50 file, ~6,18 MiB (plan, story, prompt batch)
  - `act_tools/`: 29 file, ~0,4 MiB
  - `prompts/`: 12 file, ~0,31 MiB
  - `data/`: 20 file, ~41,45 MiB
  - `db/`: 4 file, ~350,66 MiB (gồm WAL/SHM)
- Không thấy ảnh/render/reference; `generation=0`
- Chi tiết: `runtime_inventory.json`, `runtime_inventory.csv`

## 5. Mapping 121 dòng

| Nhóm | Tổng | Matched | Moved/Manual | Missing |
|---|---:|---:|---:|---:|
| Source files | 80 | 72 | 8 moved | 0 |
| Legacy DB tables | 23 | 23 | 0 | 0 |
| External runtime | 18 | 15 | 3 manual | 0 |

- 6 snapshot SQL cũ đã được archive vào `docs/db/snapshots/`
- `BUNDLE_README.md` + `MANIFEST.txt` đã archive vào `docs/audits/2026-10-22/`
- 33 file LLM prompt 0 byte đã được tạo tại `llm/prompts/`; 2 DRAFT schema tại `llm/schemas/`
- 3 dòng manual có quyết định riêng tại `mapping_dispositions.csv`:
  1. LLM instructions → `llm_prompt_template` ở PR-06
  2. Render/reference images → **deferred**; người dùng chạy ComfyUI thủ công, không lưu render
  3. Temporary downloads/exports/logs → ephemeral, không import vào DB
- Chi tiết: `mapping_status.csv`, `mapping_status.json`

## 6. Thay đổi trong PR-00

- `docs/v4/`: archive nguyên bộ V4 unified pack
- `docs/audits/2026-10-22/`: bundle README + manifest
- `docs/db/snapshots/`: 6 snapshot schema/stats cũ
- `llm/prompts/`: 33 file `.txt` 0 byte (11 stage × 3)
- `llm/schemas/`: 2 DRAFT JSON schema
- `scripts/diagnostics/`: inventory, backup, mapping tools
- `tests/test_pr00_tools.py`: 4 test mới
- `.gitignore`: mở track cho `docs/v4`, `docs/audits`, `docs/db`, `docs/architecture`, `docs/contracts`, `docs/decisions`, `docs/guides`
- Giữ nguyên 4 file đang sửa của người dùng và untracked `765/`, `dist/`
- Snapshot git: `git_status.txt`, `git_diff.patch`, `git_diff_stat.txt`

## 7. Quyết định và giới hạn

- **Không lưu render**: theo xác nhận của người dùng, ComfyUI được chạy thủ công; nhánh `asset_blob`/visual QC chỉ mở lại khi có ảnh thực tế cần lưu.
- **Không suy luận duo/actor-target** ở PR-00. Các shot duo sẽ vào reconciliation queue ở PR-02.
- **Không rebuild catalog**: 1,2 triệu tag giữ nguyên ID/provenance/FTS.
- **Không chạy 005/006 trên DB thật**. Bước tiếp theo là PR-01 với migration runner và bản staging copy.

## 8. Bước tiếp theo

**PR-01:** migration runner có version/checksum, backup trước apply, chạy `005` + `006` trên **staging copy**, kiểm tra `integrity_check`/FK và rollback. Không đụng DB thật.
