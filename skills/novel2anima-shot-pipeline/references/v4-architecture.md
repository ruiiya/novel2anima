# V4.1 architecture redirect

This file is intentionally small. Do not treat any earlier V1 snapshot as live runtime
schema, a supported endpoint list or evidence that a database is populated.

Canonical sources:

- [`docs/architecture/PIPELINE_EXECUTION_CONTROL.md`](../../../docs/architecture/PIPELINE_EXECUTION_CONTROL.md)
- [`docs/contracts/SKILL_RUNTIME_CONTRACTS.md`](../../../docs/contracts/SKILL_RUNTIME_CONTRACTS.md)
- [`docs/v4/README.md`](../../../docs/v4/README.md)
- Actual `sqlite_master` and `PRAGMA table_info(...)` on the target DB.

Story runtime: `start_story`, `resume_run`, `rerun_from` in
`src/novel2anima/pipeline/orchestrator.py`. Files are import/export/preview only.
