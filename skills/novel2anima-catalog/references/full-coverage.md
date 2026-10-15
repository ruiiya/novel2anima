# V4 SQLite full-coverage contract

The goal is **lossless reachability of imported catalog data** and meaningful use of all
relevant data during generation planning, not placing every tag in a single Anima prompt.
This is a **design contract**, not proof that the live SQLite contains the sources, tables,
or rows. Inspect the DB and source manifests first.

## 1. Stage-to-table matrix (16 data tables + FTS5)

| Database object | Primary use; must not be ignored | Observability / verification |
|---|---|---|
| `source_snapshot` | source revision, pinned provenance, content/license manifest | all 5 source families accounted for, pins present |
| `tag` | canonical keyword, category/popularity/taxonomy properties | counts, reachable tagged words, zero-result/fallback tests |
| `tag_source` | multiple independent source sightings/evidence for tag | provenance count and source disagreement audit |
| `tag_alias` | normalize user/LLM terms and spelling variants to canonical | alias hit rate; collisions with reported resolution |
| `tag_role` | action, interaction, expression, pose, motion, camera, identity, outfit, etc.; multi-role | counts per role, role coverage, unmapped tags |
| `tag_relation` | directed `implies`; app-reviewed compatible/recommends/conflicts where present | edges by type, expansions, cyclic/invalid links |
| `tag_content_label` | original source/catalog labels and rationale metadata | label coverage and NULL/missing-value audit |
| `visual_concept` | semantic action/expression etc.; retain provisional status | counts by kind, review status, unmatched query |
| `concept_tag` | concept → primary/optional/alternative tag candidates | concepts with zero tags, multiple alternatives |
| `concept_relation` | reviewed compatible/recommends/conflicts/subtype_of links | relation integrity, useful supported expansions |
| `visual_concept_fts` | FTS5 search over concept name/description/terms | FTS freshness and query recall smoke tests |
| `model_profile` | actual prompt/render target capabilities/configuration | profile active, model and profile version captured |
| `project` | creative style, white background and continuity | shot plan resolves to a real project |
| `character_profile` | canonical identity/outfit/style constraints | no identity drift from ungrounded LLM guesses |
| `act` | beat sequence, current act and global outline | proper scoped continuity and act handoff |
| `shot` | planned/generated/reviewed variants, signatures and full history | last 5–10 + act + project novelty scores |
| `generation` | actual seeds, prompts, config, image QC and human feedback | only approved outcomes train accepted-history preference |

**Scope:** The tables serve different stages. A raw dictionary browsing request need not
read `generation`; a prompt candidate decision does need project context/history when they
exist. Report 'not applicable', 'empty table', 'unavailable', and 'not yet integrated'
distinctly. Do not claim a table was used just because it was joined once.

## 2. Source-contribution audit

- Taxonomy → `tag`, `tag_source`, `tag_alias`, `tag_role` (subject to actual source schema).
- Good-Anima index → canonical/variant spellings and source confidence/popularity evidence;
  never claim model competence solely from frequency.
- Wardrobe presets/rules → relevant pose/expression/outfit vocabulary and slot constraints,
  mapped to `tag_role`/`visual_concept`/metadata while preserving source-specific fields.
- Anima Tools → pose/action concept seeds and tag variants; record whether preview images
  were deliberately skipped for rights reasons.
- Implication map → tag census, aliases, directed `tag_relation(relation='implies')`.

If a source cannot be represented faithfully in the 16-table V1 schema, report
`SCHEMA_COVERAGE_GAP` with the missing fields (e.g., raw preset rule logic) and propose a
versioned migration or a clearly documented JSON mapping. Do not invent an existing table,
flatten away usable rule semantics, or silently ignore these contributions.

Maintain a contribution report containing source key, source revision, file hash, parser,
import counts/upserts/conflicts, covered tables, unmapped records, and licensing status.
Re-running ETL with the **same pinned snapshot** must create no duplicates; provenance
must still reflect all independent sources.

## 3. Candidate acquisition: seven complementary lanes

**Lane A — Concept lexical/FTS.** Query `visual_concept_fts` joined to `visual_concept`
and `concept_tag`. Include `approved` and `draft` in *discovery*; FTS misses must not imply
there is no matching tag.

**Lane B — Raw canonical/tag lexical.** Normalize spaces vs underscores, use exact then
indexed prefix lookups, and only bounded broader matching. Do not require a concept row.

