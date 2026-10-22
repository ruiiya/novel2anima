# ActSpec fixtures (tracked)

Small hand-written specs used by `tests/test_act_specs.py` to prove a clean
checkout can compile an act without `data/plans/`, `act_tools/` or the live DB.

- `solo_tea.json`: one participant, one shot.
- `duo_greeting.json`: two participants, interaction + reaction.

Compile with `python -m novel2anima.story.beat_planner --input <spec> --output data/plans/...`.
The spec holds project/characters/act plus `beats[]`; shot count is derived from
beats, never a fixed 60. Tag ids are resolved against the catalog at seed time.
