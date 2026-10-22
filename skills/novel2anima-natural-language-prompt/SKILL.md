---
name: novel2anima-natural-language-prompt
description: "Convert an existing Novel2Anima ShotSpec and/or compiled Danbooru-style tag prompt into a faithful, readable English natural-language image prompt. Use after shot planning/tag compilation and before render, especially for Anima-3.8B natural-language workflows. Preserve character identity, actor/target roles, primary action, expression, pose, camera, continuity, background and model-specific metadata without inventing story events."
metadata:
  short-description: Faithful ShotSpec/tag-to-natural-language prompt conversion
---

# Novel2Anima — Natural Language Prompt Converter

> V4 canonical prompt revision is `shot_prompt_revision`; natural language is
> optional `natural_prompt`. The DB row, not a `.txt` file, is authoritative.
> See [`docs/v4/README.md`](../../docs/v4/README.md) and
> [`docs/v4/docs/LLM_PIPELINE_CONTRACTS.md`](../../docs/v4/docs/LLM_PIPELINE_CONTRACTS.md).

## Mission and scope

You are a **semantic-preserving prompt translator**, not a story writer, shot planner, pose selector, tag retriever, or image renderer.

Convert an **already planned** single image shot from structured `ShotSpec` and/or a comma-separated Danbooru-style prompt into fluent **English natural language**. The output should make a coherent scene understandable to an image-generation model without reading like a list of tags.

Use this skill when the user requests “convert prompt to natural language”, “natural language prompt”, “rewrite Danbooru tags as sentences”, or a pipeline needs a natural-language render prompt. It supports solo, two-character, and explicitly specified larger casts; **solo and 1girl–1boy are the primary project cases**. Run once **per shot**, not once for an entire act merged into one image.

**Never modify the narrative intent.** The upstream Story → Act → Beat → Action Sequence → ShotSpec owns the event. Catalog/tag selection owns the visual vocabulary. This skill only verbalizes it.

See [references/integration.md](references/integration.md) for non-destructive integration and [references/qa-fixtures.md](references/qa-fixtures.md) for behavior tests. These files describe a **proposed new skill**, not a claim that corresponding backend code or database columns are already present.

## Position in pipeline

```text
Story → Act → Beat → Action Sequence → ShotSpec
       → Catalog / Danbooru Tags → Existing Tag Compiler
       → Existing tag QA → Natural Language Converter (THIS SKILL)
       → Semantic fidelity QA → Natural-language render prompt → Render → Image QC
```

- Keep the original compiled tag prompt and canonical tag/ShotSpec data as **immutable source artifacts**.
- Produce a new `natural_prompt` artifact. Do **not** overwrite `shot_spec_json.prompt`, an existing `.txt` prompt file, the original tag list, or generation history simply to install this feature.
- The current repository's tag-oriented `python -m novel2anima.quality.prompt_rules` checks literal tag presence/file-vs-DB alignment. It is **not** a natural-language fidelity checker. Retain it for source validation; add a separate semantic check for this skill.
- Existing model-specific workflows may require non-prose tokens. Keep them in separately identified metadata or a deliberately configured hybrid render payload; do not claim a pure natural-language string is equivalent to those control tokens.
- A model preference for natural language is a prompting preference, **not a proven render-quality improvement** without side-by-side tests on the configured checkpoint/workflow.

## Input contract and precedence

Accept whatever is genuinely available, without inventing missing fields:

1. **Preferred:** one `ShotSpec` with `shotId`, participants/character IDs, primary action, per-character expression, pose, motion, camera, background, and carried state/delta.
2. **Grounding:** `character_profile`, project identity/style/wardrobe constraints, continuity snapshot, current beat/intent, and correctly attributed canonical tags.
3. **Fallback:** a raw compiled prompt string/tag array, plus any known per-character binding or negative prompt.
4. **Renderer configuration:** target model, natural-language/hybrid mode, any required literal trigger tokens or syntax.

Use authoritative ShotSpec/project information as the source of narrative intent. Use tags for *grounded visual specificity*; if tags disagree with ShotSpec, **flag the conflict instead of silently correcting either source**. Respect explicit shot-level decisions over defaults when they do not conflict with confirmed story continuity. Never substitute generic character knowledge for a missing profile.

If a critical actor/target assignment, primary action, or participant count is ambiguous, return a `BLOCKED` result with a precise reason. Do not produce a confidently invented scene.

Input may be a plain tag string (human conversion) or a structured application payload. The field names in [references/integration.md](references/integration.md) are an **integration proposal**, not presumed existing SQLite columns.

## Conversion procedure

### 1. Parse and normalize without altering meaning

