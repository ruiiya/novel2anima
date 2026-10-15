# Prompt and render reference

See [retrieval-and-memory.md](retrieval-and-memory.md) for the V4 complete-catalog
retrieval contract, candidate evidence, project-wide memory and feedback.
**Examples below are illustrative, not confirmed SQLite rows or measured render quality.**

## ShotSpec shape

Mirrors the runtime tables in the catalog DB (`shot`, `generation`), not the catalog itself.

```json
{
  "shotId": "ACT02_SH018",
  "actId": "ACT_02",
  "characterId": "CHAR_001",
  "action": { "code": "ACTION_SUDDEN_TURN", "description": "turning sharply left" },
  "expression": { "code": "EXPR_SURPRISED", "intensity": 0.8 },
  "pose": { "code": "POSE_TORSO_TWIST" },
  "motion": ["hair swinging"],
  "camera": { "framing": "medium_shot", "view": "three_quarter" },
  "background": "pure_white",
  "contentProfile": "NSFW",
  "status": "PLANNED"
}
```

Status flow: `PLANNED -> GENERATED -> APPROVED | REJECTED`. The DTO is an illustrative
minimal subset; retain additional project/shot fields when they exist in the actual DB.
The compiler focuses on grounding, normalization and coherent tags. `NSFW` means
adult sexual content may be within the project scope; this example's **specific visual
action remains nonsexual**. When the actual beat involves adult sexual interaction,
represent that intent and participants in the ShotSpec fields supported by the
application; never invent SQLite columns to hold it.

## High-intensity, multi-participant NSFW ShotSpec (metadata example)

An adult story can carry specific group/intensity genre metadata without its meaning
being rewritten as romance. A high-intensity group scene may include labels such as
`gangbang`, `group_sex` or `rough_sex` when those labels actually describe user intent.
Preserve the number of participants and each adult character's identity, action role,
expression, and state. Treat genre/tone labels separately from the primary action tag.

This application-level DTO is illustrative, **not** a claim about SQLite V1 columns:

```json
{
  "contentProfile": "NSFW",
  "storyGenre": ["gangbang", "group_sex"],
  "toneTags": ["rough_sex"],
  "intensityBand": "high",
  "interactionCategory": "adult_group_sex",
  "participants": [
    {"characterId": "CHAR_A", "role": "participant", "expressionConcept": "<resolved_from_catalog>"},
    {"characterId": "CHAR_B", "role": "participant", "expressionConcept": "<resolved_from_catalog>"},
    {"characterId": "CHAR_C", "role": "participant", "expressionConcept": "<resolved_from_catalog>"}
  ],
  "primaryActionConcept": "<resolved_from_catalog>",
  "background": "pure_white"
}
```

The displayed genre labels are input/retrieval candidates, **not asserted live DB
entries**. Only use concrete catalog IDs after resolving them. Map extra DTO fields
into actual JSON fields where supported, otherwise report a schema gap; never invent
SQLite columns. Keep original semantic labels available even if a downstream provider
cannot render a particular request.

## Prompt block order

```text
[QUALITY + STYLE + WHITE BACKGROUND]
[CHARACTER IDENTITIES / OUTFITS — per participant when relevant]
[PRIMARY ACTION / INTERACTION, including adult sexual intent when relevant] # priority 1
[EXPRESSION + FACIAL CUES]          # priority 1
[POSE / GESTURE]                    # support
[MOTION]                            # support
[CAMERA / COMPOSITION]              # support
[SHORT NATURAL LANGUAGE DETAIL]
```

Hybrid Danbooru tags plus a short natural-language caption: exactly one primary action, no
duplicate aliases, no contradictory camera/pose/expression combinations, and a short prompt
over a long one. Resolve aliases and check conflicts against `tag_alias`,
`tag_relation(relation='conflicts')`, `concept_relation` before emitting. Prompt compilation remains separate from catalog discovery and follows the actual
rendering environment.

