# Novel2Anima V4 — Architecture and SQLite data inventory

This is a **technical extract** of the user's V4 compact-context handoff. It includes
architecture, schema intent and performance hypotheses, not the source document's
operational prescriptive passages. The original user-provided document is NOT bundled
with these runtime skills to prevent duplicate, outdated instructions taking precedence.

## Product and workflow

- Idea → living novel/project → adaptive acts → beats → ShotIntent → retrieved
  candidates → LLM Sequence Director → structured ShotSpec → deterministic Anima
  prompt compiler → ComfyUI → QC/revision/approval → project/act memory.
- Detail the current act and outline future acts. 200–500+ shots per project and
  ~10–15 per batch are POC targets, not hard constraints.
- Visual priority: **ACTION/INTERACTION + EXPRESSION/FACIAL CUES**. Secondary support:
  pose/gesture, motion, framing/camera. Default setting: isolated character on white.
- Preserve character identity, project style, and normally outfit across shots.
  Novelty is judged over recent shots, current act, and full project history.
- Model target: Anima Base 2B plus separate Turbo 4-Step LoRA via ComfyUI. Test settings
  before relying on them: 4 steps, CFG 1, er_sde and LoRA strength ~1.0.

## SQLite V1 (16 tables + 1 FTS5 virtual table)

- Raw dictionary: `source_snapshot`, `tag`, `tag_source`, `tag_alias`, `tag_role`,
  `tag_relation`, `tag_content_label`.
- Curated visual library: `visual_concept`, `concept_tag`, `concept_relation`,
  `visual_concept_fts`.
- Runtime: `model_profile`, `project`, `character_profile`, `act`, `shot`,
  `generation`.
- **Tag** is canonical model syntax; **Visual Concept** is an action/expression/etc.
  unit used by the LLM. Map tags via primary/optional/alternative, not all synonyms.
- `visual_concept_fts` indexes concept text, **not** every raw tag. Complement concept
  retrieval with canonical tag, alias, role and relation paths.
- Directed `IMPLIES` comes from source edges; `COMPATIBLE`, `RECOMMENDS`, and
  `CONFLICTS_WITH` are separate curated mappings only if present in the DB.
- Content-like source metadata fields and editorial statuses are stored DB facts;
  their field names and native scales remain unchanged. NSFW-first includes
  sexual-action/interaction vocabulary, not only suggestiveness. Keep these records
  discoverable alongside SFW material; source labels do not establish model permissions.
- SQLite MVP uses FTS5/B-tree/JSON, with migrations, integrity checks and WAL.
  Do not silently replace it with PostgreSQL, vector DB or a graph database.

## Source datasets (five families)

1. `Mexes/danbooru-tag-taxonomy` — raw taxonomy, names, roles, counts, aliases.
2. `ShiroEirin/comfyui-good-anima` — model tag spelling/index evidence.
3. `lingdongbudong/Comfyui-Anima-Wardrobe` — wardrobe, expression/pose presets and rules.
4. `nregret/Comfyui-Anima-Tools` — pose/action groups and tag variants.
5. `grio43/danbooru-implication-map` — canonical aliases, directed implications.

Record revision/commit, SHA256, provenance, original fields and source permissions.
Imports must be idempotent. Images belong on disk; SQLite stores references and QC.

## Evidence and anti-repeat

- `primary_signature=(action, expression, intensity_band)` and
  `secondary_signature=(pose, motion, camera, direction)` are proposed features.
- Compare last 5–10 accepted shots, all current-act shots, and project-wide history;
  keep planned/rejected/generated/approved distinctions.
- Do not invent catalog IDs, observed datasets, measured recall or measured rendering
  performance. This documentation cannot prove the actual backend or SQLite is populated.