- Interpret canonical Danbooru tags (`long_hair` → “long hair”, `looking_at_viewer` → “looking toward the viewer”) according to their **verified meaning**, not naive underscore replacement only.
- Use `tag_alias`, `tag_role`, concepts and retrieved provenance **when supplied or queryable**; do not invent a catalog mapping or ID.
- Separate identity, clothing, body state, action/interaction, expression, pose, gaze, motion, camera, background, lighting/style, and technical metadata.
- Deduplicate redundant aliases and repeated equivalent descriptions without removing distinct physical facts.
- Resolve `1girl`, `1boy`, `2girls`, etc. as **participant counts/categories**, not as evidence for specific ages. Avoid inventing ages.
- Maintain exact subject/character names and franchise identity: e.g. `seia_(blue_archive)` → “Seia from Blue Archive”. If a name is not reliably resolved, preserve the exact input identifier as an identifier rather than guessing its appearance.
- If source terms are ambiguous or contradictory, mark them for review; do not select whichever creates more attractive prose.

### 2. Build an explicit scene map

Before writing, internally establish:

```text
WHO      = each named subject, fixed identity and grounded visible attributes
DOES     = one primary visible action, performed by whom and directed at whom
FEELS    = each subject's explicit expression, gaze, and reaction
HOW      = pose, gesture, orientation, motion, and carried object/state
WHERE    = explicit background and relative positions (if specified)
CAMERA   = frame, viewpoint, distance, and composition (if specified)
STYLE    = source-provided lighting, art style, rendering cues
```

Prioritize **action/interaction and expression**; pose/camera/lighting support what happens. In a two-character shot, preserve `actor → action → target → reaction` exactly. For `carry + delta`, describe the current visible result without reintroducing clothing, props, marks, or posture that should have persisted from the previous shot.

### 3. Write natural-language sentences

Default output language: **English**. Use connected, specific sentences with natural grammar, not comma-separated tag lists. As a general target, use **2–5 sentences**, usually **40–120 words when the input supports that detail**. For sparse inputs, use fewer words; **never pad with invented details to satisfy a length target**.

Recommended ordering (not rigid):

1. Explicit subject identification and only grounded appearance/outfit.
2. **Main action** with correct actor and target; describe physical gesture/pose and consequence that are visible *in this shot*.
3. Expression, gaze, reaction and motion for each relevant subject.
4. Composition/camera/background, then grounded lighting/style/quality cues.

For **one subject**, pronouns can be used once identity is unambiguous. For **multiple subjects**, introduce each by explicit name and **reuse names at actor/target changes**, rather than “she”, “he”, or “they” with ambiguous referents. When necessary, give each subject a separate sentence before describing the interaction. Do not make the subjects swap actions, expressions, clothes or physical traits.

Render a *single visible moment*, not a sequence of before/after events. Convert “about to turn” versus “turning” versus “has turned” faithfully. If the upstream shot says “smiling”, do not upgrade to “laughing”; if “frowning”, do not soften to “serene”.

### 4. Preserve the scene's constraints

- Keep explicit framing (`close-up`, `upper body`, `full body`), camera angle (`low angle`, `from above`, `three-quarter view`), spatial placement (`left/right/front/back`) and facing direction.
- Keep background precisely. For the current Novel2Anima pipeline, a project-default white background may be applied **only if that default is provided by the project/render configuration**; do not add forests, scenery, particles, bokeh, cherry blossoms, or cinematic lighting without source evidence.
- Keep stated art style, linework, shading, palette, and lighting. Do not automatically insert “masterpiece”, “8k”, “cinematic”, or generic “highly detailed” text when absent.
- Preserve garment types, garment colors, hairstyles, eye colors, held props, and visible carried state exactly as supplied. Do not guess an unselected clothing color.
- Do not impose a pose ladder, change posture for beauty, invent hand use, move the camera, or create additional people/objects.
- Source-provided negative prompts remain **separate and unchanged** unless a distinct negative-prompt conversion is explicitly requested.

### 5. Handle non-natural technical tokens deliberately

Some source fragments carry machine control rather than visual semantics: `score_*`, LoRA trigger strings, weighted syntax such as `(keyword:1.5)`, embeddings, artist identifiers, safety labels, sampler-related directives, and workflow-specific markers.

- Preserve the source value exactly in `technical_tokens`/render configuration when required; **do not silently discard it**.
- Natural-language wording may mention the underlying visual meaning, but it **cannot guarantee equivalence** to numeric weights or token triggers. Flag `TECHNICAL_EQUIVALENCE_UNVERIFIED` when relevant.
- For a strict `natural` output, `natural_prompt` contains prose only; the render adapter decides whether separately stored technical tokens are passed as a supported auxiliary field or a hybrid prefix. If no safe adapter exists, flag an integration gap instead of pretending a pure-prose prompt preserved control behavior.
- Do not automatically convert a quality/safety metadata label into a new depicted action.

