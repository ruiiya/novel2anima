# Novel2Anima — Git + SQL schema bundle

Bundle này gồm:

- Toàn bộ file **git-tracked** tại working tree hiện tại (bao gồm thay đổi WIP nếu có).
- `sql/current_schema.sql`: DDL hiện tại dump từ `db/novel_anima.db`, có chú thích mô tả bảng.
- `sql/current_columns.tsv`: danh sách cột của từng bảng.
- `sql/current_foreign_keys.tsv`: khóa ngoại của từng bảng.
- `sql/table_descriptions.md`: mô tả nội dung từng bảng.
- `sql/table_descriptions.tsv`: bản rút gọn để máy đọc.
- `sql/db_stats.json`: số dòng, thống kê dữ liệu derived/runtime, git commit/status.
- `MANIFEST.txt`: thông tin đóng gói.

Không có trong bundle: `.git/`, `db/novel_anima.db`, WAL/SHM, dữ liệu `data/` **không được track**,
`docs/`, `765/`, `act_tools/`, `db/backup/`, `__pycache__/`, `.pytest_cache/`.
Các file `data/` đang được git-track (ví dụ roster/wardrobe JSON) vẫn có trong bundle vì
chúng thuộc phần git.

Lưu ý: đây là **schema + source**, không phải bản dump dữ liệu DB.
