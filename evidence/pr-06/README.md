# PR-06 - LLM contracts and prompt registry

## Trạng thái

| Mục | Kết quả |
|---|---|
| Trạng thái | **HOÀN TẤT** |
| Branch | `rebuild/v4` |
| Migration | `009_llm_registry.sql` |
| Schema | 11 file `llm/schemas/*.schema.json` |
| Runtime | `llm/contracts.py`, `llm/registry.py` |
| Tests | 6 test method, phủ 11 stage; full suite 119 pass, 1 skip |

## Contract

Mỗi output có envelope bắt buộc:

```json
{
  "schema_version": "v4-1",
  "stage": "06_shot_direction",
  "status": "proposed",
  "decisions": {},
  "uncertainties": [],
  "evidence_refs": []
}
```

`stage` là `const` trong schema, nên output của stage này không thể được nhận bởi stage khác. Validator chỉ dùng subset JSON Schema cần thiết, không thêm dependency.

## Approval gate

- `create_draft()` chỉ tạo `status=draft`; không thể invoke.
- `approve()` là thao tác duy nhất chuyển sang `active`; từ chối `system_text`/`task_text` rỗng hoặc output schema rỗng.
- Khi approve template mới, template active cũ của cùng stage bị `retired`.
- `active_template()` trả `None` nếu chưa approve; `invoke_stage()` raise `StageBlocked`.
- `llm_prompt_template_event` ghi mọi insert và mọi thay đổi `status`; event là immutable.

## Audit và retry

- `llm_run.execution_key` là duy nhất; retry cùng key trả run cũ, không gọi executor lần hai.
- Output hợp lệ mới được ghi `output_json`; output sai ghi `status=invalid`, lỗi trong `validation_json`, `output_json` giữ NULL.
- Executor lỗi ghi `status=failed` và `error_text`, không ghi canonical result.
- Không có write domain nào từ LLM; `invoke_stage()` chỉ ghi `llm_run`.

## Migration staging

- DB: `db/backup/pr-01/staging_live.db`
- Backup: `db/backup/pr-06/pre_009_staging_backup.db`
- Backup SHA-256: `33b499bc827182009478c0b5ce2dac0394031109c1a748546027c89dff31002b`
- `009_llm_registry`: `0aa57238dd3a9e95e4af0ea3f4f58b4927d9e64601542bcfe80e0eb3394ed74e`
- `pending=[]`, `integrity_check=ok`, `quick_check=ok`
- Project/template/event counts: `0 / 0 / 0`

## Tests

```text
python -m unittest tests.test_pr06_llm_contracts -v
Ran 6 tests
OK

python -m unittest discover -s tests -q
Ran 119 tests
OK (skipped=1)
```

## Giới hạn

- Chưa seed nội dung prompt; 33 placeholder vẫn zero-byte và DB là nguồn duy nhất sau khi con người approve.
- Chưa gọi provider thật; adapter provider thuộc PR-07.
- `qa_run`/render invariants thuộc PR-07.
