# act_tools

One-off act generators live outside the core ETL pipeline.

- `generators/` — per-act plan builders. Each has `main()`, `--dry-run` and
  `--output <dir>`; running it writes only under that directory.
- `act_quality.py` — shared pose/caption/expression helpers imported by the
  generators. Core validation stays in `etl/story_logic.py`.

New plan builders must not be added to `etl/`; `tests/test_layout.py` enforces
that. Generated plans still go through `etl/seed_plan.py` before any DB write.
