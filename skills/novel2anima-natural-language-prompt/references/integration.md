# Integration reference — proposed, not installed

## Existing repository interfaces to inspect

As of the public repository review on 2026-10-20, the Novel2Anima README and shot-pipeline reference mention:

- `skills/novel2anima-shot-pipeline/SKILL.md`: upstream ShotSpec and render pipeline guidance.
- `skills/novel2anima-catalog/SKILL.md`: tag meanings, aliases, roles, concepts, source provenance.
- `python -m novel2anima.pipeline.plan_seeder`, `python -m novel2anima.wardrobe.rules`: upstream prompt/tag and garment work.
- `python -m novel2anima.quality.prompt_rules`: tag-string and database alignment checks; not suitable as a gate for prose equivalence.
- `python -m novel2anima.llm.adapters.review_adapter`: LLM advisory review of caption vs tags and character/continuity issues.

Verify the actual checkout before editing. README/skill references may describe planned rather than deployed features, and available model configurations can differ from those examples.

## Suggested handoff, not a database migration

Call the converter once per shot **after the original tag prompt passes its existing checks**. Give it the original shot facts and compiled tags. Preserve both forms and choose a render-time prompt mode explicitly.

```json
{
  "shotId": "ACT01_SH001",
  "compiled_tag_prompt": "...",
  "shotSpec": {
    "participants": [],
    "primaryAction": null,
    "expressions": {},
    "pose": null,
    "camera": null,
    "background": null,
    "carry": {},
    "delta": {}
  },
  "characterProfiles": [],
  "projectDefaults": {},
  "negativePrompt": "...",
  "renderProfile": {
    "model": "anima-3.8b",
    "promptMode": "natural",
    "requiredTokens": []
  }
}
```

This is an **illustrative adapter DTO**. Align the actual names and fields with existing JSON; do not add SQLite columns on the assumption that these exact names exist. `anima-3.8b` is an example target profile, not confirmation of a deployed model configuration.

## Proposed output mapping

- Store `natural_prompt` in a new **derived artifact** (e.g. one JSONL row per shot) keyed by actual shot ID and source revision/hash.
- Keep `compiled_tag_prompt`, canonical tag IDs, and `negativePrompt` unchanged.
- Keep `status`, `issues`, `technical_tokens`, model/workflow version, and converter revision for audit/reproducibility.
- Only feed `natural_prompt` to the renderer when `status == PASS` and that render mode is configured.
- `NEEDS_REVIEW` requires resolution or explicit human sign-off in a separately audited workflow; `BLOCKED` must not auto-render.
- For multi-shot acts, maintain 1:1 shot-to-output mapping; conversion never merges adjacent shots.
- When re-seeding or changing a shot, regenerate the derived prompt from that shot's new revision, but **do not delete previous generation or approval history**.

## Compatibility warning

An existing `check_prompts.py` reportedly expects *every canonical tag* to appear literally in the compiled prompt and its file contents to match the DB. Replacing that field with prose causes a **false failure**. The correct architecture keeps the source tag prompt, validates it with the original checker, then independently checks semantic fidelity of prose.

Likewise, do not automatically pass `technical_tokens` as prose: the render adapter must decide whether to retain a special-token hybrid prefix, native metadata, or reject unsupported controls.

## Minimal acceptance tests

1. Source input and compiled prompt unchanged byte-for-byte after conversion.
2. Solo output is complete prose with action and expression when those exist in the source.
3. Multi-subject output preserves distinct names, actor/target and per-subject appearance.
4. No new visual or story details absent from explicit source/defaults.
5. Conflicting or unbound roles return review/block status; no silent choices.
6. Repeated conversion of identical inputs/configuration yields identical semantic result or records any nondeterministic revision.
7. Render logs contain the *actual* prompt used and a reference to its canonical source.
8. Both original tag-mode and new NL-mode workflows remain independently selectable until comparative QC is performed.
