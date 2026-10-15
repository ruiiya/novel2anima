# Novel2Anima — SQLite build (P0 schema + P1 import)

Local SQLite catalog for the Novel2Anima pipeline: raw Danbooru tags, curated visual
concepts and the runtime tables, in one file. No PostgreSQL, no vector DB.

## Run

    python etl/build.py all        # schema -> fetch -> load -> verify
    python etl/build.py fetch      # download pinned sources into data/sources/ (sha256 manifest)
    python etl/build.py load       # idempotent import into db/novel_anima.db
    python etl/build.py verify     # integrity_check / foreign_key_check / FTS5 / row gates
    python etl/build.py schema --force   # drop and rebuild the db from sql/schema_v1.sql

Python 3.9+ stdlib only (`sqlite3`, `urllib`, `csv`, `json`). SQLite must have FTS5.

## What is in the db (measured, 2026-10-15)

| table | rows | source |
|---|---|---|
| `tag` | 280,100 | implications db + taxonomy CSV + Anima index |
| `tag_alias` | 49,340 | Danbooru active aliases (40,732) + CSV aliases, first-writer-wins |
| `tag_relation` | 45,501 | Danbooru active `implies` edges |
| `tag_role` | 30,265 | taxonomy `slot` mapping: outfit 12,028 / other 6,927 / identity 3,496 / pose 2,976 / action 1,354 / ... |
| `tag_content_label` | 548 | Anima `banned_tags.csv` -> `scope='blocked'` |
| `visual_concept` | 297 | Anima-Tools pose groups (draft, `contextual`) |
| `concept_tag` | 514 | primary/optional tag per concept |
| `tag_source` | 387,997 | provenance row per (tag, source, ref) |

Verified: `integrity_check` ok, 0 foreign-key violations, FTS5 index == concept rows,
`MATCH 'pose'` returns 297. Rerunning `load` (and `load --force`) changes nothing:
imports are keyed on `source_snapshot(source_key, revision)`.

## Pinned sources (`etl/sources.json`)

| key | pin | use |
|---|---|---|
| `danbooru_implications` | content sha256 (site rebuild) | aliases, implications, tag census |
| `danbooru_taxonomy` | HF revision `1fc970c9` | category/slot/confidence, post counts, aliases |
| `anima_tag_index` | commit `77fba841` | Anima naming, post counts, banned artists |
| `anima_wardrobe` | commit `e049b034` | attire slots, pose/expression/clothing vocabulary |
| `anima_tools` | commit `f9c0fd57` | pose groups -> `visual_concept` seeds |

Every download is hashed into `data/sources/manifest.json`; `load`/`verify` run offline
from that cache. Licenses are recorded per source in `sources.json` and copied into
`source_snapshot.license_note` — check them before redistribution.

## Deliberate limits (not done yet)

- **Danbooru API sync** (`tags.json` / `aliases.json` / `tag_implications.json`) returns
  HTTP 403 from this network, so the implication map is taken from the published
  2026-08-22 snapshot instead of a live sync. Add a keyset-pagination client when a
  Danbooru API key is available.
- **No action/expression concepts derived from taxonomy yet** — `visual_concept` holds
  only the 297 pose-group seeds, all `review_status='draft'`, `content_scope='contextual'`.
  P2 curation (approve concepts, set `neutral`/`adult`/`blocked`, add `CONFLICTS_WITH`)
  is the next task; `verify` reports the pending count.
- **No retrieval/ranking API, no shot history, no ComfyUI orchestration** (P3–P5).
- Alias conflicts (26,653 rows) are resolved first-writer-wins, implications db first.
  Losing CSV aliases are counted in the load stats, not stored.
- `data/sources/` is gitignored: `python etl/build.py fetch` refetches it. `db/novel_anima.db`
  is tracked via Git LFS, so run `git lfs install` before cloning. The implications snapshot
  is a weak pin (site rebuild changes bytes), so the manifest hash is the authoritative record.

## Layout

    sql/schema_v1.sql      DDL (16 tables + FTS5 + triggers), from the V1 schema-only db
    etl/sources.json       pinned source list
    etl/build.py           schema / fetch / load / verify
    db/novel_anima.db      built catalog (Git LFS)
    db/import_report.json  counts + check results from the last verify
    data/sources/          raw downloads + sha256 manifest (gitignored)
    skills/                novel2anima-catalog + novel2anima-shot-pipeline (skill specs)
