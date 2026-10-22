# Novel2Anima - V4 rebuild

> V4 code lives under `src/novel2anima/`; the legacy `etl/` tree is removed.
> The SQLite DB is canonical for projects, prompts, renders and QA. Start at
> [`docs/v4/README.md`](docs/v4/README.md).
>
> V4.1 story execution is governed by `src/novel2anima/pipeline/orchestrator.py`
> and migration `sql/migrations/013_execution_control.sql`. Catalog maintenance is
> operator-only via `scripts/catalog/run_job.py`; it is never a story substep.
> The pipeline gate is `scripts/release/release_gate_v41.py`.

## Catalog build (P0 schema + P1 import)

Local SQLite catalog for the Novel2Anima pipeline: raw Danbooru tags, curated visual
concepts and the runtime tables, in one file. No PostgreSQL, no vector DB.

## Run

    python -m novel2anima.catalog.build_service all        # schema -> fetch -> load -> verify
    python -m novel2anima.catalog.build_service fetch      # download pinned sources into data/sources/ (sha256 manifest)
    python -m novel2anima.catalog.build_service load       # idempotent import into db/novel_anima.db
    python -m novel2anima.catalog.build_service verify     # integrity_check / foreign_key_check / FTS5 / row gates
    python -m novel2anima.catalog.build_service schema --force   # drop and rebuild the db from sql/schema_v1.sql
    python -m novel2anima.pipeline.plan_seeder data/characters/dxd_roster.json   # roster-only: upserts character_profile, writes no shots

Python 3.9+ stdlib only (`sqlite3`, `urllib`, `csv`, `json`). SQLite must have FTS5.

## What is in the db (measured, 2026-10-22)

| table | rows | source |
|---|---|---|
| `tag` | 1,208,773 | implications db + taxonomy CSV + Anima index + Danbooru dump |
| `tag_alias` | 149,546 | Danbooru active aliases + CSV aliases, first-writer-wins |
| `tag_relation` | 213,175 | Danbooru implications + compatibility edges |
| `tag_role` | 30,265 | taxonomy `slot` mapping |
| `tag_content_label` | 9,994 | rating/content classification |
| `visual_concept` | 583 | Anima-Tools groups and curated concepts |
| `concept_tag` | 9,741 | primary/optional tag per concept |
| `tag_source` | 1,479,995 | provenance row per (tag, source, ref) |

Verified on the current live/staging copies: `integrity_check` ok, 0 foreign-key
violations, project rows 0, catalog preserved at 1,208,773 tags. Rerunning `load`
(and `load --force`) changes nothing: imports are keyed on
`source_snapshot(source_key, revision)`.

## Pinned sources (`config/catalog/sources.json`)

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

## Local Danbooru dump (`python -m novel2anima.catalog.importers.danbooru_dump`)

`python -m novel2anima.catalog.importers.danbooru_dump [--dir DIR] [--only tags,aliases,implications,artists]`
imports the official Danbooru CSV dumps (`tags.csv.gz`, `tag_aliases.csv.gz`,
`tag_implications.csv.gz`, `artists.csv.gz`) straight from disk. Each file is hashed into
`source_snapshot`, so reruns are idempotent: existing tags keep their id, `post_count`
takes the max, new tags land as `unreviewed`. No schema change, no invented ids.

`python -m novel2anima.catalog.importers.analyze_posts [--file PATH] [--limit N] [--pair-every 8] [--dry-run]`
(6.7M post, ~25 min): cap nhat `tag.post_count` theo so post that, sinh `tag_content_label`
tu histogram rating (adult/contextual/neutral), sinh `tag_relation(relation='compatible')`
theo lift co-occurrence (chi giu lift >= 5), va liet ke tag thieu ra
`data/sources/posts_unknown_tags.txt`.
`python -m novel2anima.catalog.importers.unknown_tags [--min-count 5]`: nap cac tag thieu do vao bang tag
(category NULL vi khong biet, post_count = so lan xuat hien).

