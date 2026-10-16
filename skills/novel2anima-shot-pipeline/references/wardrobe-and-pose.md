# Wardrobe colour, pose ladder and the QA reporting layer

Three mechanisms sit between a plan and the prompt file. Two of them are **deterministic gates
applied at seed time**, the third only **reports problems** so the model can decide.

## 1. Colour lock of outfits (data lives in the catalog, not in code)

A garment tag without a colour lets the model repaint it between shots (stockings white in one
shot, black in the next). The lock replaces each garment with a colour-aware variant.

- Knowledge is stored as `visual_concept code='WC_<garment>'` (kind `other`), built by
  `python etl/import_colour_sets.py --apply`:
  - `concept_tag usage='primary'` = the base garment;
  - `concept_tag usage='alternative'` = a real `<colour>_<garment>` catalog tag;
  - `priority=1` on a variant = the colour currently chosen for that garment.
- Phase-1 preparation lives in `data/wardrobe/colour_choice.json` (`garment -> colour`); it wins
  over colours inferred from already-seeded acts. Garments that have **no** colour variant in the
  catalog use a generic cue from `data/wardrobe/colour_cue.json` (`<colour>_clothing`), e.g.
  `miko` -> `white_clothing`.
- At seed time (`etl/wardrobe.py`, called by `etl/seed_plan.py`) every base garment is swapped for
  its variant; underwear follows the dominant colour of the set (black set -> `black_panties`).
- A garment with **no colour decision is never guessed**: the seed prints
  `chua chon mau: [...]` and the QA layer records it as `mau_thieu`. Add the decision to
  `colour_choice.json` when phase 1 makes it (verify the variant tag really exists first).

## 2. Pose ladder (still code, because it is a judgement about staging)

Inside one phase the stance may only escalate: standing -> kneeling/squatting -> sitting -> lying.
A shot that steps back is pulled to the previous shot's stance and the contradictory pose/action
tag is dropped. `standing` is the default floor, so an act should open standing.

- `python etl/seed_plan.py <plan.json>` — gate on (default).
- `--no-fix-pose` — report the ladder violations only, keep the author's poses.
- Neutral support tags (`spread_legs`, `legs_up`, `bending_over`, `all_fours`dots) are kept as-is.

## 3. QA reporting layer — identify, do not enforce

`python etl/qa_shots.py [--act N] [--apply]` scans every seeded shot and writes one row per
problem into `shot_state` with `source='qa:v1'` (`--apply` first deletes its own rows only).

| axis | meaning | severity |
|---|---|---|
| `mau_thieu` | garment has no colour decision in the catalog yet (phase-1 gap) | 0.4 |
| `mau_lech` | catalog knows a colour but the shot carries neither the variant nor the cue | 0.5 |
| `xung_dot` | two tags in the same shot linked by `tag_relation(relation='conflicts')` | 0.6 (0.3 when the note says "not to be confused with") |
| `tu_the_lech` | stance steps back inside a phase | 0.5 |
| `noi_dung_chan` | tag marked `blocked` in `tag_content_label` | 1.0 |

A second producer writes the same table from an LLM pass: `etl/llm_review.py --apply` stores `llm:<axis>` rows with `source='qa:llm:v1'` (meaning vs beat, self-contradiction, wrong-character tags, state reset) and keeps the raw answer in `data/reviews/actNN_llm.json`. Severity is a priority hint, **not** a verdict: nothing here rewrites prompts or blocks a seed.
`value_tag_id` holds the tag that triggered the row, `since_shot_no`/`cause_shot_no` the shot
where it started. Report them to the user; let the shot author or the model decide.

## Using tags outside the base tag

`python etl/suggest_tags.py --tag black_thighhighs` (or `--shot <id>`, `--act <n>`, `--limit`,
`--role`) proposes additional tags from `tag_relation` (compatible / recommends / implies),
from `concept_tag optional/alternative` of concepts bound to the shot's tags, and from
`tag_role`. Output is `name :id post_count role why` — every row must be looked up before use;
never invent IDs.

## Plan input: names are the source of truth

Plans may carry stale `name:id` pairs (ids from another catalog snapshot). `seed_plan` resolves
each ref by **name** through `tag(canonical_name)` and reports
`id cu trong plan -> lay theo ten: N ref`; only a name missing from the catalog aborts the seed.
Prefer writing fresh plans by name, and re-run `python etl/check_reseed.py` after catalog changes
(prompts must stay byte-identical, then it re-runs the QA layer because reseeding cascades
`shot_state` rows away).

## Order after a schema rebuild

```text
python etl/build.py all                  # schema -> fetch -> load -> verify
python etl/import_colour_sets.py --apply # nap bang mau vao catalog (sau khi catalog doi)
seed: python etl/seed_plan.py <plan>     # cho moi plan
python etl/qa_shots.py --apply           # lop bao cao van de
python etl/check_reseed.py               # 5 checks
```
