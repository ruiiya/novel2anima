---
name: novel2anima-catalog
description: "Novel2Anima V4.1 SQLite catalog retrieval, provenance, tag validation and operator-controlled maintenance; no autonomous catalog ETL during story creation."
metadata:
  short-description: DB-first catalog read/retrieve and approved maintenance
---

# Novel2Anima Catalog — V4.1

> **Runtime authority:** SQLite V4.1. See
> [`docs/architecture/PIPELINE_EXECUTION_CONTROL.md`](../../docs/architecture/PIPELINE_EXECUTION_CONTROL.md)
> and [`docs/contracts/SKILL_RUNTIME_CONTRACTS.md`](../../docs/contracts/SKILL_RUNTIME_CONTRACTS.md).
> `src/novel2anima/` is the implementation; the legacy `etl/` tree is removed.
> `shot_finding` and `shot_state` are projections, not canonical authority.
> POC settings and historical counts are not live measurements.

## Story-time use (read-only)

- Retrieve tags/concepts through the approved DB retrieval service. Match exact canonical
  ID, aliases, roles, concepts, relations and provenance; preserve original metadata
  without fabricating tag IDs.
- Return a compact evidence-backed shortlist. Metadata labels, including mature-content
  classifications, must be preserved faithfully; do not substitute a different meaning.
- Missing/misclassified tag → `CURATION_GAP` with candidates and evidence. **Do not**
  call import/rebuild/prune/FTS updates, create an importer script, or modify catalog
  rows as part of `story.start`.
- Keep retrieval relevant to the shot and its participants. A catalog tag is not
  automatically approved for a particular story or equivalent to an outfit anchor.

## Catalog maintenance (separate operator job)

- Allowed only outside `story.start` through
  `python scripts/catalog/run_job.py --db <db> --job <code> --job-key <key>
  --actor <operator> --approved-by <owner>`, with source pins, rights/license review,
  checksum/import ledger and a DB snapshot.
- Historical `etl/*` commands are **legacy references only**. They are not runtime
  endpoints and must not be dispatched by a story LLM stage.
- Administrative import/rebuild/prune records a `catalog_job` ledger row and never
  appears as a `pipeline_step_run` of a story.

## Execution mode

- `LEGACY`: accurately explain current scripts, no fabricated V4 APIs, no auto-created ETL.
- `MIGRATING`: only deployed compatibility adapters with explicit status; a conflicting
  writer → `BLOCKED_DEPENDENCY`.
- `V4_ACTIVE`: application-supplied mode; only registered retrieval/service entrypoints.
  LLM output is proposal data, never SQL/OS commands.

Read [references/v4-architecture.md](references/v4-architecture.md) for the canonical
architecture redirect. See [references/catalog.md](references/catalog.md) for table
meanings and SQL examples, and [references/full-coverage.md](references/full-coverage.md)
for coverage and tests.

## Mission

Maintain **one local SQLite file** (B-tree, JSON, FTS5) holding three connected layers:
`Raw Danbooru/Anima Tags → Visual Concepts → Project/Shot History + Render Feedback`.
Import and search the complete source vocabulary, **including adult sexual/explicit NSFW
terms and high-intensity group/rough labels when present**, without replacing their
meaning with generic romance or suggestiveness. Keep
source-provided fields, original values, editorial statuses and provenance as ordinary
database metadata. NSFW, sexual activity and explicit source categories are part of the
catalog's searchable vocabulary, not automatic reasons to omit records. Semantic and
creative interpretation takes place at shot-planning time, not while importing tags.

**Full coverage ≠ every tag in a prompt.** Every imported record should be reachable and
auditable; retrieval draws on all relevant evidence. Final prompts still need a compact,
consistent choice of supported visual tags.

## Inventory — core 16 catalog/runtime tables plus FTS5

- Import/provenance: `source_snapshot`, `tag_source`.
- Vocabulary: `tag`, `tag_alias`, `tag_role`, `tag_relation`, `tag_content_label`.
- Concepts: `visual_concept`, `concept_tag`, `concept_relation`, `visual_concept_fts`.
- Runtime: `model_profile`, `project`, `character_profile`, `act`, `shot`, `generation`.
- V4.1 orchestration/provenance: `pipeline_run`, `pipeline_run_execution`,
  `pipeline_step_run`, `llm_prompt_template`, `llm_run`, `asset_blob`, `catalog_job`.

Each table has a stage-specific purpose; no individual query needs to join every object.
Canonical shot data lives in `shot_spec_revision`, `shot_participant`,
`shot_interaction` and `shot_outfit_binding`, not in removed JSON columns.

## Derived knowledge stored as concepts (maintenance only)

Some admin catalog edits do not add tables — they add `visual_concept` rows that later
steps read. `data/wardrobe/*.json` is a seed/fixture/import source, not active runtime
configuration; the DB rows are authoritative. Do not run these commands from a story:



- **Outfit colours**: `python -m novel2anima.catalog.importers.colour_sets --apply` writes one `visual_concept`
  per garment (`code='WC_<garment>'`, kind `other`) whose `concept_tag` rows name the base
  garment (`usage='primary'`), the real `<colour>_<garment>` variants (`alternative`) and the
  chosen colour (`priority=1`). Source of truth for the phase-1 decisions is
  `data/wardrobe/colour_choice.json` (`garment -> colour`) plus `colour_cue.json` for garments
  with no colour variant in the catalog. It deletes stale `WC_*` concepts and rebuilds FTS.
