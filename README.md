# Novel2Anima

A local story-to-image pipeline for anime-style shot production: a **SQLite catalog**
of Danbooru/Anima tag data, a **story planning layer** (acts → beats → ShotSpecs →
seeded shots → compiled prompts), an **LLM-first planning skill set**, and a set of
deterministic Python gates that validate everything before anything is rendered
through ComfyUI (Anima Base 2B + Turbo 4-step LoRA). No PostgreSQL, no vector DB —
one SQLite file plus flat JSON/plan files.

Python 3.9+ stdlib only (`sqlite3`, `urllib`, `csv`, `json`). SQLite must have FTS5.

## Pipeline at a glance

```text
Idea (LLM skill, 3–5 synopsis picks)
  → ActSpec JSON (act_specs/*.json, hand- or LLM-authored beats[])
  → etl/build_story_plan.py   compile beats → seed-compatible plan (shots derived, never a fixed quota)
  → etl/plan_actions.py       list missing narrative bridges
  → etl/check_story.py        story QA (0 ERROR required)
  → etl/seed_plan.py          validate, resolve tags in SQLite, upsert shot rows, publish prompt files
  → etl/check_prompts.py      diff prompt files vs DB/catalog (0 error before render)
  → etl/qa_shots.py --apply   advisory findings into shot_finding/shot_state
  → etl/llm_review.py --act N --apply   semantic LLM pass (caption vs tags, colour flips, wrong-character tags)
  → ComfyUI render → generation records → QC/revision
```

Every plan follows the shared narrative contract in `etl/story_logic.py`: interaction
direction (`actor → primaryAction → target`, `INTERACTION_*` errors), pose bridges,
prop ownership, required reactions, phase/wardrobe contracts, exposure contracts and
duplicate/repetition guards. The validator is pure Python — no DB access, no silent
rewrites; problems are reported before they are fixed.

## Run the catalog

```text
python etl/build.py all          # schema → fetch → load → verify
python etl/build.py fetch        # download pinned sources into data/sources/ (sha256 manifest)
python etl/build.py load         # idempotent import into db/novel_anima.db
python etl/build.py verify       # integrity_check / foreign_key_check / FTS5 / row gates
python etl/build.py schema --force   # drop and rebuild the db from sql/schema_v1.sql
python etl/seed_plan.py data/characters/dxd_roster.json   # roster-only upsert, writes no shots
```

## What is in the db (measured, 2026-10-15)

| table | rows | source |
|---|---|---|
| `tag` | 280,100 | implications db + taxonomy CSV + Anima index (+ local Danbooru dumps) |
| `tag_alias` | 49,340 | Danbooru active aliases (40,732) + CSV aliases, first-writer-wins |
| `tag_relation` | 45,501 | Danbooru active `implies` edges (+ curated recommends/conflicts) |
| `tag_role` | 30,265 | taxonomy `slot` mapping: outfit 12,028 / other 6,927 / identity 3,496 / pose 2,976 / action 1,354 / … |
| `tag_content_label` | 548 | Anima `banned_tags.csv` → `scope='blocked'` |
| `visual_concept` | 297 | Anima-Tools pose groups (draft, `contextual`) + wiki groups |
| `concept_tag` | 514 | primary/optional tag per concept |
| `tag_source` | 387,997 | provenance row per (tag, source, ref) |
| `character_profile` | 236 | local rosters (Blue Archive, DxD) with identity/outfit JSON |

Verified: `integrity_check` ok, 0 foreign-key violations, FTS5 index == concept rows.
Rerunning `load` changes nothing: imports are keyed on
`source_snapshot(source_key, revision)`.

## Pinned sources (`etl/sources.json`)

| key | pin | use |
|---|---|---|
| `danbooru_implications` | content sha256 (site rebuild) | aliases, implications, tag census |
| `danbooru_taxonomy` | HF revision `1fc970c9` | category/slot/confidence, post counts, aliases |
| `anima_tag_index` | commit `77fba841` | Anima naming, post counts, banned artists |
| `anima_wardrobe` | commit `e049b034` | attire slots, pose/expression/clothing vocabulary |
| `anima_tools` | commit `f9c0fd57` | pose groups → `visual_concept` seeds |

Every download is hashed into `data/sources/manifest.json`; `load`/`verify` run
offline from that cache. Licenses are recorded per source in `sources.json` and
copied into `source_snapshot.license_note` — check them before redistribution.

## Local Danbooru dump and maintenance importers