## Retrieval and ranking

1. Input: act/beat intent, action + expression, energy, character id, project metadata and history.
2. Search `visual_concept_fts`, **raw canonical tags, aliases and multi-role tags**,
   plus bounded relation/curated-preset expansion; combine with indexes;
   return original source fields and review values with the candidates.
3. Attach provenance, original labels and editorial status. Let the LLM interpret shot
   context while keeping candidate discovery comprehensive. Preserve source usage rights.
   In group scenes, retain participant count, role assignments, story genre and intensity
   separately from model tag candidates.
4. Rank on action relevance, expression fit, and novelty of the action-expression pair;
   sexual action/interaction is eligible for this semantic ranking like any other adult
   scene intent. Preserve evidence without adding content-grade penalties;
   then pick pose/motion/camera as support. Draft candidates get a confidence annotation,
   not an automatic zero score; avoid auto-approving them.
5. Return top 5–10 candidates with canonical IDs, original metadata, confidence,
   mapping and ranking reasons so the director sees alternatives before committing.

Ranking weights are a heuristic and are **not benchmarked** - treat any weight as a tunable
POC value, say so when reporting results, and never present a ranking score as validated.


## Repetition memory

- `primary_signature = (action, expression, intensity_band)`
- `secondary_signature = (pose, motion, camera, direction)`
- Windows: last 5-10 shots, whole act, whole project (200-500+ shots).
- Counts come from stored history: `PLANNED` is not accepted history, `REJECTED` never counts
  as accepted, `APPROVED` dominates.
- Limiting repeated combinations, not forbidding repeated actions.

## Render profile

| setting | POC value | note |
|---|---|---|
| checkpoint | Anima Base | plus the 4-step LoRA, not an Anima-Turbo checkpoint |
| LoRA | `sorryhyun/anima-turbo-4step` v3 | strength start 1.0 |
| steps | 4 | official Anima-Turbo runs 8-12 steps; do not stack |
| CFG | 1 | negative prompts lose effect; use positive constraints |
| sampler | `er_sde` | confirm it exists in the installed ComfyUI |
| background | white | `white background`, `simple background`; use `solo` **only** for one participant |

Read the model card and prompt rules for the exact checkpoint/LoRA in use before a run, and
save the actual workflow, seed, sampler, steps and CFG with each generation row.

Every produced image is appended to `generation` with `prompt`, `seed`, `image_path`,
`image_sha256`, `evaluation_json`, `decision`. Image bytes stay on disk - the DB stores paths.

## QC and retry taxonomy

| failure | first response |
|---|---|
| render defects / broken anatomy | retry same spec, new seed |
| background not white, clutter | reinforce positive background constraints |
| identity drift | benchmark a dedicated identity LoRA/reference adapter; do not retune the Turbo LoRA for identity |
| action or expression not readable | rerank retrieval, pick a more explicit action tag, or split the shot |
| near-duplicate of a recent approved shot | change the primary signature, or justify the repetition |

Retries are bounded per shot and target one named failure; unattempted fixes are reported,
not silently skipped. Human review decides approval - the pipeline may propose, not approve
on its own. Near-duplicate detection should not rely on pHash alone.

## NSFW adult interaction integration notes

For a user-requested adult sexual beat, keep its **sexual semantic category** in the
planner/ShotSpec and include action + expression candidates from the complete catalog.
Do not treat `contentProfile=NSFW` as a request to change all shots to sexual content:
mixed projects also contain nonsexual actions. Preserve relationship/participants and
per-character expressions if the actual schema supports them; otherwise flag a DTO/schema
gap. Do not substitute flirtation for sexual activity solely because of a content label.
For multi-character scenes, preserve subject-specific action/expression and per-character
carry/delta instead of flattening all participants into one shared state. Adult-only
scope is unchanged; keep catalog discovery independent from generation-stage constraints.