`python -m novel2anima.catalog.importers.wiki_pages [--file PATH]`: wiki text -> tag_source metadata.
`python -m novel2anima.catalog.importers.wiki_links [--reset]`: wiki sections -> tag_relation
("related tags"/"see also" = recommends, "not to be confused with"/"should not be tagged as" =
conflicts) + under_debate flag trong tag_source.
`python -m novel2anima.catalog.importers.wiki_groups`: 48 page `tag_group:*` (4 nhom e621 bi skip) -> visual_concept kind=other
+ concept_tag (palette theo nhom: clothes, colors, anatomy, sex_positions...).
Moi importer local nhan `--file`/`--dir`; mac dinh lay tu `N2A_DATA_DIR` (fallback
`data/imports/`), khong con duong dan may ca nhan trong code.
`python -m novel2anima.catalog.maintenance.prune_tags [--apply] [--vacuum]`: xoa tag post_count=0 khong duoc
tham chieu o dau (giu tag co wiki/role/relation/concept/alias hoac duoc nhac trong plan).
`python -m novel2anima.catalog.maintenance.cleanup_db [--apply] [--vacuum]`: xoa alias trung ten tag that (tag thang alias),
xuat `data/sources/tags_not_prompt_token.txt` (tag ky tu dac biet/emoji - van giu trong db) va vacuum.
`python -m scripts.qa.check_reseed`: legacy authoring diagnostic only. It may compare
`data/plans/*.json`, but canonical runtime data is SQLite (`shot_prompt_revision`), not a
prompt file; do not use it as a story endpoint or as canonical state.

## Quy tac chung cho moi plan (`python -m novel2anima.wardrobe.rules`, seed_plan tu ap)

Ca hai quy tac chi ap khi db *biet*, khong hard-code trong code:

- **Khoa mau do**: du lieu mau nam trong catalog — `visual_concept` code `WC_<do>` + `concept_tag`
  (`primary` = do goc, `alternative` = bien the mau, `priority=1` = mau dang chon).
  Nap bang `python -m novel2anima.catalog.importers.colour_sets --apply`: bien the `<mau>_<do>` that trong catalog
  (`black_thighhighs`, `white_shirt`...), bo mau chuan bi cho phase 1
  (`data/wardrobe/colour_choice.json`: `<do> -> <mau>`), va cue `<mau>_clothing` cho do khong co
  bien the mau (`data/wardrobe/colour_cue.json`). seed_plan thay tag do bang bien the mau, noi y
  doi mau theo bo (set den -> `black_panties`). Mon nao chua co quyet dinh mau thi khong doan —
  chi bao `chua chon mau: [...]`.
  Thu tu uu tien mau: **shot explicit > act explicit > catalog preset (chi do lot) > heuristic**.
  Do mac ngoai phai co mau ngay trong plan/act; seed khong tu doan mau tu catalog.
  Heuristic (noi y theo mau bo do) chi chay khi do lot chua co mau o muc cao hon, nen
  `white_panties` khai bao ro trong plan duoc giu nguyen. Override bang `colour_choice`
  (map `<do> -> <mau>`) o `shot` hoac `act`.
- **Tu the**: `wardrobe.lock_poses()` chi la checker read-only (bao nhieu stance xung dot
  trong cung frame), khong sua pose/action. Chuyen tu the giua cac shot la su kien ke chuyen
  hop le; muon sua thi sua plan bang tay.

Thu tu sau `python -m novel2anima.catalog.build_service all`: seed_plan moi plan -> `python -m novel2anima.quality.shot_rules --apply`
-> `python -m novel2anima.quality.prompt_rules` (soat may: file vs db, cu phap, tag thieu/thua/lap, xung dot,
so nguoi, do dai, trung lap, negative, dong `qa:*`)
-> `python -m novel2anima.llm.adapters.review_adapter --act N --apply` (soat nghia bang LLM: caption vs tag, doi mau
giua cac shot, tag gan sai nguoi; ket qua la goi y, luu `data/reviews/`). `python -m scripts.qa.check_reseed`
gom 6 buoc dau va tra ve 0 error.