```text
python etl/import_danbooru_dump.py [--dir DIR] [--only tags,aliases,implications,artists]
python etl/analyze_posts.py [--file PATH] [--limit N] [--pair-every 8] [--dry-run]
python etl/import_posts_unknown.py [--min-count 5]
python etl/import_wiki_pages.py [--file PATH]
python etl/import_wiki_links.py [--reset]
python etl/import_wiki_groups.py
python etl/import_colour_sets.py --apply
python etl/prune_tags.py [--apply] [--vacuum]
python etl/cleanup_db.py [--apply] [--vacuum]
python etl/check_reseed.py
```

- `import_danbooru_dump.py` imports official CSV dumps from disk; hashed into
  `source_snapshot`, idempotent: existing tags keep their id, `post_count` takes the
  max, new tags land as `unreviewed`.
- `analyze_posts.py` (6.7M posts, ~25 min) refreshes `tag.post_count`, derives
  `tag_content_label` from the rating histogram and lift-based
  `tag_relation(compatible)` rows (lift ≥ 5), and lists unknown tags.
- Wiki importers turn wiki text into `tag_source` metadata, `recommends`/`conflicts`
  relations and additional `visual_concept` groups.
- Local importers read `--file`/`--dir` or `N2A_DATA_DIR` (fallback `data/imports/`);
  no personal machine paths in code.
- `prune_tags.py` drops unreferenced zero-post tags; `cleanup_db.py` merges aliases
  that duplicate real tags and vacuums.
- `check_reseed.py` reseeds every `data/plans/*.json` and asserts idempotency
  (unchanged prompt files, no loose aliases, clean FK). Run after any catalog edit.

## Plan rules (`etl/wardrobe.py`, applied by seed_plan)

- **Colour lock:** colour data lives in the catalog (`visual_concept` code
  `WC_<garment>` + `concept_tag`), not in code. `import_colour_sets.py --apply` loads
  real `<colour>_<garment>` variants, phase-1 defaults (`data/wardrobe/colour_choice.json`)
  and the `<colour>_clothing` cue (`data/wardrobe/colour_cue.json`). Priority:
  **explicit shot colour > explicit act colour > underwear catalog preset > set heuristic**.
  A garment without a colour decision is never guessed — it is reported
  (`chua chon mau`, QA axis `mau_thieu`). Undies follow the set colour unless declared.
- **Stance:** `wardrobe.lock_poses()` is a read-only checker (stance conflicts in one
  frame); cross-shot stance changes are narrative events — fix the plan, not the code.
- Plans may use tag *names* only; stale plan tag ids are replaced with the catalog id.

## Story QC chain

1. `python etl/plan_actions.py --plan <plan>` — missing action/pose bridges.
2. `python etl/check_story.py --plan <plan>` — full narrative validator, must be clean.
3. `python etl/seed_plan.py <plan> --dry-run` — tag resolution against the catalog.
4. `python etl/seed_plan.py <plan>` — DB upsert + prompt file publish (atomic, outbox
   row in `act_publication`).
5. `python etl/check_prompts.py` — file-vs-DB diff, syntax, missing/extra/repeated
   tags, conflicts, cast counts, length, duplicates, negative line.
6. `python etl/qa_shots.py --apply` — advisory findings into `shot_finding`
   (`source='qa:v1'`); never edits prompts or blocks seed.
7. `python etl/llm_review.py --act N --apply` — semantic review (caption vs tags,
   colour flips inside a beat, wrong-character tags); advisory, stored in
   `data/reviews/`.

Observations are non-destructive: `etl/infer_state.py` writes continuity inference to
`shot_observation`/`act_observation` (migration 004) and never edits confirmed
`shot_state`/`act_continuity`; default is report-only, `--apply` writes only the
`inferred:*` rows it owns.

## Blind mode (story first, cast later)

`etl/bind_character.py` + the `novel2anima-blind-story` skill let you plan an act
before choosing characters. Cast entries are role slots (`LEAD`, `PARTNER_A`) with
`role: "placeholder"`, generic adult appearance anchors and no canon tags; shots
render normally. Two outfit states (full / nude + accessories) are supported by the
phase contract (`wardrobe: dressed|nude`).

```text
python etl/bind_character.py --list asuna          # find character_profile codes
python etl/bind_character.py --plan data/plans/blind.json --slot LEAD \
    --character ba_asuna_blue_archive --project-id 1 --dry-run
python etl/bind_character.py --plan data/plans/blind.json --slot LEAD \
    --character ba_asuna_blue_archive --project-id 1
python etl/seed_plan.py data/plans/blind.json      # reseed after binding
```