**Lane C — Aliases and source spellings.** Follow `tag_alias` to canonical ID; attach all
`tag_source` sightings and resolved spellings. Alias conflict resolution must be traced.

**Lane D — Roles/slots.** Use multi-valued `tag_role` to discover action/interaction and
expression first; then pose/gesture/motion/camera, wardrobe/outfit/identity/style/background
as constraints. Role and category evidence complement rather than overwrite each other.

**Lane E — Relations.** At most one hop by default (two only with measured benefit).
`IMPLIES` is directed and only supports implication/redundancy reasoning; it is
not evidence of compatibility or a complete assessment of a shot.
`RECOMMENDS`/`COMPATIBLE`/`CONFLICTS` apply **only** if curated and present. Evaluate both incoming/outgoing edges where semantics call for it, never
blindly assume symmetry.

**Lane F — Curated seeds, presets and variants.** Examine concepts mapped from Wardrobe
and Anima Tools, including `draft` for discovery; preserve alternate tag forms and
applicable slot arbitration. Report any preset rules lost in the importer.

**Lane G — Memory and measured render feedback.** `shot` is the novelty source;
`generation` supplies actual QC/review, successful configurations and per-concept failure
patterns. They affect reranking, retry decisions and diversity, not raw dictionary
membership. Cold-start DBs must report absence of feedback instead of fabricating scores.

Retrieve enough candidates from **each viable lane** before reranking; use explicit
limits configurable by role/batch, not an undifferentiated global `LIMIT 10` that lets
popular tags starve action/expression. This applies equally to explicit adult sexual
interaction tags: do not search only euphemisms, return a SFW-only shortlist, or impose
a hidden content-rating threshold in SQL/FTS/ETL. Merge by canonical tag and
concept IDs while preserving multiple evidence paths. Then take top candidates per required role/shot.

## 4. Candidate response contract (application DTO, NOT assumed V1 SQL columns)

```json
{
  "canonicalTagId": 123,
  "canonicalTag": "looking_back",
  "conceptCode": "ACTION_SUDDEN_TURN",
  "roleMatches": ["action", "pose"],
  "evidence": [
    {"lane": "alias", "sourceKey": "danbooru_taxonomy", "revision": "<pin>"},
    {"lane": "concept_mapping", "mapping": "primary"}
  ],
  "sourceMetadata": {"contentScope": "<original_db_value>", "reviewStatus": "draft"},
  "curationState": "provisional",
  "relevance": {"action": 0.9, "expression": 0.1},
  "noveltyEvidence": {"approvedPairOccurrencesInAct": 0}
}
```

This is an **illustrative DTO**; scores are examples, not output from an actual DB.
Attach source provenance, curation confidence and meaningful selection/ranking reasons.
A candidate omitted from a short prompt remains queryable in the catalog.

## 5. Catalog metadata and curation

- Preserve source-specific fields as original data; keep raw values intact through ETL
  and retrieval, including source scales and missing-value markers.
- `review_status`/taxonomy status expresses editorial progress. Include `draft` and
  `unreviewed` in discovery with their original values. Editorial promotion is a
  separate, auditable workflow, not an implicit effect of search or generation.
- Maintain source provenance, license/use conditions and original grading scales; do not
  automatically convert Danbooru G/S/Q/E to Wardrobe 0–4.
- The shot-planning LLM makes contextual creative selections from this evidence.
- NSFW may include adult sexual activity; it is not synonymous with nudity, lingerie,
  flirting or suggestive posing. Preserve original sexual concepts in the result set.
  `contentProfile` describes project/shot intent and does not discard raw data at import.
- Separate source/catalog coverage from model output eligibility: a catalog hit is not
  proof that any particular assistant or image service may emit the corresponding output.

## 6. SQLite query patterns (verify schema/indexes locally first)

```sql
-- Real table existence and columns first. V4 documents intent, not a DB snapshot.
SELECT name, type FROM sqlite_master WHERE type IN ('table', 'view') ORDER BY name;
PRAGMA table_info(tag);
PRAGMA table_info(visual_concept);
PRAGMA foreign_key_check;
PRAGMA integrity_check;
```

```sql
-- Raw role fallback; do not require concept mapping or a category-wide filter.
SELECT t.id, t.canonical_name, r.role, r.confidence,
       t.post_count, t.taxonomy_status
FROM tag_role AS r
JOIN tag AS t ON t.id = r.tag_id
WHERE r.role IN ('action', 'interaction', 'expression')
ORDER BY r.confidence DESC, t.post_count DESC
LIMIT 100;
```

