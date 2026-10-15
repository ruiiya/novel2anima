# Catalog reference

Table semantics and query examples for the intended `db/novel_anima.db`. An earlier
skill reference claimed **280,100 tags, 49,340 aliases, 45,501 implication edges,
30,265 tag roles and 297 draft concepts** as of 2026-10-15. These are **historical,
unverified claims**, not counts established from a SQLite DB available with this skill.
The user-provided V4 handoff describes an earlier **schema-only** DB state. Run the
actual database audit before reporting live figures.

For all-16-table coverage, multi-lane search, fallback and metrics, see
[full-coverage.md](full-coverage.md). Read the [V4 architecture inventory](v4-architecture.md) when revising the data contract.

## Two different units

- **Tag** - the keyword the image model sees: canonical name, alias, role, popularity, provenance.
- **Visual concept** - the meaning the LLM and the shot planner reason about
  (`ACTION_SUDDEN_TURN`, `EXPR_SURPRISED`). Many tags per concept (`primary`/`optional`/`alternative`);
  a tag can hold several roles. Never stuff every synonym of a tag into a prompt.

## Tables

Dictionary: `source_snapshot`, `tag`, `tag_source`, `tag_alias`, `tag_role`, `tag_relation`,
`tag_content_label`.
Curated: `visual_concept`, `concept_tag`, `concept_relation`, `visual_concept_fts` (FTS5, kept in
sync by triggers).
Runtime: `model_profile`, `project`, `character_profile`, `act`, `shot`, `generation`.

`tag_relation.relation`: `implies` comes from Danbooru. `compatible`, `recommends`,
`conflicts` are app-curated judgments - do not derive them from `implies` on the fly.
`concept_relation`: `compatible`, `recommends`, `conflicts`, `subtype_of`.

## Roles

`identity, outfit, action, expression, pose, motion, camera, composition, background, style,
interaction, other`. Seeded from the taxonomy `slot` column:

| slot | role(s) |
|---|---|
| `appearance:*` | identity |
| `clothing:*` | outfit |
| `pose:expression` | expression |
| `pose:camera` | camera |
| `pose:combat` | action |
| `pose:interaction` | interaction, action |
| `pose:gesture` | pose, action |
| `pose:kinetic` | motion |
| `pose:posture`, `pose:physiological` | pose |
| `scenery:setting`, `scenery:atmosphere` | background |
| `scenery:props`, `equipment:*`, `creature:animal` | other |
| characters, copyrights, meta, style, layout, unclassified | no role (dictionary only) |

Curation priority when choosing what to promote into concepts: **action/interaction ->
expression/facial -> pose/gesture -> motion -> camera/composition**.

## Catalog retrieval and metadata

Return raw and curated records with their stored source fields. Include any available
`tag_content_label.scope`, `visual_concept.content_scope` and `review_status` values
verbatim in the response evidence. Catalog retrieval is based on names, aliases, roles,
relations and mappings; preserve provenance across merged records. Sexual-content labels,
including adult consensual explicit tags, are data attributes. Do not suppress or
rename those entries as “romantic” merely because they are sexual. A single tag may
represent an action/interaction plus a pose or expression: keep multi-role mappings.

The historical report of 297 `draft` concepts is unverified without the live DB. When
concepts are unavailable, discover raw tags through canonical/alias/role lookups rather
than converting drafts into approvals or pretending the dictionary is empty.

## Queries that are actually useful

FTS5 concept lookup (name/description/search_terms):

```sql
SELECT c.code, c.kind, c.name, c.content_scope, c.review_status,
       group_concat(t.canonical_name) AS tags
FROM visual_concept_fts f
JOIN visual_concept c ON c.id = f.rowid
LEFT JOIN concept_tag ct ON ct.concept_id = c.id
LEFT JOIN tag t ON t.id = ct.tag_id
WHERE visual_concept_fts MATCH 'kneel*'
GROUP BY c.id;
-- Search all concept statuses; return their original catalog metadata.
```

Candidate tags for a role, most popular first:

```sql
SELECT t.canonical_name, t.post_count, r.confidence,
       t.taxonomy_status, c.scope AS content_scope
FROM tag_role r
JOIN tag t ON t.id = r.tag_id
LEFT JOIN tag_content_label c ON c.tag_id = t.id
WHERE r.role = 'expression'
ORDER BY r.confidence DESC, t.post_count DESC
LIMIT 25;
-- Taxonomy review status is returned but does not govern this lookup.
```

Ingredient set for a concept, plus what each ingredient implies:

```sql
SELECT t.canonical_name AS ingredient, i.canonical_name AS also_implied
FROM concept_tag ct
JOIN tag t ON t.id = ct.tag_id
LEFT JOIN tag_relation r ON r.from_tag_id = t.id AND r.relation = 'implies'
LEFT JOIN tag i ON i.id = r.to_tag_id
WHERE ct.concept_id = (SELECT id FROM visual_concept WHERE code = 'POSE_KNEELING');
```

Resolve an alias, and inspect stored tag metadata:

```sql
SELECT t.canonical_name, t.post_count, t.taxonomy_status
FROM tag_alias a JOIN tag t ON t.id = a.tag_id WHERE a.alias_name = 'kemonomimi';

SELECT t.canonical_name, c.scope, c.rationale
FROM tag t LEFT JOIN tag_content_label c ON c.tag_id = t.id
WHERE t.canonical_name = 'white_background';
```

`visual_concept_fts` is an external-content FTS5 table: after bulk writes outside the triggers,
run `INSERT INTO visual_concept_fts(visual_concept_fts) VALUES('rebuild')` (build.py does this).

## Source map

| key | pin type | what it contributes |
|---|---|---|
| `danbooru_implications` | content sha256 (weak) | aliases, `implies` edges, full tag census (name/category/post_count) |
| `danbooru_taxonomy` | HF revision | category/subcategory/slot/confidence, post counts, aliases |
| `anima_tag_index` | git commit | Anima naming, post counts, source-specific index metadata |
| `anima_wardrobe` | git commit | attire slots, pose/expression/clothing vocabulary (roles only) |
| `anima_tools` | git commit | pose groups -> concept seeds (images are never imported) |

Live Danbooru API sync (`tags.json`, `aliases.json`, `tag_implications.json`) returned HTTP 403
from this network; add a keyset-pagination client only when a working endpoint or API key exists.
