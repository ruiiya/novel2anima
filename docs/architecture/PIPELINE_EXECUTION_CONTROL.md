# V4.1 — Pipeline Orchestration & Execution Control (PR-10)

**Trạng thái:** đã triển khai PR-10 trên `src/novel2anima/pipeline/`, `llm/stage_executor.py`, `storage/pipeline_repository.py` và migration `sql/migrations/013_execution_control.sql` (bản đã review, thay cho DRAFT 007 vì repo thực đã dùng 007..012). **Tiền đề:** PR-00..PR-09 hoàn thành. Chỉ chạy production khi `runtime_mode=V4_ACTIVE` và `strict_execution_control=on`; mặc định migration để `LEGACY/off` cho pilot an toàn.

## A. Hai loại công việc không được trộn

1. `CATALOG_MAINTENANCE`: fetch/import/prune/FTS rebuild/migrate/bulk data cleanup; chỉ `catalog_job` theo lệnh người vận hành hoặc lịch bảo trì riêng, có phạm vi và quyền hạn rõ. **Không bao giờ là stage con của `story.start`.**
2. `STORY_RUN`: xử lý brief → story → characters/outfit → acts/shots → retrieval → prompt → QA → render theo workflow version đã đăng ký. Có thể gồm nhiều bước LLM/Python nhưng chỉ có một `pipeline_run` logic cho một yêu cầu start; các lần retry là `pipeline_step_run` attempts, không tự tạo workflow mới.

Danh sách những CLI được xếp vào catalog/admin (cấm gọi khi start story): `etl/build.py`, `etl/import_tags.py`, `etl/import_wiki_pages.py`, `etl/import_colour_sets.py`, `etl/prune_tags.py`, `etl/cleanup_db.py` và mọi script rebuild/import/migrate tương đương. `etl/seed_plan.py`, `etl/plan_actions.py`, `etl/llm_review.py`, `etl/qa_shots.py` trước V4 chỉ là CLI tương thích; khi đã cutover, entrypoint phải gọi service/stage tương ứng, **không shell-out để tự tạo pipeline khác**.

## B. Chủ sở hữu quyền quyết định

- **User:** khởi tạo project/story, duyệt brief/identity/outfit/shot được yêu cầu; yêu cầu rerun hoặc chỉnh nội dung.
- **Application orchestrator:** chọn workflow đã đăng ký; xác định steps/dependencies; kiểm tra template và revision; scheduling, retries, idempotency, DB transaction, error status.
- **LLM stage:** chỉ nhận payload stage và đề xuất output JSON theo schema; không tạo/ghi script, không điều hành CLI, không truy cập SQLite trực tiếp, không thêm step, không quyết định chạy catalog ETL.
- **Deterministic service:** retrieval/compile/validation/provenance, đọc và ghi DB theo repository API.
- **Catalog admin:** thao tác ETL qua chức năng tách riêng được cấp quyền; mọi rebuild kiểm soát và ghi import job ledger.

## C. API/contract đích cần hiện thực ở PR-10

> Tên module và function dưới đây là **đích thiết kế**, chưa có trong source ZIP cũ.

`src/novel2anima/pipeline/{registry,orchestrator,policies,step_runner,dependency_graph}.py`

- `start_story(project_id, input_revision_id, client_run_key, workflow_version) -> run_id`.
- `resume_run(run_id)` sau khi được giải quyết BLOCKED_CONFIG/NEEDS_REVIEW; không tự vượt approval.
- `rerun_from(run_id, step_code, reason, request_key)` tạo run/revision mới có provenance; `reason` bắt buộc.
- `catalog_update(...)` **không** thuộc `start_story`, nằm ở namespace admin với quyền riêng.

Workflow definition lưu trong source/registry có version và allowlist. SQLite lưu version/hash và các lần chạy để audit, **không** cho LLM tự cung cấp một DAG/CLI thực thi.

## D. 11 stage LLM và các bước Python nằm chung DAG đã đăng ký

```text
start_story
  01_brief [LLM] -> 02_story [LLM] -> 03_character [LLM]
  -> 04_wardrobe [LLM] -> 05_act_beats [LLM] -> 06_shot_direction [LLM]
  -> retrieve_catalog [PY] -> 07_catalog_selection [LLM, conditional]
  -> compile_prompt [PY] -> 08_natural_prompt [LLM, OPTIONAL]
  -> 09_semantic_review [LLM + deterministic checks]
  -> render [adapter, optional/authorized] -> 10_visual_qc [LLM, requires image]
  -> 11_targeted_revision [LLM, conditional; creates draft only]
```

- Đúng **một shot trên một panel**; solo và duo là đường chạy bình thường.
- Trước mỗi LLM stage: require approved system/task/template/schema, identity, outfit and actor→target binding; thiếu → `BLOCKED_CONFIG`/`NEEDS_REVIEW`, **không gửi request đến provider**.
- `07`, `08`, `10`, `11` được skip hợp lệ tùy điều kiện; một `SKIPPED_CONDITION` khác hoàn toàn `SUCCEEDED`. QC ảnh không chạy khi chưa có image asset.
- Stage LLM **không được** sinh ra bước ETL mới kể cả khi missing tag, wardrobe rule hoặc source mapping: trả `CURATION_GAP`/`BLOCKED_DEPENDENCY`, tạo đề xuất bảo trì ngoài story.

## E. Trạng thái và lịch sử