- Replaces `identity_json`/`outfit_json` from the DB and renames the slot code in
  every reference (participants, actions/poses/gaze/targets, expressions, reactions,
  `sequence.actor/target`).
- Works on any plan, not only blind ones (use `--force` when the slot already has a
  real identity). Display name is derived from the DB canon tag.
- Refuses: non-placeholder slot without `--force`, a code already bound in the plan,
  and codes ambiguous across projects without `--project-id`. Plan-level ERRORs abort
  the write.
- After a rebind, increment `act.revision` before reseeding if generated/approved
  images exist; captions still contain the old character name and need manual edits.

## Tests

```text
python -m unittest discover -s tests
```

76+ tests, stdlib `unittest` only. Includes: ActSpec fixtures compile without a DB
(`act_specs/`), story contract/interaction-direction regressions, tag roles,
infer-state rules, migrations, layout, prompt QA, and bind-character behaviour
(temp DB, rename coverage).

## Deliberate limits (not done yet)

- **Danbooru API sync** (`tags.json`/`aliases.json`/`tag_implications.json`) returns
  HTTP 403 from this network; the implication map uses the published 2026-08-22
  snapshot. Add a keyset-pagination client when an API key is available.
- **No action/expression concepts derived from taxonomy yet** — `visual_concept`
  holds only the 297 pose-group seeds (all `draft`, `contextual`). P2 curation
  (approve, `neutral`/`adult`/`blocked` scopes, `CONFLICTS_WITH`) is pending; the
  colour-lock `WC_*` concepts are likewise not yet loaded into this DB.
- **No retrieval/ranking API, no ComfyUI orchestration service** (P3–P5).
- Alias conflicts are resolved first-writer-wins (implications db first); losing CSV
  aliases are counted in load stats, not stored.
- `data/sources/` is gitignored and refetchable. `db/novel_anima.db` is a build
  artifact, not tracked: rebuilding is `python etl/build.py all` + re-seed. The
  implications snapshot is a weak pin (site rebuild changes bytes) — the manifest
  hash is authoritative.

## Layout

```text
sql/schema_v1.sql          DDL (16 tables + FTS5 + triggers)
sql/migrations/            002 shot_state, 003 shot_finding, 004 observation/publication
data/characters/           rosters (Blue Archive, DxD) → character_profile
data/plans/                built plan JSONs (gitignored working artifacts)
data/wardrobe/             colour defaults + cue tables for phase 1
act_specs/                 tracked hand-authored ActSpec fixtures (solo/duo/blind/CI)
act_tools/                 local-only act workspace (gitignored)
etl/build.py               schema / fetch / load / verify
etl/story_logic.py         shared narrative validator (pure, no DB)
etl/build_story_plan.py    beats[] → shots plan compiler
etl/plan_actions.py        narrative bridge checker
etl/check_story.py         plan-level story gate
etl/seed_plan.py           validate → resolve → upsert → publish prompts
etl/wardrobe.py            colour table, colourize, stance checker
etl/bind_character.py      bind/rebind a cast slot to a character_profile row
etl/check_prompts.py       prompt-file vs DB/catalog gate (0 error before render)
etl/qa_shots.py            advisory findings into shot_finding
etl/llm_review.py          semantic LLM review (codex exec via stdin, JSON)
etl/infer_state.py         non-destructive continuity observations
etl/suggest_tags.py        tag suggestions from relations/concepts/roles
etl/state_rules.py         continuity inference policy (RULES_VERSION)
etl/tag_roles.py           versioned body-state tag overrides
db/novel_anima.db          built catalog (gitignored, not tracked)
db/import_report.json      counts + check results from the last verify
out/prompts/               published prompt/negative files per plan
skills/                    novel2anima-catalog, novel2anima-shot-pipeline,
                           novel2anima-blind-story, novel2anima-natural-language-prompt
tests/                     stdlib unittest suite
```

## Git / disk maintenance

```text
git lfs prune                 # drop LFS objects nothing points to
del .git\lfs\tmp\*            # LFS scratch (safe when no git/lfs is running)
python etl/build.py verify    # 13 checks
```

Keeping `db/` out of git is a hard requirement: a 327 MB database re-stages on every
git operation and bloats `.git/lfs/tmp` by hundreds of MB. To publish a checkpoint on
purpose: `git add -f db/novel_anima.db` (the LFS filter in `.gitattributes` applies).
