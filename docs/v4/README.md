# Novel2Anima — V4 Unified Standardization Pack

**Ngày:** 2026-10-22  
**Trạng thái:** Bộ thiết kế/tài liệu + SQL DRAFT + công cụ audit/staging **không tác động đến DB gốc**. Không phải code đã refactor hay production migration.

Đây là **bộ V4 hợp nhất thay cho các bộ kế hoạch V1, V2, V3**. Không ghép ba ZIP cũ khi triển khai. Thứ tự tài liệu có hiệu lực: `MASTER_PLAN.md` > `docs/DECISIONS_AND_CONFLICTS.md` > các tài liệu chủ đề V4 > SQL DRAFT tham khảo. Nếu xung đột với code hiện hành, đánh dấu GAP và bổ sung test, không ngầm coi là đã triển khai.

## Các file quan trọng

- `MASTER_PLAN.md`: kế hoạch thực hiện thống nhất P0–P9, thứ tự và tiêu chí nghiệm thu.
- `mappings/MASTER_MAPPING.csv`: **121 dòng** bao phủ 80 source files + 23 DB tables + 18 external-data groups; 3 bản mapping gốc cũng được giữ để đối chiếu.
- `docs/DB_NORMALIZATION.md`: thiết kế lại SQLite, quan hệ, quyền sở hữu dữ liệu, quy tắc dọn legacy.
- `docs/EXTERNAL_DATA_MIGRATION.md`: inventory/hash/import/reconcile + BLOB và file ngoài.
- `docs/SOURCE_REFACTOR.md`: cấu trúc project và migration CLI 29 script `etl/`.
- `docs/LLM_PIPELINE_CONTRACTS.md`: 11 stages, 33 file prompt `.txt` **0 byte**, output theo revision DB.
- `docs/TEST_CUTOVER_ROLLBACK.md`: gates, test, acceptance, rollback.
- `docs/DECISIONS_AND_CONFLICTS.md`: các mâu thuẫn V1–V3 và quyết định V4.
- `docs/TASKS_FOR_CODEX.md`: task thực thi theo lô, sửa code và thử nghiệm riêng.
- `sql/reference/`: snapshot schema hiện tại và migrations 002–004 **không được chỉnh sửa**.
- `sql/proposals/`: `005`, `006` bản **DRAFT đã kiểm thử cấu trúc**, chưa là production migration.
- `tools/`: audit SQLite, inventory ngoài DB, staging copy, tự kiểm bundle.
- `scaffold/src/`: thư mục đích **rỗng**, KHÔNG thay cho 29 Python scripts trong repo.
- `workspaces/_template/`: file TXT trống chỉ cho nhập xuất hoặc trao đổi với LLM, **không** là persistence runtime.

## Chạy an toàn (Windows PowerShell, sau khi giải nén)

```powershell
# Chạy từ thư mục NOVEL2ANIMA_V4 được giải nén
python .\tools\validate_v4_bundle.py
python -m unittest discover -s tests -v

# Audit DB gốc: script chỉ đọc DB; báo cáo JSON được xuất ra nơi bạn chỉ định
python .\tools\audit_db_readonly.py --db D:\Novel2Anima\db\novel_anima.db --output .\db-audit-v4.json

# Inventory files ngoài DB: không sửa dữ liệu nguồn
python .\tools\inventory_external_readonly.py --root D:\Novel2Anima --output .\external-inventory-v4.json --sha256

# Staging: source chỉ đọc, target DB mới phải CHƯA TỒN TẠI
python .\tools\stage_migration_copy.py --source D:\Novel2Anima\db\novel_anima.db --target D:\Novel2Anima\db\novel_anima_v4_staging.db --report .\stage-v4.json
```

Đường dẫn ví dụ phải thay bằng đường dẫn thật. **KHÔNG chạy SQL `005/006` trực tiếp trên DB thật.** Script staging chỉ backfill một số quan hệ chắc chắn và xuất các trường hợp cần rà soát; nó **không** hoàn tất chuyển dữ liệu JSON/TXT/ảnh ngoài DB.

## Giới hạn kiểm chứng

ZIP gốc có 80 files/source, schema + thống kê DB snapshot (ước ~361 MB), **không có DB thực** hoặc toàn bộ `data/`, `prompts/`, `reviews/`, ảnh chưa track. Baseline trước đó: 75 unittest pass + 1 skip (trên source ZIP); SQL V3 9 tests trên in-memory SQLite. V4 bổ sung tests/công cụ bundle, nhưng chưa thể cam kết migration thực tế có parity cho đến khi chạy với DB và runtime data của người dùng.
