# Novel2Anima — Mapping DB ↔ Skill (Natural Prompt)

| Skill | Đọc DB | Ghi DB / Bàn giao |
|---|---|---|
| `database` | Migration, schema, các bảng | init, transaction, integrity |
| `catalog-ingest` | Source registry, tag/outfit/character | Upsert catalog có provenance; không ghi render |
| `story-planner` | Story/source/roles/plans | save-plan, add-act, add-beat, add-event |
| `blind-cast` | story_roles, casting | bind-role sau khi chọn nhân vật |
| `character-profile` | characters, traits, outfits, captions | trả identity/outfit đã xác minh |
| `storyboard-planner` | Story revision/Event/Role/Casting, Visual Bible | save-storyboard → storyboards/slots/locations/props/styles/coverage/dependencies |
| `shot-spec` | Story/Event/roles/vocab | save-shot, shot_participants/interactions |
| `continuity` | snapshots + shot_dependencies đúng nhánh | save-continuity |
| **`anima-prompt`** | ShotSpec/roles/casting/continuity/catalog | **save-natural-prompt → `shot_prompts`** |
| `fidelity-qa` | source→ShotSpec→`shot_prompts`, event_shot_mappings, sequence | save-qa `PROMPT` (hoặc `STORY/SHOT`), sequence QA evidence |
| `orchestrator` | toàn pipeline, storyboard_seals | seal-storyboard, export-bundle, export-story-prompts |
| `render-adapter` | **không đọc DB** | chỉ đọc `natural.prompt.txt` hoặc `prompt` string trong JSONL |

## Quản lý revision

- Story revisions và casting revisions độc lập với Shot revisions.
- Prompt revision tăng khi sửa văn bản cho cùng `shot_id`; sửa Shot tạo `shot_id` mới, không ghi đè.
- V4 export cả Story theo seal của storyboard hiện hành, thứ tự số, exact Shot/Prompt/QA ID. Không tự thay thế bằng revision gần nhất. Legacy Story chưa có storyboard giữ quy tắc V3.
- Mỗi bundle có prompt hash/shot ID/revision để đối chiếu. Bảng Layout cũ chỉ giữ lịch sử, không được dùng làm prompt canonical.