## Xac dinh van de, khong cung nhac (`python -m novel2anima.quality.shot_rules`, `python -m novel2anima.catalog.retrieval.suggest_tags`)

- `python -m novel2anima.quality.shot_rules --apply`: quet moi shot, ghi van de vao `shot_finding` (axis
  `mau_thieu`, `mau_lech`, `xung_dot`, `tu_the_lech`, `noi_dung_chan`; `source='qa:v1'`).
  Day la lop bao cao de model/nguoi doc roi quyet dinh: khong sua prompt, khong chan seed.
  Moi `(shot, rule, source)` la mot row rieng nen QA va LLM review khong ghi de nhau.
  `infer_state.py` ghi continuity suy luan vao `shot_observation`/`act_observation`
  (migration 004), khong bao gio sua `shot_state`/`act_continuity` da duoc chot;
  mac dinh chi report, them `--apply` moi ghi va chi xoa dong `inferred:*` cua act no xu ly.
  `act_publication` la outbox: `pending=1` giua commit DB va publish file; rerun plan de reconcile.
- `python -m novel2anima.catalog.retrieval.suggest_tags --tag black_thighhighs` (hoac `--shot ID` / `--act 13`): goi y tag
  ngoai tag goc tu `tag_relation` + `concept_tag optional/alternative` + `tag_role`.
- Plan chi can dung *ten* tag: id cu trong plan duoc thay bang id trong catalog (bao
  `id cu trong plan -> lay theo ten: N ref`); chi ten khong co trong catalog moi bi tu choi.

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
- `data/sources/` is gitignored: `python -m novel2anima.catalog.build_service fetch` refetches it. `db/novel_anima.db`
  is a **build artifact, not tracked** (gitignored): rebuild it with `python -m novel2anima.catalog.build_service all`
  then re-seed the plans. Committing a 327 MB file left ~300 MB of LFS scratch in
  `.git/lfs/tmp` per git operation; to publish a checkpoint on purpose use
  `git add -f db/novel_anima.db` (the LFS filter in `.gitattributes` still applies).
  The implications snapshot is a weak pin (site rebuild changes bytes), so the manifest hash
  is the authoritative record.

## Bao tri (git / dia)

    git lfs prune                 # xoa LFS object khong con ref nao tro toi
    del .git\lfs\tmp\*            # scratch cua LFS (an toan khi khong co git/lfs dang chay)
    python -m novel2anima.catalog.build_service verify    # 13 checks

Giu `db/` ngoai git la yeu cau: file 327 MB bi stage lai moi lan git thao tac, sinh ra
hang tram GB trong `.git/lfs/tmp`.

## Layout

    sql/schema_v1.sql      DDL (16 tables + FTS5 + triggers), from the V1 schema-only db
    data/characters/       character roster (dxd_roster.json) -> character_profile
    act_specs/             tracked hand-authored ActSpec fixtures (solo + duo, CI)
    act_tools/             local-only act workspace (gitignored; generated by act runs)
    config/catalog/sources.json       pinned source list
    python -m novel2anima.catalog.build_service           schema / fetch / load / verify
    python -m novel2anima.catalog.tag_roles       one versioned source for body-state tag overrides
    python -m novel2anima.continuity.rules     continuity inference policy (RULES_VERSION)
    db/novel_anima.db      built catalog (gitignored, khong track)
    db/import_report.json  counts + check results from the last verify
    python -m novel2anima.quality.prompt_rules   self-check prompt cua mot act (0 error moi render)
    python -m novel2anima.llm.adapters.review_adapter      soat prompt bang LLM (codex exec qua stdin, JSON)
    data/sources/          raw downloads + sha256 manifest (gitignored)
    skills/                novel2anima-catalog + novel2anima-shot-pipeline (skill specs)