- `pipeline_run`: `QUEUED`, `RUNNING`, `WAITING_APPROVAL`, `BLOCKED_CONFIG`, `BLOCKED_DEPENDENCY`, `FAILED`, `COMPLETED`, `CANCELLED`; cần mapping với enum 005 trước khi áp dụng SQL.
- `pipeline_step_run`: `QUEUED`, `RUNNING`, `SUCCEEDED`, `FAILED`, `BLOCKED_CONFIG`, `BLOCKED_DEPENDENCY`, `NEEDS_REVIEW`, `SKIPPED_CONDITION`, `CANCELLED`. Một stage có nhiều attempt, lưu `attempt_no`, `input_fingerprint`, `output_revision_refs`, `retry_of_step_run_id`, `error_code`, timestamps; không xóa lịch sử cũ.
- Một logical run có `run_key` duy nhất trong 005. Trùng **cùng key và cùng payload hash** phải trả về run cũ; cùng key nhưng payload khác → `IDEMPOTENCY_CONFLICT`. Không tự dùng hash nội dung story làm key duy nhất giữa các yêu cầu độc lập.
- `pipeline_step_run` được triển khai trong `sql/migrations/013_execution_control.sql`. Bản DRAFT 007 chỉ là tham chiếu; không áp dụng trực tiếp. Migration đã rebuild bảng cũ, giữ FK/index/trigger và chạy qua checksum runner trên DB copy trước.
- Transaction ghi output hợp lệ + status thành công phải atomic. Không đánh dấu completed trước khi commit. Timeout/retry dùng backoff giới hạn, không lặp vô hạn; manual side effects/render có idempotency key riêng và checkpoint.

## F. Dependency-aware rerun

- Fingerprint bước = `workflow_version` + `step_code` + `input_revision_ids/hashes` + `approved_template_version` + `model/config version` + `policy/version` (nếu liên quan). Không dùng file timestamp.
- Input không đổi: có thể **reuse deterministic** `retrieve_catalog`, `compile_prompt`, validation; kiểm tra output còn tồn tại và đúng revision.
- LLM outputs **không mặc định tái dùng** nếu người dùng yêu cầu viết lại; chỉ reuse khi chính sách step cho phép và key/revision trùng rõ ràng.
- Nếu outfit của nhân vật X đổi → invalidates shot specs/prompt/QC có binding đến outfit đó; duy trì các shot không liên quan. Nếu sửa action của shot S → invalidate ShotSpec/prompt/QA/render của S và continuity của hậu duệ phụ thuộc, không tự chạy lại catalog ETL hay các story khác.
- Mọi rerun phải tạo revision/provenance mới hoặc trỏ về kết quả immutable thực sự tương đương; approved history không được overwrite.

## G. Deny-by-default execution guard

1. LLM provider được gọi qua một `LLMStageExecutor` cố định: không có quyền OS shell, write SQL, filesystem mutations hoặc arbitrary tool registry.
2. Dispatcher chỉ nhận `step_code` nằm trong registry whitelist; không nhận Python code/command/path từ model output. Không thực thi `subprocess`, `os.system`, `eval`, `exec` hoặc import code do LLM sinh ra trong story path.
3. Không dùng prompt instruction làm rào chắn duy nhất: phải có boundary ở service/API, ACL, validation, DB permissions khi triển khai.
4. Bảo trì catalog tách endpoint/job scheduler, khác permission và không được phép bị gọi bởi identity của story workflow.
5. Runtime mode `LEGACY` / `MIGRATING` / `V4_ACTIVE`: chỉ advertise capabilities có thật. `LEGACY` dùng các CLI được hỗ trợ **theo hướng dẫn có kiểm soát**, không tuyên bố đã có orchestrator. `MIGRATING`: chặn câu lệnh dễ gây double-write, gọi API tương thích có kiểm soát. `V4_ACTIVE`: bắt buộc đi qua registry.

## H. PR-10 acceptance và những test **phải chạy trên code triển khai thật**

- `start_story` từ cùng request key không tạo >1 logical run, không tạo script hoặc `catalog_job`.
- Với một story gồm 10 shot, chỉ có một root `pipeline_run`, các step runs/attempts đầy đủ; không có `subprocess` do model quyết định.
- Mock LLM trả `"command":"python etl/build.py"` / `"create_etl": true`: rejected by schema/service; file/process không thay đổi.
- Thiếu approved stage prompt/template/schema → `BLOCKED_CONFIG` và provider mock có **0 calls**.
- Hai lần retry mất kết nối sau DB commit: một output revision, log attempts chính xác.
- `male headpat female` giữ nguyên actor→target; outfit revision không trôi giữa nhiều shot.
- Rerun shot đơn lẻ không rebuild tag/FTS/catalog; có test negative cho command allowlist và unauthorized catalog job.
- `pipeline_step_run` FK/index, terminal status consistency, cancellation, blocked/skip/review được kiểm thử trên SQLite copy.
- E2E story ở chế độ DB-only, không cần plan/prompt/review JSON files ngoài. Tests hồi quy 75 baseline, migration parity và post-PR09 release test phải chạy lại.

## I. Rollback

Flag `strict_execution_control` (bảng `runtime_setting`) có thể tắt dispatcher mới trong pilot **và dùng lại snapshot code+DB phù hợp**, không được quay về LLM tự do tạo code trong sản xuất. Backup trước migration 013; DB copy; rollback qua app version và DB snapshot tương ứng, không xóa lịch sử mới. Nếu không có snapshot tương thích → giữ trạng thái BLOCKED và xử lý thủ công có ghi nhận, không force bypass.
