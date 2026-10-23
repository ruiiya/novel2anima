# Blind cast contract

Plan JSON for `novel2anima-blind-story`. It is a normal ActSpec for
`etl/build_story_plan.py` / `etl/seed_plan.py`; `blind_mode` and `role` are metadata the
backend ignores. Verified against `etl/story_logic.validate_plan`: a placeholder cast only
needs `code`, `adult` and valid tags — no `identity_json` canon row is required.

## Minimal solo plan

```json
{
  "blind_mode": true,
  "project": {
    "title": "Blind — rainy stairwell",
    "idea": "Story-first draft; cast intentionally unbound.",
    "content_profile": "nsfw",
    "style_json": {"background": "white background"}
  },
  "characters": [
    {
      "code": "LEAD",
      "name": "woman",
      "role": "placeholder",
      "gender": "girl",
      "adult": true,
      "identity_line": "1girl, solo, adult, long hair, black hair, green eyes",
      "identity_json": {
        "adult": true,
        "attributes": ["long_hair", "black_hair", "green_eyes"]
      },
      "outfit_json": {}
    }
  ],
  "act": {"act_no": 1, "title": "Stairwell", "outline": "blind mode; cast unbound",
          "status": "planned", "revision": 1},
  "beats": [
    {"id": "b01", "description": "She climbs, soaked.", "purpose": "action",
     "shots": [{"participants": ["LEAD"], "action": ["climbing_stairs"],
                "expression": ["tired"], "pose": ["standing"],
                "caption": "She climbs the wet stairs.", "outfit": ["t-shirt"]}]}
  ]
}
```

## Duo plan — roles stay directed

```json
"characters": [
  {"code": "LEAD", "name": "woman", "role": "placeholder", "gender": "girl",
   "adult": true, "identity_json": {"adult": true, "attributes": ["black_hair"]}},
  {"code": "PARTNER_A", "name": "man", "role": "placeholder", "gender": "boy",
   "adult": true, "identity_json": {"adult": true, "attributes": ["short_hair"]}}
]
```

```json
{"participants": ["LEAD", "PARTNER_A"],
 "purpose": "interaction",
 "action": ["holding_hands"],
 "character_actions": {"LEAD": ["holding_hands"], "PARTNER_A": ["smile"]},
 "sequence": {"actor": "LEAD", "target": "PARTNER_A", "purpose": "interaction",
              "reactionRequired": true},
 "caption": "The woman takes the stranger's hand; he smiles."}
```

`purpose: interaction` requires `sequence.target` plus a scoped action for the actor, or
`INTERACTION_TARGET_REQUIRED` / `INTERACTION_ACTOR_ACTION_MISSING` blocks the seed.

## Field mapping (`etl/seed_plan.py`)

| plan field | read by backend | blind-mode rule |
|---|---|---|
| `blind_mode` | no | `true`; survives in plan JSON only |
| `characters[].code` | roster + shot FK | stable role slot, never renamed |
| `characters[].name` | role clauses / captions | render-safe noun, no identity |
| `characters[].gender` | `cast_line` (`1girl`, `1boy`, ...) | explicit, drives counts |
| `characters[].adult` | `CONTENT_SAFETY_BLOCK` gate | must be `true` for nsfw |
| `characters[].identity_json.attributes` | prompt identity tokens | generic anchors only |
| `characters[].identity_json.identity_tags` | prompt identity tokens | empty — canon lives here |
| `characters[].identity_line` | prompt identity line | anchors, identical in every shot |
| `characters[].outfit_json` | per-shot outfit default | may stay `{}` |
| `role` | no | `placeholder`; DB stores identity_json only |

## Binding a slot (`etl/bind_character.py`)

```text
python etl/bind_character.py --list asuna                      # find codes
python etl/bind_character.py --plan <plan> --slot LEAD \
    --character ba_asuna_blue_archive --project-id 1 --dry-run
python etl/bind_character.py --plan <plan> --slot LEAD \
    --character ba_asuna_blue_archive --project-id 1
```

- Replaces `identity_json`/`outfit_json` from `character_profile`; drops placeholder anchors.
- Renames `code` and every reference: `participants`, `character_actions/poses/gaze/targets`,
  `reactions`, `sequence.actor/target`.
- `blind_mode` flips to `false` only when no placeholder slots remain.
- Display `name` is always derived from the DB canon tag, so a rebind swaps it too.
- Refuses a non-placeholder slot (unless `--force`), a code already bound in the plan, and an
  ambiguous code shared by several projects without `--project-id`.
- Runs `story_logic.validate_plan` before writing; ERRORs abort unless `--force`.

## QA checklist

- [ ] `blind_mode: true`, every character has `role: "placeholder"`.
- [ ] Codes uppercase, unique, unchanged across acts and revisions.
- [ ] `adult: true` at character level (and in `identity_json`) for nsfw/explicit.
- [ ] No `(...)` character tag, franchise, real name or guessed age anywhere.
- [ ] Anchor set identical in `identity_json.attributes` and `identity_line`; no drift
      without a declared change beat + revision bump.
- [ ] Every anchor/outfit/action/expression/camera tag exists in SQLite.
- [ ] Duo/group shots keep per-character roles and certified `sequence` direction.
- [ ] `build_story_plan` → `plan_actions` → `check_story` → `seed_plan --dry-run` →
      `check_prompts` clean of ERROR before render.
- [ ] Render status recorded as `PLACEHOLDER`; "placeholder" never appears in a prompt
      or caption.

## Failure modes

| symptom | cause | fix |
|---|---|---|
| `CONTENT_SAFETY_BLOCK` | nsfw plan without `adult: true` | set character + identity_json adult |
| `UNKNOWN_PARTICIPANT` | shot code not in `characters[]` | use the slot code |
| `INTERACTION_TARGET_REQUIRED` | `purpose: interaction` without target | declare sequence.target |
| `INTERACTION_ACTOR_ACTION_MISSING` | no `character_actions[actor]` | scope the action to the actor |
| `ADULT_TAG_MISSING` warning | `identity_line` lacks `adult` | add it to the anchors |
| identity drift between shots | anchors edited per shot | restore the fixed set |