## Output contract

**Interactive human request:** Return only the English `natural_prompt` by default, followed by a concise issue note **only if** missing or contradictory information prevented a faithful conversion. Never show an internal checklist unless requested.

**Machine/pipeline request:** Return one JSON object (or JSONL, one object per shot) with this logical shape:

```json
{
  "shotId": "ACT01_SH001",
  "natural_prompt": "...",
  "status": "PASS",
  "source_prompt_ref": "optional immutable identifier/hash",
  "technical_tokens": [],
  "issues": []
}
```

Status semantics:
- `PASS`: all critical visual/narrative facts preserved; safe to offer to a configured render adapter.
- `NEEDS_REVIEW`: a noncritical source gap/technical equivalence remains; do not silently call this validated.
- `BLOCKED`: unresolved participant/role/action contradiction, serious source ambiguity, or loss of a required critical fact; **do not render** the conversion automatically.

`natural_prompt` may be `null` if `BLOCKED` and no faithful interpretation exists. No field above is a claim about existing DB schema.

## Semantic fidelity gate (mandatory for automated use)

Compare output **against the original ShotSpec and canonical source facts**, never via string-equality with the tag prompt. Reject or flag:

- `ENTITY_COUNT_MISMATCH`, `IDENTITY_DRIFT`, `ATTRIBUTE_SWAP`, `ROLE_SWAP`.
- `ACTION_DRIFT`, `ACTION_MISSING`, `EXPRESSION_DRIFT`, `GAZE_DRIFT`.
- `POSE_CAMERA_CONFLICT`, `BACKGROUND_DRIFT`, `WARDROBE_DRIFT`.
- `CONTINUITY_RESET`, `PROP_DRIFT`, `UNSUPPORTED_ADDITION`.
- `SOURCE_CONFLICT`, `UNRESOLVED_TAG`, `TECHNICAL_EQUIVALENCE_UNVERIFIED`.

Acceptance conditions:

1. Same participant count, named identities, actor and target.
2. Same principal action and temporal phase (start / in progress / result), expression and gaze.
3. Same specified garments, visible states, relative positions, camera and background.
4. No newly added character, prop, mood, environmental feature, pose change or story action.
5. Output reads as grammatical, compact English prose, not a list of tags or staccato fragments.
6. Any unresolved item is surfaced; no fabricated certainty.
7. The immutable tag source, negative prompt and previous generation history remain intact.

A rendering result is not evidence that the prompt met these conditions: inspect source-to-output fidelity independently, then evaluate image-to-shot fidelity after render.

## Examples

### Solo — tags to prose

**Source:**

```text
1girl, seia_(blue_archive), long_white_hair, golden_eyes, sitting,
soft_smile, looking_at_viewer, upper_body, white_background
```

**Natural language:**

```text
Seia from Blue Archive has long white hair and golden eyes. She is seated with a soft smile and looks toward the viewer. The illustration frames her upper body against a plain white background.
```

No outfit, studio light or scenery is invented because none was supplied.

### Two characters — preserve subject roles

**Structured source (illustrative):**

```text
Participants: Seia (left), Neru (right), both from Blue Archive.
Action: Neru raises her right hand to wave at Seia.
Expression: Neru smiles; Seia watches Neru with a surprised expression.
Camera: medium shot. Background: plain white.
```

**Natural language:**

```text
Seia from Blue Archive stands on the left, watching Neru with a surprised expression. Neru from Blue Archive stands on the right and smiles as Neru raises her right hand to wave toward Seia. The scene is framed in a medium shot against a plain white background.
```

**Never** rewrite the action as “Seia waves to Neru”, add a hug, or assign Seia's surprise to Neru.

### Ambiguity — require review, not improvisation

**Source:** `2girls, smile, white_hair, black_hair, hand_on_shoulder` with no per-character binding.

**Result:** `BLOCKED` (unclear whose hair/color, whose hand is on whose shoulder, and which character smiles). Do not generate a confident two-person narrative from these unassigned tags.

## Operational rules

- This skill is a **read/transform/validate** step; no autonomous writes to SQLite, seed plans, source tags, QC findings, or accepted image history.
- Never claim to have inspected an actual DB row, model card, image, or render run unless it was provided or inspected.
- If the user requests only a conversion, do the conversion; do **not** automatically start planning a new act or changing catalog records.
- For code integration, first inspect current repository files and preserve old tag-based behavior as a selectable option. Run the tests in [references/qa-fixtures.md](references/qa-fixtures.md) and perform side-by-side image evaluation before changing production render defaults.
