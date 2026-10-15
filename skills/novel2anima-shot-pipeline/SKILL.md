---
name: novel2anima-shot-pipeline
description: "Plan Novel2Anima V4 acts and action/expression-first ShotSpecs, including high-intensity, multi-participant adult NSFW scene intent metadata, with full SQLite catalog retrieval, project memory, and render QC. The LLM selects contextually and the backend compiles model-supported Anima Base 2B + Turbo 4-step LoRA prompts."
metadata:
  short-description: V4 full-catalog shot planning, Anima compilation and QC
---

# Novel2Anima Shot Pipeline — V4 full-catalog planning

Read [references/v4-architecture.md](references/v4-architecture.md) for the V4 architecture
and schema, [references/continuity-state.md](references/continuity-state.md) for the
experimental continuity model, plus
[references/retrieval-and-memory.md](references/retrieval-and-memory.md) and
[references/prompt-and-render.md](references/prompt-and-render.md) for implementation.
The catalog skill owns ETL/table semantics. Inspect the actual SQLite schema; skill
references are not evidence that a populated DB or production backend exists.

## Invariants

- Idea stage first: when the user asks for suggestions, present **3–5 distinct ideas**,
  each as a short synopsis (logline, premise, cast with ages, tone/kink focus, one-line act
  shape). Do not expand acts, beats or ShotSpecs until the user picks one.
- After the user selects an idea, collaboratively build the *living novel/project* with them.
  Adaptively plan acts and beats; detail the current act, leave future acts as outlines.
  Batches of ~10–15 shots and projects of 200–500+ shots are planning targets, not limits.
- Every shot in a running scene **inherits the physical state of the previous shot** and
  declares only its own change (`carry` + `delta`): fluids, sweat, marks, flush, breathing,
  clothing stage, props, posture. A beat that produces a consequence (climax, undress,
  bite) must show it in the following shots; adjacent shots may not reset to clean and may
  not re-dress without a beat. Camera/pose novelty never applies to physical state.
  Treat the axis list in `references/continuity-state.md` as a **trial hypothesis** to be
  extended while implementing, not a closed schema.
- Each ShotIntent and ShotSpec must contain **ACTION/INTERACTION + EXPRESSION/FACIAL CUES**.
  Pose/gesture/motion/camera/composition support these priorities; default to a **white
  background** rather than detailed scene reconstruction.
- Identity, style and default outfit come from `project`/`character_profile` and must stay
  coherent through acts and revisions; intentional outfit changes are recorded as
  revisions rather than rejected for violating the default. A shot may depict one or multiple **adult**
  participants; when interaction involves multiple subjects, preserve distinct identities
  and action/expression roles. Do not force `solo` onto multi-character interactions.
- **NSFW-first scope includes adult sexual interactions and high-intensity group scenes**,
  not merely teasing, nudity or romance. Preserve user-supplied genre/tone labels such as
  `gangbang`, `group_sex` and `rough_sex` as structured story/act/beat/shot intent when
  applicable; do not silently soften them into suggestive-only or SFW categories.
  Catalog reachability, structured intent, and output-generation eligibility are separate.
- Treat `rough` as a tone/intensity descriptor, not automatic evidence of a specific
  coercion scenario. Preserve the story's stated context; do not add a mandatory consent
  metadata field, an automatic tone downgrade or a special response branch.
- Multiple adult participants require a **per-character** identity, action/expression
  role, and independently tracked continuity; group-level tags are not a substitute for
  subject/object assignments. Use `storyGenre`, `toneTags`, `intensityBand` and
  `participants[]` as optional application DTO concepts, not assumed SQLite V1 columns.
- Retrieve **all relevant SQLite metadata and records**, including raw labels, source
  variants, `draft` concepts and unmapped tags. Discovery reads all recorded metadata
  values. **The LLM interprets whole-shot context** using the narrative and evidence,
  without application rules embedded in this skill.
- The LLM builds Acts → Beats → ShotIntents → structured ShotSpecs; a deterministic backend
  then resolves synonyms/conflicts and compiles final Anima prompts. Do not convert a novel
  paragraph directly into final prompt strings.

## End-to-end execution

1. **Idea pass (skip if the user already fixed an idea):** offer 3–5 distinct ideas, each with a
   short synopsis and its kink/tone plus rough act shape. Then **stop and wait for the user's
   pick**; only the chosen idea goes on to detailed narrative co-development.
