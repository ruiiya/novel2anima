# Novel2Moss — Mapping DB ↔ Skill (Natural Prompt)

| Skill | Đọc DB | Ghi DB / Bàn giao |
|---|---|---|
| `database` | Migration, schema, các bảng | init, transaction, integrity |
| `catalog-ingest` | Source registry, tag/outfit/character | Upsert catalog có provenance; không ghi render |
| `story-planner` | Story/source/roles/plans | save-plan, add-act, add-beat, add-event |
| `blind-cast` | story_roles, casting | bind-role sau khi chọn nhân vật |
| `character-profile` | characters, traits, outfits, captions | trả identity/outfit đã xác minh |
| `shot-spec` | Story/Event/roles/vocab | save-shot, shot_participants/interactions |
| `continuity` | snapshots trước và hiện tại | save-continuity |
| **`natural-language-prompt`** | ShotSpec/roles/casting/continuity/catalog | **save-natural-prompt → `shot_prompts`** |
| `fidelity-qa` | source→ShotSpec→`shot_prompts` | save-qa `PROMPT` (hoặc `STORY/SHOT`) |
| `orchestrator` | toàn pipeline | export-bundle, export-story-prompts |
| `render-adapter` | **không đọc DB** | chỉ đọc `natural.prompt.txt` hoặc `prompt` string trong JSONL |

## Quản lý revision

- Story revisions và casting revisions độc lập với Shot revisions.
- Prompt revision tăng khi sửa văn bản cho cùng `shot_id`; sửa Shot tạo `shot_id` mới, không ghi đè.
- Export cả Story chọn **Shot revision mới nhất** cho mỗi `(beat_id, shot_key)`, rồi lấy natural prompt revision mới nhất của Shot đó; nếu thiếu, báo lỗi trước khi xuất.
- Mỗi bundle có prompt hash/shot ID/revision để đối chiếu. Bảng Layout cũ chỉ giữ lịch sử, không được dùng làm prompt canonical.
