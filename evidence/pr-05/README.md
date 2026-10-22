# PR-05 - Story, wardrobe and continuity invariants

## Trạng thái

| Mục | Kết quả |
|---|---|
| Trạng thái | **HOÀN TẤT** |
| Branch | `rebuild/v4` |
| DB migration | Không thêm; dùng `005`–`007` đã có |
| Code | `storage/domain_repository.py` |
| Tests | `tests/test_pr05_invariants.py` — 6 pass |

## Invariant đã khóa

- `shot_participant` là nguồn duy nhất cho thành viên shot; cross-project bị trigger chặn.
- `shot_interaction` bắt buộc `actor_character_id`, `target_character_id`, `action_code`; không suy vai, không cho actor = target.
- Headpat male→female và female→male đều lưu riêng, không tự đảo.
- `character_identity_revision`, `outfit_revision`, `shot_spec_revision` approved là immutable.
- `outfit_item` lưu slot/cut/material/anchor; `shot_outfit_binding` pin revision theo `(shot_id,character_id)`.
- Đổi outfit tạo revision mới; shot cũ vẫn giữ revision cũ.
- `continuity_assertion` giữ lịch sử; `effective_continuity()` ưu tiên `user` hơn `inference`/`llm` mà không xóa claim cũ.

## Tests

```text
python -m unittest tests.test_pr05_invariants -v
Ran 6 tests
OK
```

## Giới hạn

- Chưa có UI/CLI riêng cho revision; writer API là `storage.domain_repository`.
- `qa_run`/`qa_issue` append-only được kiểm ở PR-07.
