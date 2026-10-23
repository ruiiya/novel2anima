---
name: novel2anima-blind-story
description: "Blind mode for Novel2Anima: plan acts, beats and ShotSpecs with role placeholders and fixed generic adult appearance anchors when no canonical character has been chosen. Renders placeholder shots without inventing franchise identities and defers binding. Use before novel2anima-shot-pipeline when the user asks for blind mode, unknown cast, or story-first-cast-later."
metadata:
  short-description: Placeholder-cast story planning (blind mode)
---

# Novel2Anima — Blind Story (placeholder cast)

Blind mode writes the story before the cast. Characters are **role slots** with a fixed
generic appearance, not canon identities. Shots render normally; nothing here invents a
franchise, a character name or an ID. This skill is an overlay on
[`novel2anima-shot-pipeline`](../novel2anima-shot-pipeline/SKILL.md): planning rules,
interaction contracts, continuity, wardrobe colours and QC gates stay in force. Catalog
tags still come from `novel2anima-catalog`; never invent a tag.

Read [references/blind-cast-contract.md](references/blind-cast-contract.md) for the exact
plan JSON, the `seed_plan` field mapping and the QA checklist.

## When to use

- User wants to build the story/act/shot list first and pick characters later.
- User gives a premise, role or archetype but no name, franchise or `character_profile`.
- User explicitly says `blind mode`, `chưa chọn nhân vật`, `tạo truyện trước`.

Do **not** use it to rename or disguise a real character the user already named; that is a
normal cast plan in the shot pipeline.

## Contract

1. **`blind_mode: true`** at plan root. Metadata only; the backend ignores unknown keys.
2. **`characters[]` are role slots.**
   - `code`: stable uppercase role (`LEAD`, `PARTNER_A`, `STRANGER_1`). Keep it across acts,
     revisions and reseeds so continuity and shot history stay attached.
   - `name`: render-safe noun (`woman`, `man`, `stranger`), never a franchise/person name.
   - `role: "placeholder"`, and `adult: true` (also `identity_json.adult: true`) whenever
     `content_profile` is `nsfw`/`explicit`; otherwise `CONTENT_SAFETY_BLOCK`.
   - `gender`: set explicitly — `seed_plan` derives `1girl`/`1boy` cast counts from it.
3. **Appearance anchors, not identity.** Put 2–4 generic visual anchors in
   `identity_json.attributes` + `identity_line` (hair, eyes, build, one accessory).
   Leave `identity_json.identity_tags` empty: that is where canon IDs belong.
   Anchors are immutable across the project; a visible change (dye, haircut, scar) is a
   declared beat and an act `revision` bump, exactly like outfit changes.
4. **No canon.** Never add `name_(franchise)`, a character tag, a guessed age, or a "close
   enough" real identity. No implicit binding, no "probably Asuna".
5. **Outfit is per shot.** `outfit_json` may stay `{}`; every named garment still needs a
   colour decision or it is reported by the wardrobe gate. Do not silently repaint.
6. **Per-character roles still apply.** Duo/group shots need `character_actions`,
   `character_poses`, `character_gaze`, `character_targets` and a certified
   `sequence.actor`/`target`; the shared `INTERACTION_*` validator is unchanged.
7. **Render allowed.** Placeholder shots are producible art, not identity proof. Mark the
   project `blind_mode`, mention it in the act outline, and never write "placeholder" into
   a prompt or caption. A later binding may keep the images as reference, not as canon.

## Procedure

1. Take the premise/tone/intensity; propose 3–5 story ideas as in the shot pipeline and
   stop for a pick.
2. Assign role slots and their generic anchors. Retrieve the anchor/outfit/action tags from
   SQLite; report unresolved tags instead of inventing them.
3. Plan beats → shots with the shot pipeline contract (action + expression first, state
   carry/delta, purpose, interaction direction).
4. Emit the seed-compatible plan (see the reference), then run the normal gates:
   `python etl/build_story_plan.py --input <spec> --output <plan>`,
   `python etl/plan_actions.py --plan <plan>`,
   `python etl/check_story.py --plan <plan>`,
   `python etl/seed_plan.py <plan> --dry-run`, then seed and
   `python etl/check_prompts.py`.
5. Report shots as `PLANNED`/`GENERATED` with identity status `PLACEHOLDER`
   (`BLIND_IDENTITY_PLACEHOLDER`, advisory). Hard errors from the shared validators are
   never waived because the cast is blind.
6. **Binding:** choose a `character_profile.code` and run
   `python etl/bind_character.py --plan <plan> --slot LEAD --character <code>`.
   It copies `identity_json`/`outfit_json`, renames the slot and every per-character
   reference (participants, actions/poses/gaze/targets, reactions, `sequence.actor/target`),
   then validates before writing. Use `--list <query>` to find codes and `--project-id`
   when a code exists in several projects. Do not hand-edit bound identity data.
