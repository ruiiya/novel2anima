# V4 Shot Retrieval, Novelty and Feedback Contract

Read the sibling catalog skill's `references/full-coverage.md` first for all 16 tables +
FTS5. This reference translates that coverage into planning and candidate decisions.

## A. Request and output boundaries

Given project, act, beat, character ID(s), action/interaction intent (including
adult consensual sexual interaction when applicable), expression/facial cue, energy,
the project's existing metadata, selected model profile, recent+act+project history,
produce a **grounded** and testable shortlist and structured ShotSpec; not final tags
invented from prose. Work on ~10–15 shots in one sequence pass; batch size is configurable.

Use catalog discovery broadly; narrow only at subsequent decision stages. Access all
relevant SQLite domains in the actual pipeline: source provenance; raw tag and alias; role;
tag/concept edges; concept FTS and mapping; content labels; model profile; project/character/
act continuity; shot signatures; generation outcomes. Missing domains are explicit gaps.

## B. Stage graph, with measurable output

```text
Idea + current Act + Character (project/character_profile/act)
  → Beat/ShotIntent (mandatory action AND expression)
  → FTS concepts || raw canonical || aliases || multi-role || graph expansion || presets
  → Unified candidate evidence + source_snapshot/tag_source/tag_content_label
  → LLM contextual selection using full retrieved evidence
  → Rank action/expression/novelty + QC-informed support choices
  → Sequence Director: cross-batch variation, identity/style/outfit locks
  → ShotSpec w/ tag/concept IDs, provenance, alternates, explanation and flags
  → Validator → deterministic tag compiler
  → ComfyUI → generation+QC+review → feedback and revised history
```

Original catalog fields and editorial states travel with each candidate. The LLM
performs contextual interpretation using the user's narrative and the retrieval evidence.

## C. Role-specific retrieval and selection

1. Action/interaction: require a clearly visualizable primary action, with optional
   interaction target. An adult sexual action/interaction is still an action/interaction
   candidate, not automatically a clothing/pose item. Preserve participant roles without
   overwriting character identity. Search both concepts and raw `tag_role` action/interaction entries.
2. Expression: require primary expression + intensity + facial cues. Search both concepts
   and raw expression-role tags. Do not infer a missing expression from a camera tag.
3. Identity/outfit/style: validate canonical project and character constraints, not fresh
   hallucinated tags; note deliberate outfit changes as explicit versioned user decisions.
   Default outfit continuity is a preference, not an unconditional rejection of an
   intentional change in an adult scene.
4. Pose/gesture/motion: add only if they clarify the primary action or increase novelty.
   An imported Wardrobe pose may become a concept seed but is not independently approved.
5. Camera/composition/background: white background by default, add framing as support;
   avoid contradictory view/framing tags and excessive environmental details.
6. Normalization/relations: collapse aliases to canonical, prevent duplicate implied tags,
   apply only curated conflicts/compatibility, and respect directionality. Source popularity
   alone does not prove tag works on Anima 4-step.

Candidate discovery should never enforce `approved` for *all lanes*: when the visual
concept layer is all drafts, fall back to raw tags and surface review gaps. If action
or expression remains ungrounded, mark
`ACTION_UNRESOLVED` / `EXPRESSION_UNRESOLVED`, and do not invent DB-backed IDs.

## D. Proposed scoring logic (not benchmarked)

Use lexicographic priorities or transparent weighted components, validating visual and
identity constraints **before final compilation**:

- Action relevance + expression/facial match dominate, including adult sexual-action
  semantics when present in the planned shot.
- Character/style and narrative transition consistency next.
- Primary-pair novelty across recent, act and project; do not penalize a necessary action
  repetition as severely if expression/intensity and motion meaningfully change.
- Pose/motion/camera support and image-model QC evidence next.
- Provenance/curation confidence used to represent uncertainty and review load, not as
  arbitrary suppression of metadata classes or all draft tags.

Any example weights are tuning hypotheses until evaluated against rendered images. Expose
score reasons and selected alternatives; do not claim a score represents true model skill.

## E. Cross-scale repetition memory

- `primary_signature = (action_concept_or_tag, expression_concept_or_tag, intensity_band)`.
- `secondary_signature = (pose, motion, camera, direction)`.
- Compare **last 5–10 accepted** shots, current act and all approved project shots.
- Track `PLANNED` for collision avoidance within an unfinished batch separately; do not
  count `REJECTED` in the accepted denominator. Preserve all attempts diagnostically.
- Sequence Director may make a deliberate repeat with reason; avoid dozens of shots whose
  only changes are camera angle or arm position but identical action/expression meaning.
- pHash alone is not semantic pose similarity; optional embeddings are a later enhancement
  (do not add pgvector or external vector DB to V4 MVP).

## F. Render feedback loop

For each generation store: shot revision, selected prompt + canonical tag references if the
schema supports them, actual seed, checkpoint, Turbo LoRA, sampler, steps, CFG, workflow,
file path/hash, original project metadata, QC measures, reviewer decision, failure
codes and retry lineage. Use `generation` and `model_profile` to learn which action/expression/motion
combinations actually worked **on this model profile**, without assuming post_count is
render quality. If the V1 schema has nowhere to store specific fields, write a migration
gap, do not silently lose feedback or invent columns.

Example QC failures: `IDENTITY_DRIFT`, `ACTION_NOT_READABLE`,
`EXPRESSION_MISMATCH`, `BACKGROUND_NOT_WHITE`, `ARTIFACT`, `NEAR_DUPLICATE`,
`WORKFLOW_UNSUPPORTED`. Target a retry to the named failure, cap retries, save every
attempt, and only add human-approved results to accepted-history statistics.

## G. Minimum candidate payload (application DTO, NOT an existing DB schema)

```json
{
  "shotIntent": {
    "action": "turn suddenly",
    "expression": "surprise",
    "intensity": 0.8
  },
  "candidatesByRole": {
    "action": [{"conceptCode":"ACTION_SUDDEN_TURN", "canonicalTagId":123,
                "provisional":true, "evidenceLanes":["fts", "role", "alias"]}],
    "expression": [{"conceptCode":"EXPR_SURPRISED", "canonicalTagId":456,
                     "provisional":true, "evidenceLanes":["fts", "role"]}]
  },
  "retrievalCoverage": {
    "conceptFTS": "consulted", "rawTag": "consulted",
    "aliases": "consulted", "relations": "consulted",
    "sourceProvenance": "consulted", "history": "empty",
    "generationFeedback": "empty"
  },
  "curationState": "provisional",
  "notes": ["concept has not been editorially reviewed"]
}
```

IDs/scores above are **illustrative placeholders**. No actual SQLite or retrieval service
was exercised by the skill documentation alone.

## H. Per-batch acceptance checklist

- Every shot has grounded primary action and grounded expression/facial cue.
- Actions/expressions come from discoverable concept/tag data, or are explicitly
  labeled `CURATION_GAP`; no fabrication of catalog IDs.
- Alias/source roles/relations were consulted where relevant, and effective coverage
  across lanes is logged, including provisional and raw-only candidates.
- Real project/character/act records determine identity/style continuity.
- Shortlist preserves original source labels, review state, provenance and evidence,
  including adult sexual concepts rather than a euphemistic-only substitute.
- Selected tag set has no duplicate aliases, implied redundancy or curated conflicts.
- Batch, act and project diversity inspected separately; planned and approved not mixed.
- Approved and rejected generations recorded separately; QC feedback used only if present.
- Report unknown source mappings, not-yet-imported DBs and schema/version gaps explicitly.
