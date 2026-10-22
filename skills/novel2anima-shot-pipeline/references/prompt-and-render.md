# Prompt and render reference

See [retrieval-and-memory.md](retrieval-and-memory.md) for the V4 complete-catalog
retrieval contract, candidate evidence, project-wide memory and feedback.
**Examples below are illustrative, not confirmed SQLite rows or measured render quality.**

## ShotSpec shape

Mirrors V4.1 canonical revision tables (`shot_spec_revision`, `shot_participant`,
`shot_interaction`, `shot_outfit_binding`, `shot_prompt_revision`, `generation`), not the
catalog vocabulary. The DTO below is illustrative; inspect the actual schema.

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

## Anima prompt rules (circlestone-labs/Anima model card)

- Syntax: lowercase tags, **spaces instead of underscores** (`long hair`, `from behind`, `dark-skinned male`);
  only `score_*` tags keep their underscore. Artist tags need an `@` prefix (`@artist name`).
- Tag order: `[quality/meta/year/safety] [1girl/1boy/1other] [character] [series] [artist] [general]`.
  Order inside a section is arbitrary.
- Positive prefix: `masterpiece, best quality, score_7, ` on the base model, then the safety tag
  (`safe` / `sensitive` / `nsfw` / `explicit`). Anima-Aesthetic is quality-tuned: quality tags are
  optional and `score_*` tags should be dropped.
- Negative: `worst quality, low quality, score_1, score_2, score_3, artist name, blurry, jpeg artifacts, chromatic aberration`.
  It is stored in the prompt revision/DB payload; any `.neg.txt` copy is an export only.
  At CFG 1 negatives lose effect, so still state constraints positively.
- Natural language may be mixed with tags in any order; a pure-NL prompt should be at least two
  sentences. Name a character and then describe their appearance - required for multi-character
  shots, otherwise the model mixes the cast up.
- Prompt weighting needs a higher value than SDXL, e.g. `(chibi:2)`.
- The model was trained with random tag dropout: do not stuff every relevant tag in.
- The base model's default style is plain; artist/quality tags are what shape it.
- One artist per project, not per shot: a plan-level `artist_line` (for example `@miyama-zero`, the
  High School DxD light-novel illustrator) is emitted once after the `[series]` block, so faces and
  rendering stay consistent across acts. Two artists is the ceiling; three collapse the style. The
  separate `artist name` negative only suppresses watermark signatures, so it can stay.

## Outfit colour, pose and QA gates (seed time)

The prompt compiler does not decide garment colours or stance order by itself: `python -m novel2anima.wardrobe.rules`
swaps every garment for the colour variant recorded in the catalog (`visual_concept WC_*`, prepared
for phase 1 in `data/wardrobe/*.json`) and keeps stance monotone inside a phase
(standing -> kneeling -> sitting -> lying). Problems the gates cannot decide are written to
`shot_state` by `python -m novel2anima.quality.shot_rules` for the model to judge. Details, commands and the current axes:
[wardrobe-and-pose.md](wardrobe-and-pose.md).

## Prompt self-check (`python -m novel2anima.quality.prompt_rules`)

After seeding an act (or the whole project) run `python -m novel2anima.quality.prompt_rules [--act N]
[--examples K]` — read-only, exit 1 when an ERROR remains. It compares the canonical
prompt revision with the DB and catalog tables:

| check | what it means |
|---|---|
| revision vs DB | each shot resolves to the expected current `shot_prompt_revision`; any export file is not authority |
| syntax | lowercase tags, no `_` left (except `score_*`), no `, ,` |
| missing tag | every tag in the spec must appear in the prompt — unless another tag in the same shot implies it (deliberately pruned) |
| redundant tag | a tag that another tag implies is still in the prompt |
| conflict | a `tag_relation(relation='conflicts')` pair in one shot: ERROR, downgraded to WARN when the pair is also `compatible` or its note says "not to be confused" |
| counts | `Ngirls / Nboys / yuri` line matches the participants (gender read from the plan) |
| slots | missing action / expression / pose |
| length | more than 80 tags per prompt (random tag dropout flattens long prompts) |
| duplicates | two shots share a prompt, or one action repeats 4 shots in a row |
| negative | the prompt revision has a non-empty negative carrying worst/low quality + blurry |
| `shot_state` | the act's `qa:*` rows (`mau_thieu`, `mau_lech`, `xung_dot`, `tu_the_lech`, `noi_dung_chan`) |

### LLM self-check (`python -m novel2anima.llm.adapters.review_adapter`)

`prompt_rules` is mechanical; it cannot tell that a caption says "legs clamping" while the tag
says `spread_legs`, or that the bra flips black -> white inside one beat. For that layer:

    python -m novel2anima.llm.adapters.review_adapter --act 13            # call the configured reviewer
    python -m novel2anima.llm.adapters.review_adapter --act 13 --apply    # append QA findings
    python -m novel2anima.llm.adapters.review_adapter --act 13 --payload  # print payload for review

Each batch of shots is sent as `shot | phase | participants | beat | caption | tags` and the model
answers strict JSON `{"findings":[{"shot","axis","severity","why"}]}` with axes
`y_nghia / mau_thuan / danh_tinh / tiep_dien / gia_tao / thieu / khac` (meaning vs beat,
self-contradiction, wrong character assignment, reset state, unreadable phrasing, missing beat
detail). Results belong in `qa_issue`/derived QA projections; a JSON report may be exported but
is not the authority.

Treat LLM findings as **hypotheses, not verdicts** (it does hallucinate, e.g. "tag lap 2 lan" that
is not in the string): `prompt_rules` reports them as WARN, so mechanical checks stay the gate
and the LLM layer only proposes what to inspect. Verify each one against the prompt before
changing a plan. Re-seeding an act cascades derived `shot_state` rows away; reconstruct derived
projections from canonical revisions and QA rows rather than treating an export as truth.

A WARN is a judgement call to report; an ERROR blocks: fix the plan or catalog and append a
new revision, never hand-edit an approved prompt revision. `python -m scripts.qa.check_reseed`
is an authoring/diagnostic gate, not a story-runtime endpoint.

## Prompt block order (compiler output)

```text
[quality + score tags][safety tag][count: 1girl / Nboys]
[CHARACTER IDENTITIES + OUTFITS — character, series, attributes, per participant]
[OUTFIT / BODY STATE — carried marks, piercings, fluids live here]
[PRIMARY ACTION / INTERACTION, including adult sexual intent when relevant] # priority 1
[EXPRESSION + FACIAL CUES]          # priority 1
[POSE / GESTURE]                    # support
[MOTION]                            # support
[CAMERA / COMPOSITION]              # support
[BACKGROUND CONSTRAINT][SHORT NATURAL LANGUAGE CAPTION]
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
| steps | 4 | POC value; the model card gives 30-50 steps for Base/Aesthetic and 8-12 for Turbo |
| CFG | 1 | Turbo setting; Base/Aesthetic want CFG 4-5. Negatives lose effect at CFG 1 |
| sampler | `er_sde` | card's neutral default; `euler_a`, `dpmpp_2m_sde_gpu`, `euler` also work |
| resolution | 512-1536 px | fixed square per project style; 1024 is the usual middle |
| background | white | `white background`, `simple background` in the general section; use `solo` **only** for one participant |

Read the model card and prompt rules for the exact checkpoint/LoRA in use before a run, and
save the actual workflow, seed, sampler, steps and CFG with each generation row.

Every produced image is appended to `generation` with the prompt revision, seed, model
settings, `asset_id`, evaluation and decision. Image bytes are stored in `asset_blob`;
there is no `generation.image_path` authority column.

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