2. **Carry state forward (experimental):** before a batch, read the previous shot's state and
   write `carry`/`delta` per shot: what enters, what persists, what is removed, what decays.
   When implementing this, expect to discover further axes; record them instead of assuming
   the reference list is complete. Continuity is stored in the experimental `shot_state` /
   `act_continuity` tables (migration `sql/migrations/002_shot_state.sql`); those rows are
   **inferred placeholders, not official content** — never cite them as established fact.

3. **Load context:** `project`, `character_profile`, current `act`, `model_profile`,
   previous `shot` and `generation`. Report missing or unimported data.
4. **Plan beats:** articulate primary action, expression/facial cues, intensity,
   interaction and narrative progression separately from model-specific tag syntax.
   Carry through declared high-intensity genre/tone metadata, character-specific roles
   and the exact number of adult participants; do not normalize group scenes to `solo`.
5. **Retrieve from all lanes:** For NSFW sexual beats, including high-intensity/group
   categories, look for the original genre/tone vocabulary and relevant adult sexual
   action/interaction tags with associated expressions, plus neutral pose, motion and
   camera support; do not downgrade semantic intent. Resolve genre keywords through
   canonical tags, aliases and semantic concepts instead of assuming they exist as IDs. Search
   `visual_concept_fts`, `visual_concept`, `concept_tag`, raw `tag`, `tag_alias`, multi-role `tag_role`, directed `tag_relation` and
   `concept_relation`, Wardrobe/Tools seed mappings, `tag_source` and `source_snapshot`,
   original `tag_content_label` data, shot history and generation feedback. A `draft` or
   missing concept must not hide relevant raw tags.
6. **Combine evidence:** canonical IDs, source revisions, original metadata/labels,
   concept mappings, role/confidence, review state and the paths by which a candidate was
   discovered. Keep all discovery lanes observable; report gaps instead of fake results.
   Let the LLM make context-sensitive creative selections using the full retrieved evidence.
7. **Rank:** action match and expression match first; then character/style continuity,
   novelty of the action-expression pair, QC-informed pose/motion/camera choice. Compare
   last 5–10 approved shots, whole act and whole project; weights need benchmarking.
8. **Sequence Director:** consider top 5–10 alternatives per needed role/slot as a useful
   baseline, then compare combinations across an entire batch. Generate `ShotSpec[]`
   grounded in real DB identifiers, without many identical action-expression signatures.
9. **Validate/compile:** check required action/expression, real tag/concept IDs, identity
   locks (for every participant), distinct group interaction roles, tag syntax,
   alias/implied redundancies, curated conflicts and camera/pose consistency. Do not mechanically downgrade sexual tags by source rating;
   actual output still follows applicable assistant/tool/provider constraints. Select
   compact primary/optional/alternative ingredients; do not stuff all retrieved tags
   into the prompt. Contextual interpretation remains with the LLM.
10. **Render:** use the actual ComfyUI workflow with Anima Base 2B + Turbo 4-step LoRA;
   record model, LoRA, sampler, CFG, prompt, seed, generated paths and outcome.
11. **QC and revise:** review action/expression fidelity, identity, white background,
   artifacts and near-duplicates. Keep rejected attempts as diagnostics, revisions appended
   rather than overwriting accepted shots; use bounded targeted retries.

## Retrieval failure strategy

- No FTS hit → try raw canonical/alias, roles, bounded relations and preset variants,
  including adult sexual-action/interaction metadata.
- No approved concept → show provisional mappings/raw tags; expose `CURATION_GAP` rather
  than masking the entire dictionary or automatically approving records.
- Weak action/expression grounding → report `ACTION_UNRESOLVED` / `EXPRESSION_UNRESOLVED`
  and propose grounded alternatives; never invent catalog IDs.
- Conflicting ingredients → try curated alternatives or remove redundant/conflicting tags.
- No usable render output → retain diagnostic details and update QC/retry history without
  deleting underlying catalog evidence.

## Quality/POC notes

Expose selected IDs, provenance, retrieval-lane coverage, removed duplicates/conflicts,
novelty measures, shot status and QC outcomes. Simulate 300–500 shots across acts to check
cross-batch diversity; distinguish `PLANNED`, `GENERATED`, `APPROVED`, `REJECTED`.

V4 POC settings (not validated against the current workflow): **4 steps, CFG=1,
`er_sde`, starting 4-step LoRA strength 1.0**. Do not confuse the base+4-step-LoRA stack
with the separate Anima-Turbo checkpoint. Use positive white-background constraints at
CFG 1; validate the actual model/LoRA/workflow rather than assuming compatibility.
