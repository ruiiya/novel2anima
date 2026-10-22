# 11 LLM stages — interface contract và DB-first rule

## Hình thức chuẩn

`llm/prompts/01_brief` đến `11_targeted_revision` mỗi thư mục có `system.txt`, `task.txt`, `examples.txt` **rỗng 0 byte**; chỉ hỗ trợ người vận hành chủ động soạn thảo. Không load ba file đó như instruction thực khi chúng rỗng. Active template phải nằm ở DB `llm_prompt_template`, có `stage`, `revision`, `status`, `schema_version`, full body và dấu vết approval. Cần mở rộng DRAFT schema nếu thiếu trường cần thiết.

Mỗi lần gọi model tạo `llm_run`: `execution_key` chống trùng, input revision refs/hashes, model/provider, template ID, validated request JSON, response JSON, parse errors, duration/token/cost nếu có, validation status. LLM output chỉ là **proposal**; service thực hiện validation, ownership checks và commit revision mới. Không expose toàn bộ catalog 1.2M tags cho LLM; SQL retrieval trả top-k có evidence.

## Bước và invariant

| Stage | Quyết định LLM | Đầu ra chính | Guard |
|---|---|---|---|
| 01 brief | chuẩn hóa yêu cầu | brief revision | không mất yêu cầu đã chốt |
| 02 story | action-driven short story | story revision | 1–2 nhân vật mặc định |
| 03 character | mô tả nhận dạng, IDs | identity revision | explicit character code |
| 04 wardrobe | outfit anchor/items | outfit revision | cut/material/silhouette/details |
| 05 act beats | bố cục hành động | act/beat revision | một panel là một shot |
| 06 shot direction | ShotSpec, action direction | shot spec revision | actor/target explicit, current outfit pin |
| 07 catalog selection | chọn tag trong shortlist | tag IDs | only existing DB tags |
| 08 natural prompt | NL expression nếu cần | natural_prompt | tag + negative gốc bất biến |
| 09 semantic review | đánh giá logic + continuity | qa issues | không sửa approved content |
| 10 visual QC | so ảnh với outfit/shot | qa issues | image from DB or authenticated adapter |
| 11 targeted revision | đề nghị minimal fix | draft new revision | only revise identified axes |

## Input/Output protocol (proposal, V4 contracts)

- `schema_version`, `stage`, `project_id`, `act_id?`, `shot_id?`, `input_revision_refs` là phần envelope do application gán, LLM không tự đặt ID hay thay đổi refs.
- `result` luôn JSON object có `status=proposed|needs_review`, `decisions`, `uncertainties`, `evidence_refs`. Output validated against stage-specific schema; unknown IDs blocked.
- Directed action: `actor_character_id`, `target_character_id`, `action_code` phải là ID trong `shot_participant`; when solo non-directed action, `target_character_id` can be null if business contract allows, không tự đảo.
- Outfit: `outfit_revision_id` pin per `(shot_id,character_id)`; update outfit takes new approved revision, not mutable JSON/loose tags.
- Compiler handles deterministic tag sorting/dedupe/conflict resolution with DB provenance, LLM chỉ chọn/refine proposal from shortlist.
- For each stage with missing approved system/task/schema: status `BLOCKED_CONFIG` and no model invocation.

**Các JSON schema trong `llm/schemas` là DRAFT contracts** để test interface, chưa được dùng trực tiếp với runtime models và cần hoàn chỉnh theo payload thực tế khi P6.
