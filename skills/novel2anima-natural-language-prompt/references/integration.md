# Integration of natural-language prompts — V4.1

This replaces the legacy JSONL/`etl/seed_plan.py` integration design. In `V4_ACTIVE`,
use optional registered stage `08_natural_prompt` after deterministic prompt compilation
and before downstream QA/render. The stage requires an approved DB template and schema.

## Inputs

- `shot_id`, source `shot_spec_revision_id`, `source_prompt_revision_id`,
  participant/actor-target bindings, outfit revision IDs and reference/anchor hashes.
- Immutable source positive/negative prompts and separate technical tokens.
- `llm_prompt_template` ID/revision, model/provider policy and
  `pipeline_run`/`pipeline_step_run` identity.

## Outputs

- A schema-validated proposal (`natural_prompt`, `issues`, `status`,
  `source_revision_refs`). The application persists a derived `shot_prompt_revision`
  with linkage to source, plus `llm_run` history; the skill does not write the DB.
- Source negative prompt and weighted/render-specific controls remain separate and
  unchanged.
- On ambiguous actor/target or missing garment detail, mark `NEEDS_REVIEW` and skip
  automatic rendering.

## Forbidden

- Do not produce file JSONL/TXT as the canonical current prompt, run `etl/*`, modify an
  approved prompt, or create a story, DB table or arbitrary new stage.
- `LEGACY` standalone transformation may return plain prose without claiming any DB
  write occurred.

## Test

Use single female, duo actor-target wave/headpat, ambiguous `2girls`, unknown garment,
fixed framing and technical-token fixtures. Verify no role swap, wardrobe drift, scene
addition or negative-prompt mutation. Render benchmark only after integration controls
are proven.