- **Wiki-derived grouping**: `python -m novel2anima.catalog.importers.wiki_groups` / `import_wiki_links.py` turn Danbooru
  wiki text into concept tags and `tag_relation` evidence (`from_tag_id`/`to_tag_id`, note kept).
- Tag hygiene: `python -m novel2anima.catalog.maintenance.prune_tags`, `python -m novel2anima.catalog.maintenance.cleanup_db [--apply] [--vacuum]`,
  `python -m novel2anima.catalog.importers.danbooru_dump`, `python -m novel2anima.catalog.importers.unknown_tags`.
Report empty, unmapped and unused domains separately. Do not invent V1 columns or
migrations: inspect `sqlite_master` and `PRAGMA table_info(...)` in the actual DB.
Preserve `tag_content_label`, `content_scope` and `contentProfile` values when they exist;
include them in data exports/retrieval evidence without rewriting source scales. Do not
translate a source label into a global eligibility decision or silently strip explicit
adult records from ETL, FTS-backed concepts, raw-tag lookup, aliases, roles or relations.

## All five source families

1. `Mexes/danbooru-tag-taxonomy`: names, taxonomy, semantic slots, confidence, counts,
   aliases.
2. `ShiroEirin/comfyui-good-anima`: Anima spellings/index variants and popularity evidence.
3. `lingdongbudong/Comfyui-Anima-Wardrobe`: wardrobe, pose and expression presets,
   source-specific metadata/levels. Preserve source-specific meanings.
4. `nregret/Comfyui-Anima-Tools`: pose/action groups and variants; preview assets need
   separate rights review.
5. `grio43/danbooru-implication-map`: aliases and directed `IMPLIES` edges.

Pin revision/commit, SHA256, source/license data and per-source contributions. Imports
must be idempotent, with disagreements kept as evidence, not flattened out. Respect source
licenses and access rights when copying or distributing material.

## Retrieval: comprehensive in reach, selective in output

Use every applicable lane in [references/full-coverage.md](references/full-coverage.md):
concept FTS5; canonical/exact/prefix raw tags; alias normalization; multi-valued roles;
directed relationship expansion; Wardrobe/Tools seeds and variants; provenance; project
history; model profile; generation QC. Dedupe on canonical IDs while retaining *all*
evidence paths. `draft`, `unreviewed`, and unmapped raw records remain **discoverable** with
original metadata and confidence attached. Use all recorded statuses in generic retrieval.
A query for an adult sexual interaction, including group/rough genre intent, must
search action/interaction and expression roles, plus canonical tags, aliases, concepts
and relations, not just clothing/pose/euphemistic vocabulary. Search user-provided labels
such as `gangbang`, `group_sex`, `rough_sex` as canonical/alias/FTS candidates; never
assume they exist or create synthetic tag IDs when the source DB lacks them.

When no curated concept exists, return raw-tag, alias or role candidates and report
`CURATION_GAP`. An editorial status records review progress, not whether a term exists in the catalog.

## Catalog development rules

- Actual package entrypoints: `python -m novel2anima.catalog.build_service <schema|fetch|load|verify>`,
  importers under `python -m novel2anima.catalog.importers.*`, and maintenance under
  `python -m novel2anima.catalog.maintenance.*`. They are admin-only. Check the file and
  DB state before claiming a command exists.
- Catalog ETL stages (admin path): pinned fetch → checksum/license manifest → safely parse
  CSV/JSON/SQLite/JS (never `eval` untrusted JS) → normalize tags/aliases → roles → preset
  mappings → concepts → relations → retain native metadata → FTS5 rebuild →
  integrity/coverage checks. The story path only reads the resulting DB.
- Preserve `tag` (model syntax) versus `visual_concept` (semantic meaning). One concept may
  provide primary/optional/alternative tags; one tag may have multiple roles/concepts.
- `IMPLIES` is not equivalent to `COMPATIBLE` or `CONFLICTS_WITH`; only use curated links
  where they actually exist. Preserve source spellings, popularity and evidence.
- Runtime SQLite: `PRAGMA foreign_keys=ON`, `busy_timeout=5000`, WAL; short transactions,
  one primary writer, no shared WAL across hosts via NFS/SMB; migrations and backups.
- Render bytes are stored in `asset_blob`; `generation` stores the asset reference,
  prompt revision, seed, model settings and decision. Preserve generation revision/history;
  QC rejections are diagnostic evidence and are not approved-history repetitions.

## Runtime story-quality safety

Catalog retrieval does not create story events. Preserve real action/expression tag IDs,
match each action to the intended participant and reaction, and leave missing semantic
mappings explicitly unresolved. No random tag pool can replace a beat → micro-action plan.
A missing mapping is `CURATION_GAP`, never an invitation to write/import tags in the story
process. Preserve prior generation and approved prompt revisions when a plan changes; add
new revisions rather than overwriting history.

## Done criteria

Verify five source pins/manifests, contribution or justified zero contribution, schema
integrity, foreign keys, FTS5, idempotent re-import, and the full stage-to-table matrix.
Test concept, alias, role, relation and raw-tag fallback, including rows of all original
metadata values, including adult sexual categories and unmapped NSFW tags. Check
that history and render feedback can be traced to selected tags and concepts. Report all unimplemented lanes and gaps; never claim a live populated database
or measured model performance without evidence.

With a real SQLite file, run the **read-only** coverage audit:

```bash
python skills/novel2anima-catalog/scripts/sqlite_coverage_audit.py /path/to/novel_anima.db --output coverage-report.json
```

This checks DB structure and counts, not whether the running backend uses the whole DB.
Follow the integration tests in [references/full-coverage.md](references/full-coverage.md).
