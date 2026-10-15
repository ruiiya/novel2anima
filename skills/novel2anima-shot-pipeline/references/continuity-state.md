# Continuity and state carry-over (EXPERIMENTAL)

**Status: trial model. Not validated, not authoritative.** It exists so repeated runs can
accumulate evidence. Expect to infer more axes while implementing; treat every axis list
here as a starting hypothesis, not a closed schema. Any table sketch below is
**reference content only** - it is not created, not migrated and not an official part of
the V1 catalog.

## Why

A shot sequence loses feeling when the physical state resets between adjacent shots: the
masturbation beat ends and the next shot returns to a dry, clean body; clothing that was
already open appears closed again; marks, sweat and fluids vanish. Each shot must be both
a *continuation* and a *step forward*.

## Contract

Every ShotIntent/ShotSpec carries two fields:

- `carry` - the state inherited from the previous shot in the act.
- `delta` - what this beat changes, and only what this beat causes.

Rules:

1. No shot may inherit an empty state inside a running scene.
2. A new state element requires a causal beat that produced it. No spontaneous appearance.
3. Once present, an element persists until an explicit beat removes it; removal is itself a
   recorded `delta`.
4. Monotonic where the beat is monotonic: clothing goes one way (worn -> open -> partial ->
   removed). No re-dressing without a beat that narrates it.
5. Fluids, sweat and marks accumulate and are visible in every later shot at their current
   severity; they dry or fade on their own schedule, never instantly.
6. Post-climax beats must show the consequence of the climax (wet thighs, slick patch on the
   sheet, limp tail, breathing state), not a reset to the state before it.
7. Novelty applies to camera, pose and framing. Physical state is continuity, not novelty:
   vary the camera freely, do not vary the body back to clean.

## Multi-participant state tracking (design gap)

For adult group scenes, a single `(shot_id, axis)` key cannot represent independent
values of the same axis on multiple characters. The trial SQLite model currently has
no `character_id`/`target_id` in `shot_state`. Preserve per-participant `carry`/`delta`
in the ShotSpec layer where supported; do not interpret a shared-axis row as evidence
that every participant has that state. A future migration should support per-character
state ownership, optional body region, action actor/target, and shared props. This is a
schema gap, not a claim that the current DB has been migrated.

## Axes discovered so far (hypothesis, extend in the field)

- fluids: `pussy_juice`, `female_ejaculation`, `saliva`, `drooling`, `sweat`, `cum`
- marks: `bite_mark`, scratch/claw trails, reddened skin, grip marks
- physiology: flush/blush severity, sweat sheen, erect nipples, breathing state
  (`heavy_breathing`, `panting`), trembling
- hair/body: `wet_hair`, stray strands, hair_between_eyes, dishevelment
- outfit state: current removal stage, displaced straps, stretched fabric, stains;
  where removed items ended up
- posture/fatigue: trembling -> weak knees -> sitting -> lying; tail raised -> wagging ->
  limp -> twitching
- props: a used toy stays where it was dropped or is still in place
- environment (only when the shot is not on the default white background): wet spot,
  discarded clothing pile, moved furniture
- decay clocks: marks fade, sweat dries, fluids cool - on a stated schedule, never instantly

## Current implementation (trial, inferred data)

Migration `sql/migrations/002_shot_state.sql` creates two tables **outside** `schema_v1.sql`:

```text
shot_state(shot_id, axis, value_tag_id, severity, since_shot_no, cause_shot_no, source)
act_continuity(act_id, axis, initial_tag_id, notes)
```

`etl/infer_state.py` (v0.3) walks each act in shot order and fills them. The rows are
**inferred placeholders**: they are searchable, grep-able trial data, not editorial fact.
A missing row does not prove a state element is absent, and `value_tag_id IS NULL` means
either "initial state" (`outfit:stage` level 0 = dressed) or a catalog gap.

Harvested from `tag_relation(relation='implies')` - the same source also drives prompt
pruning, see below.

### Value ladders (v0.3)

A state escalates instead of appearing once:

| axis | ladder |
|---|---|
| fluid:vaginal | `pussy_juice` -> `pussy_juice_on_fingers` -> `pussy_juice_drip` -> `pussy_juice_trail` -> `pussy_juice_puddle` |
| fluid:ejaculate | `female_ejaculation` |
| fluid:saliva | `saliva` -> `saliva_trail` |
| fluid:sweat | `sweat` -> `wet_hair` |
| mark:bite | `bite_mark` -> `bite_mark_on_shoulder` (+ on_neck / on_thigh / on_breast available) |
| mark:scratch | `scratches` -> `red_skin` |
| physiology:flush | `blush` -> `red_skin` |
| physiology:breath | `heavy_breathing` -> `panting` -> `parted_lips` |
| hair:mussed | `messy_hair` -> `wet_hair` |
| posture:fatigue | `trembling` -> `afterglow` |
| outfit:stage | (dressed) -> `undressing` -> `bottomless` -> `completely_nude`, monotonic; value names are generic, triggers include open_kimono / clothes_pull / skirt_lift / strap_slip / unzipped / bra_pull and topless / panties / panties_aside |
| outfit:soaked | `wet_clothes` while still dressed; **removed** once nude (row keeps `value_tag_id=NULL`, source `inferred:v0.3:removed`) |

### Decay (v0.3)

A live state that the current shot does not refresh loses severity every shot and is
dropped at zero; the drop is written as one row with `value_tag_id=NULL` and
`source='inferred:v0.3:decayed'`.

| axis | refreshed by | severity lost per shot | gone after ~ |
|---|---|---|---|
| fluid:sweat | sweat / heavy_breathing / panting / wet_hair | 0.15 | 4 shots |
| physiology:breath | same set + strong reactions | 0.15 | 4 shots |
| fluid:saliva | saliva / drooling / kiss tags | 0.12 | 5 shots |
| hair:mussed | messy_hair / wet_hair | 0.12 | 5 shots |
| physiology:flush | blush / red_skin | 0.10 | 6 shots |
| posture:fatigue | trembling / afterglow | 0.08 | 7 shots |
| fluid:vaginal | any genital action tag | 0.05 | 12 shots |
| fluid:ejaculate | female_ejaculation | 0.05 | 12 shots |
| mark:scratch | scratching / clawing / scratches | 0.04 | 15 shots |
| mark:bite | biting / bite_mark | 0.03 | 20 shots |
| physiology:nipples | nipples / topless / completely_nude | 0.02 | never practically |
| prop:toy | sex_toy + friends | 0.00 | never - a dropped toy stays put |
| outfit:stage | monotonic, never decays | - | - |

Refreshing a state restores it to the severity of its current ladder level, never above.

Closely related but unused so far: `pussy_juice_stain`, `pussy_juice_drip_through_clothes`,
`wet_spot`, `hickey`, `handprint`, `slap_mark`, `cum_pool`, `cum_on_body`, `excessive_cum`.

### Prompt pruning (data-driven)

The compiler drops a tag when another tag in the same prompt transitively implies it
(`tag_relation(relation='implies')`, closure computed at seed time). Observed redundancies
inside our own tag set: `double_dildo`/`dildo`/`strap-on`/`vibrator` -> `sex_toy`,
`cowgirl_position`/`upright_straddle` -> `straddling`, `french_kiss` -> `kiss`,
`completely_nude` -> `nude`, `on_back`/`on_side`/`on_stomach` -> `lying`,
`hug_from_behind` -> `hug`, `open_kimono` -> `kimono`, `panties_around_one_leg` -> `panties`,
`seductive_smile` -> `smile`, `very_long_hair` -> `long_hair`, `twin_braids` -> `braid`,
`skin_fang` -> `fang`, `fox_tail` -> `tail`, `standing_sex` -> `standing`,
`black_dress` -> `dress`, `white_apron` -> `apron`, `kimono` -> `japanese_clothes`.

No `conflicts` edges touch the tags used by the current acts.

## Validation loop

1. Plan a batch with `carry`/`delta` filled in.
2. Render and compare adjacent shots: did any element disappear, reappear, or reset?
3. Record each violation with the shot pair and the axis.
4. After several batches, promote the recurrent axes into the schema decision; do not
   freeze the axis list from a single run.