```sql
-- Concept FTS discovery; requires the reference's V1 FTS shape.
SELECT c.id, c.code, c.kind, c.content_scope, c.review_status
FROM visual_concept_fts
JOIN visual_concept c ON c.id = visual_concept_fts.rowid
WHERE visual_concept_fts MATCH 'turn*'
LIMIT 100;
```

```sql
-- Alias resolution with provenance kept available for later evidence enrichment.
SELECT a.alias_name, t.id, t.canonical_name
FROM tag_alias a JOIN tag t ON t.id = a.tag_id
WHERE a.alias_name = 'looking_back';
```

Do not run a broad FTS rebuild when no write occurred; rebuild after bulk import that
bypassed normal synchronization and validate FTS counts/samples. FTS5 indexes **concept
text** in V1, not every raw tag. Never claim FTS alone covers the entire raw dictionary.

## 7. Coverage and quality gates

Capture for each import/retrieval/release:

- Per-source: pin, checksum, ingested, skipped (with reasons), orphaned, collisions,
  schema coverage and license review.
- Per-table: row count, indexes used where measurable, orphan FK rows, references resolved,
  zero/NULL coverage and last imported snapshot.
- Per-role: candidate counts for action, expression, interaction, pose, motion and camera;
  concept-mapped vs raw-only matches; alias hit rate and relation expansions.
- Per-metadata category: counts for all original labels, statuses and NULLs; keep
  source values intact.
- Per-request: lane hits/unique candidates; action/expression fulfillment; top-K diversity;
  conflict/alias/implied-tag eliminations; how many provisional records required review.
- Across 300–500 simulated shots: primary/secondary signature repetitions at recent, act
  and project scope, approved vs rejected denominators.
- Per-model/feedback: successful vs failed outcomes by tag/concept, prompt/seed/profile
  captured, actual QC failures and error-specific retries.

### Required tests (unit/integration when code + populated DB exist)

1. Same pinned ETL twice → no duplicate canonical/alias/source/relation rows.
2. All five source families have contributions or explicit skip reasons.
3. All stored label values remain searchable without being relabeled or overwritten,
   including NSFW, high-intensity adult group/rough labels and adult sexual activity
   categories (where such records exist).
4. Draft and unreviewed concepts are returned as provisional in discovery.
5. FTS miss + canonical hit, FTS miss + alias hit, and concept-less raw role search succeed.
6. Multi-role tag preserves every role and source sighting.
7. Directed IMPLIES expansion and independent curated conflict resolution behave correctly.
8. Source provenance, import permissions and original metadata remain auditable.
9. DB empty → explicit EMPTY_DB/NOT_IMPORTED state; never return fake candidates.
10. Approved, planned, rejected signatures and generator feedback are distinguished.
11. LLM contextual interpretation must not be confused with catalog editorial approval.
12. 300–500 shot simulation checks novelty windows and does not equate camera-only changes
    with action/expression diversity.

Thresholds for adequate recall, render competence, and scoring calibration are **TBD until
benchmarking**. Do not invent pass rates or measured totals.

## 8. Adult NSFW retrieval regression cases

Use synthetic, non-graphic adult-only fixture labels when no live DB is available.
These tests verify **reachability**, not permission to generate a particular image.

1. Import records labeled `SFW`, `NSFW`, and `adult_sexual` with identical provenance
   handling; confirm row counts and hashes are unchanged after a second import.
2. Resolve adult sexual-action and adult interaction test records through canonical,
   alias, role, concept mapping and relation lookups; ensure original labels survive.
3. When an adult concept is `draft` or absent, return raw-tag candidates and a curation
   gap instead of an empty shortlist; never fabricate verified concept IDs.
4. A query with `contentProfile=NSFW` returns relevant sexual-action records as well as
   their supporting facial expressions, without blanket category exclusion or forced
   conversion into suggestive-only language.
5. A query with `contentProfile=SFW` can still inspect all available catalog evidence;
   final selection should follow the intended scene and external output constraints,
   not permanently erase or mutate source data.
6. For adult-only high-intensity group intent, query `gangbang`, `group_sex` and
   `rough_sex` through canonical, alias and FTS/role routes. Preserve any real hits and
   source labels; if absent, return an explicit catalog gap instead of a sanitized
   substitute or fabricated IDs. Confirm participant tracking is per character in the
   planner and do not impose a source-label-based severity ceiling.
