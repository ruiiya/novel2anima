# Natural-language converter — QA fixture checklist

These are **acceptance examples**, not executed automated test results. Build machine-executable tests from them once the adapter and a concrete ShotSpec schema are available.

| ID | Input condition | Expected behavior |
| --- | --- | --- |
| NL01 | `1girl, seia_(blue_archive), sitting, smiling, white_background` | One named subject, seated and smiling, blank white background, natural sentences. |
| NL02 | No outfit or color in source | Do **not** invent a dress, uniform, or color. |
| NL03 | `1girl, 1boy` with explicit per-subject action and gaze | Two distinct character descriptions, explicit actor/target and gaze. |
| NL04 | `2girls, black_hair, white_hair, smiling` without bindings | `BLOCKED`; cannot assign traits or expression to an individual. |
| NL05 | Neru waves at Seia; Seia is surprised | Do not change who waves or who is surprised. |
| NL06 | Shot says “turning left” | Do not produce “has turned right” or an additional movement. |
| NL07 | `full_body, low_angle`, unambiguous pose | Keep full-body framing and low camera angle. |
| NL08 | `close_up` and `full_body` asserted simultaneously | Flag `SOURCE_CONFLICT`; do not pick whichever sounds better. |
| NL09 | Project default explicitly `pure_white` | Use white background, no added room or trees. |
| NL10 | No background or project default given | Do not assume white; omit unsupported surroundings. |
| NL11 | Previous shot carries a red scarf, current shot does not remove it | Preserve red scarf if it remains visible/relevant. |
| NL12 | Previous shot loses a scarf; delta explicitly removes it | Do not restore scarf in current prompt. |
| NL13 | `soft_smile` | Do not transform into laughing, crying or an angry expression. |
| NL14 | Character A touches Character B's right shoulder | Preserve toucher, target, side and contact point. |
| NL15 | `score_7`, `@artist`, LoRA trigger, `(pose:1.5)` | Preserve exact technical values separately; mark unverified semantic equivalence. |
| NL16 | Prompt contains existing negative prompt | Leave negative prompt unchanged; do not merge negatives into positive prose. |
| NL17 | `long_white_hair` but character profile says short black hair | Flag conflicting sources and request an authoritative shot decision. |
| NL18 | Unrecognized tag, no catalog evidence | Report `UNRESOLVED_TAG`, avoid hallucinated semantics. |
| NL19 | Three consecutive shots of a simple gesture | Convert independently; do not add new narrative events just for variation. |
| NL20 | Original tag mode checked and approved | Conversion does not alter original DB/string or break existing tag QA. |

## Example regression assertions

For each sample, check:

- `same(people, identities, action_actor, action_target, phase, expression, gaze)`.
- `same(pose, held_objects, outfit, colors, location_if_given, camera, background)`.
- `added_visual_facts == []` unless sourced from a verified project default.
- `deleted_critical_facts == []`.
- `natural_prompt` is grammatical English prose, **not** tags joined by commas.
- `source_prompt_unchanged == true`.

## Suggested A/B visual evaluation

Using the same frozen ShotSpec/seed/model/workflow where supported:

1. Render the existing compiled tag prompt (baseline).
2. Render the derived natural-language prompt (candidate).
3. Check **action correctness, expression correctness, participant identity, role assignment, pose/camera accuracy, background, continuity and composition** individually.
4. Do not equate “looks prettier” with “more faithful”; track aesthetic quality separately.
5. Report tested checkpoint/version, LoRA, seed, sampler, resolution, steps, CFG and number of evaluated shots. Do not claim a win for NL without measured evidence.
